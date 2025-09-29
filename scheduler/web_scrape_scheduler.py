import logging
import asyncio
import random
import string
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from models.models import get_session, WebScrapeConfig, ProcessedPost
from crawler.web_scraper import scrape_page
from ai import get_ai_provider
from utils.common import get_bot_client
from datetime import datetime
from playwright.async_api import async_playwright

logger = logging.getLogger(__name__)

# 全局调度器实例
_global_web_scrape_scheduler = None

def get_web_scrape_scheduler():
    """获取全局网页抓取调度器实例"""
    return _global_web_scrape_scheduler

def set_web_scrape_scheduler(scheduler):
    """设置全局网页抓取调度器实例"""
    global _global_web_scrape_scheduler
    _global_web_scrape_scheduler = scheduler
URL_TEMPLATE = "https://coinmarketcap.com/community/coins/{coin_name}/latest/"

async def execute_scrape_task(task_id: int, bot_client):
    """执行单个抓取、总结和发送任务"""
    logger.info(f"开始执行网页抓取任务 ID: {task_id}")
    session = get_session()
    task = None
    try:
        task = session.query(WebScrapeConfig).get(task_id)
        if not (task and task.is_enabled and task.target_channel_id):
            logger.warning(f"任务 {task_id} 不存在、已禁用或未设置目标频道，跳过执行。")
            return

        all_new_posts = []
        posts_by_coin = {}
        processed_unique_ids = set()  # 跟踪本次任务已处理的帖子ID，防止重复
        coin_names = [name.strip() for name in task.coin_names.split(',')]

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            # 设置统一的 User-Agent
            user_agent = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36'
            context = await browser.new_context(user_agent=user_agent)
            page = await context.new_page()

            try:
                for coin in coin_names:
                    base_url = URL_TEMPLATE.format(coin_name=coin)
                    random_param = ''.join(random.choices(string.ascii_lowercase, k=5))
                    random_value = ''.join(random.choices(string.ascii_lowercase + string.digits, k=10))
                    url = f"{base_url}?{random_param}={random_value}"

                    try:
                        scraped_posts = await scrape_page(page, url, time_limit_hours=24)

                        # 检查是否有重复的帖子
                        unique_ids_in_scrape = {p['unique_id'] for p in scraped_posts}
                        if len(scraped_posts) != len(unique_ids_in_scrape):
                            logger.warning(
                                f"任务 {task.id} 在 {coin} 页面发现重复帖子，原始 {len(scraped_posts)} 个，去重后 {len(unique_ids_in_scrape)} 个"
                            )

                        # 筛选真正的新帖子（数据库中没有且本次任务未处理过）
                        db_processed_ids = {post.post_unique_id for post in task.processed_posts}
                        coin_new_posts = []

                        for post in scraped_posts:
                            unique_id = post['unique_id']
                            if unique_id not in db_processed_ids and unique_id not in processed_unique_ids:
                                coin_new_posts.append(post)
                                all_new_posts.append(post)
                                processed_unique_ids.add(unique_id)
                                logger.debug(f"任务 {task.id}: 添加新帖子 {unique_id}")
                            elif unique_id in processed_unique_ids:
                                logger.debug(f"任务 {task.id}: 跳过本次任务已处理的帖子 {unique_id}")

                        if coin_new_posts:
                            logger.info(f"任务 {task.id} 在 {coin} 页面发现 {len(coin_new_posts)} 个新帖子。")
                            posts_by_coin[coin] = coin_new_posts
                    except Exception as e:
                        logger.error(f"抓取币种 {coin} (URL: {url}) 时出错: {e}")
                        continue
            finally:
                # 确保顺序关闭以避免残留子进程
                try:
                    await page.close()
                except Exception:
                    pass
                try:
                    await context.close()
                except Exception:
                    pass
                try:
                    await browser.close()
                except Exception:
                    pass

        if posts_by_coin:
            content_for_ai = ""
            for coin, posts in posts_by_coin.items():
                content_for_ai += f"[COIN: {coin}]\n"
                core_contents = [p['content'].split(':', 1)[-1].strip() for p in posts]
                content_for_ai += "\n".join([f"- {c}" for c in core_contents])
                content_for_ai += "\n---\n"

            summary = ""
            try:
                if not task.ai_model or not task.summary_prompt:
                    raise ValueError("任务未配置AI模型或总结提示词。" )
                
                logger.info(f"任务 {task.id}: 准备进行AI总结。模型: {task.ai_model}")
                provider = await get_ai_provider(task.ai_model)
                prompt = task.summary_prompt
                summary = await provider.process_message(message=content_for_ai, prompt=prompt, model=task.ai_model)
                logger.info(f"任务 {task.id}: AI总结完成。")

            except Exception as e:
                logger.error(f"任务 {task.id}: AI总结过程中出错: {e}")
                summary = f"【AI总结失败】\n任务 '{task.task_name}' 发现 {len(all_new_posts)} 条新动态，但在总结时出错。\n错误: {e}"
            
            try:
                target_chat_id = int(task.target_channel_id)
                logger.info(f"任务 {task.id}: 准备将总结发送到频道 {target_chat_id}")
                await bot_client.send_message(target_chat_id, summary, parse_mode='markdown', link_preview=False)
                logger.info(f"任务 {task.id}: 已成功将总结发送到 {target_chat_id}")
            except Exception as e:
                logger.error(f"任务 {task.id}: 发送消息到频道 {target_chat_id} 时出错: {e}")

            for post in all_new_posts:
                processed = ProcessedPost(scrape_config_id=task.id, post_unique_id=post['unique_id'])
                session.add(processed)
            
            task.last_run_at = datetime.now()
            session.commit()
            logger.info(f"任务 {task.id}: 已将 {len(all_new_posts)} 个新帖子标记为已处理。")
        else:
            logger.info(f"任务 {task.id}: 执行完毕，未发现新内容。")

    except Exception as e:
        logger.error(f"执行抓取任务 {task_id} 时出错: {e}")
        logger.exception(e)
        if task and bot_client:
            await bot_client.send_message(task.user_id, f"网页抓取任务 '{task.task_name}' (ID: {task_id}) 执行失败，请检查日志。")
    finally:
        if session.is_active:
            session.close()

class WebScrapeScheduler:
    def __init__(self, bot_client):
        self.bot_client = bot_client
        self.scheduler = AsyncIOScheduler(timezone="Asia/Shanghai")

    async def start(self):
        """启动调度器并加载所有任务"""
        logger.info("正在启动网页抓取调度器...")
        session = get_session()
        try:
            tasks = session.query(WebScrapeConfig).filter_by(is_enabled=True).all()
            logger.info(f"找到 {len(tasks)} 个已启用的网页抓取任务。")
            for task in tasks:
                self.scheduler.add_job(
                    execute_scrape_task,
                    CronTrigger.from_crontab(task.schedule),
                    args=[task.id, self.bot_client],
                    id=f"scrape_task_{task.id}",
                    name=f"Scrape {task.task_name}",
                    misfire_grace_time=3600,
                    max_instances=1,
                    replace_existing=True
                )
                logger.info(f"已为任务 '{task.task_name}' (ID: {task.id}) 添加调度，cron: {task.schedule}")
        finally:
            session.close()
        
        if not self.scheduler.running:
            self.scheduler.start()
            logger.info("网页抓取调度器已启动。" )

    def stop(self):
        """停止调度器"""
        if self.scheduler.running:
            self.scheduler.shutdown()
            logger.info("网页抓取调度器已停止。" )
    
    async def reschedule_task(self, task_id):
        """重新调度指定任务"""
        session = get_session()
        try:
            task = session.query(WebScrapeConfig).filter_by(id=task_id, is_enabled=True).first()
            if not task:
                logger.warning(f"任务 ID {task_id} 不存在或已禁用，无法重新调度")
                return False
            
            job_id = f"scrape_task_{task_id}"
            
            # 检查任务是否存在
            if self.scheduler.get_job(job_id):
                # 重新调度现有任务
                self.scheduler.reschedule_job(
                    job_id,
                    trigger=CronTrigger.from_crontab(task.schedule)
                )
                logger.info(f"已重新调度任务 '{task.task_name}' (ID: {task_id})，新的 cron: {task.schedule}")
            else:
                # 任务不存在，添加新任务
                self.scheduler.add_job(
                    execute_scrape_task,
                    CronTrigger.from_crontab(task.schedule),
                    args=[task.id, self.bot_client],
                    id=job_id,
                    name=f"Scrape {task.task_name}",
                    misfire_grace_time=3600,
                    max_instances=1,
                    replace_existing=True
                )
                logger.info(f"已为任务 '{task.task_name}' (ID: {task_id}) 添加调度，cron: {task.schedule}")
            
            return True
        finally:
            session.close()

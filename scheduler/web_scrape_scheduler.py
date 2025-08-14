import logging
import asyncio
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from models.models import get_session, WebScrapeConfig, ProcessedPost, ForwardRule
from crawler.web_scraper import scrape_posts
from filters.process import process_forward_rule
from utils.common import SyntheticEvent, get_bot_client
from datetime import datetime

logger = logging.getLogger(__name__)
URL_TEMPLATE = "https://coinmarketcap.com/community/coins/{coin_name}/latest/"

async def execute_scrape_task(task_id: int, bot_client):
    """执行单个抓取任务，并将内容注入到关联的转发规则中进行处理。"""
    logger.info(f"开始执行网页抓取任务 ID: {task_id}")
    session = get_session()
    try:
        task = session.query(WebScrapeConfig).get(task_id)
        if not (task and task.is_enabled and task.forward_rule_id):
            logger.warning(f"任务 {task_id} 不存在、已禁用或未关联转发规则，跳过执行。")
            if bot_client and task:
                await bot_client.send_message(task.user_id, f"网页抓取任务 '{task.task_name}' (ID: {task_id}) 因未启用或未关联规则而跳过执行。")
            return

        rule = session.query(ForwardRule).get(task.forward_rule_id)
        if not rule:
            logger.error(f"任务 {task_id} 关联的转发规则 {task.forward_rule_id} 不存在。")
            await bot_client.send_message(task.user_id, f"网页抓取任务 '{task.task_name}' (ID: {task_id}) 关联的转发规则不存在，执行失败。")
            return

        posts_by_coin = {}
        all_new_posts_flat = []
        coin_names = [name.strip() for name in task.coin_names.split(',')]

        for coin in coin_names:
            url = URL_TEMPLATE.format(coin_name=coin)
            scraped_posts = await scrape_posts(url, time_limit_hours=24)
            
            if not scraped_posts:
                continue

            seen_post_ids = {p.post_unique_id for p in task.processed_posts}
            new_posts = [p for p in scraped_posts if p['unique_id'] not in seen_post_ids]
            
            if new_posts:
                logger.info(f"任务 {task.id} 在 {coin} 页面发现 {len(new_posts)} 个新帖子。")
                posts_by_coin[coin] = new_posts
                all_new_posts_flat.extend(new_posts)
            else:
                logger.info(f"任务 {task.id} 在 {coin} 页面没有发现新帖子。")

        if posts_by_coin:
            # 构建带有币种分类的文本内容
            content_for_ai = ""
            for coin, posts in posts_by_coin.items():
                content_for_ai += f"[COIN: {coin}]\n"
                for post in posts:
                    # 移除作者信息，只保留核心内容
                    core_content = post['content'].split(':', 1)[-1].strip()
                    content_for_ai += f"- {core_content}\n"
                content_for_ai += "---\n"
            
            logger.info(f"任务 {task.id}: 准备将 {len(all_new_posts_flat)} 个新帖子的内容注入规则 {rule.id} 进行处理。")
            synthetic_event = SyntheticEvent(text=content_for_ai, client=bot_client)
            
            await process_forward_rule(bot_client, synthetic_event, str(rule.source_chat_id), rule)

            for post in all_new_posts_flat:
                processed = ProcessedPost(scrape_config_id=task.id, post_unique_id=post['unique_id'])
                session.add(processed)
            
            task.last_run_at = datetime.now()
            session.commit()
            logger.info(f"任务 {task.id}: 已将 {len(all_new_posts_flat)} 个新帖子标记为已处理。")
            await bot_client.send_message(task.user_id, f"网页抓取任务 '{task.task_name}' 执行完毕，处理了 {len(all_new_posts_flat)} 条新内容。")
        else:
            await bot_client.send_message(task.user_id, f"网页抓取任务 '{task.task_name}' 执行完毕，未发现新内容。")

    except Exception as e:
        logger.error(f"执行抓取任务 {task_id} 时出错: {e}")
        logger.exception(e)
        if task:
            await bot_client.send_message(task.user_id, f"网页抓取任务 '{task.task_name}' (ID: {task_id}) 执行失败，请检查日志。")
    finally:
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
                    replace_existing=True
                )
                logger.info(f"已为任务 '{task.task_name}' (ID: {task.id}) 添加调度，cron: {task.schedule}")
        finally:
            session.close()
        
        if not self.scheduler.running:
            self.scheduler.start()
            logger.info("网页抓取调度器已启动。")

    def stop(self):
        """停止调度器"""
        if self.scheduler.running:
            self.scheduler.shutdown()
            logger.info("网页抓取调度器已停止。")

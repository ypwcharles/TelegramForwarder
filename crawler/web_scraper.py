import asyncio
from playwright.async_api import Page
import logging
import re
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

def parse_relative_time(time_str: str) -> datetime:
    """
    将 "5m", "2h", "3d" 这样的相对时间字符串转换为绝对的 datetime 对象。
    """
    now = datetime.now()
    time_str = time_str.lower().strip().replace("·", "").strip()

    if any(x in time_str for x in ["now", "just now", "seconds"]):
        return now
    
    if "minute" in time_str:
        value = int(re.search(r'(\d+)', time_str).group(1))
        return now - timedelta(minutes=value)
    if "hour" in time_str:
        value = int(re.search(r'(\d+)', time_str).group(1))
        return now - timedelta(hours=value)
    if "day" in time_str:
        value = int(re.search(r'(\d+)', time_str).group(1))
        return now - timedelta(days=value)

    return now - timedelta(days=365)

async def scrape_page(page: Page, url: str, time_limit_hours: int = 24) -> list[dict[str, str]]:
    """
    使用一个已有的 Playwright Page 对象来抓取单个 URL。
    """
    logger.info(f"开始使用页面对象抓取 URL: {url}")
    
    POST_SELECTOR = "div[data-test=\"community-post\"]"
    AUTHOR_NAME_SELECTOR = "span[data-test=\"post-username\"]"
    CONTENT_SELECTOR = "div.text"
    TIMESTAMP_SELECTOR = "span.tooltip"
    READ_MORE_SELECTOR = "Read all"

    scraped_posts = []
    processed_post_ids = set()
    time_limit_reached = False

    await page.goto(url, wait_until="networkidle", timeout=60000)

    try:
        cookie_button = page.get_by_role("button", name=re.compile("Accept|Allow all"))
        if await cookie_button.is_visible(timeout=2000):
            await cookie_button.click()
            await page.wait_for_timeout(1000)
    except Exception:
        logger.info("未找到Cookie按钮或处理时出错。")

    for i in range(20):
        if time_limit_reached:
            break

        posts_on_page = await page.query_selector_all(POST_SELECTOR)
        if not posts_on_page and i == 0:
            logger.warning(f"在 {url} 找不到任何帖子。")
            break

        for post_element in posts_on_page:
            try:
                post_id = await post_element.get_attribute('data-post-id')
                if not post_id or post_id in processed_post_ids:
                    continue

                timestamp_el = await post_element.query_selector(TIMESTAMP_SELECTOR)
                time_str = await timestamp_el.inner_text() if timestamp_el else ""
                post_time = parse_relative_time(time_str)

                if datetime.now() - post_time > timedelta(hours=time_limit_hours):
                    time_limit_reached = True
                    break

                try:
                    read_more_button = post_element.get_by_text(READ_MORE_SELECTOR)
                    if await read_more_button.is_visible(timeout=200):
                        await read_more_button.click()
                        await page.wait_for_timeout(200)
                except Exception:
                    pass

                author_name_el = await post_element.query_selector(AUTHOR_NAME_SELECTOR)
                content_el = await post_element.query_selector(CONTENT_SELECTOR)

                author_name = await author_name_el.inner_text() if author_name_el else "N/A"
                content = await content_el.inner_text() if content_el else ""
                
                full_content = f"{author_name}: {content.strip()}"

                scraped_posts.append({
                    'unique_id': post_id,
                    'content': full_content
                })
                processed_post_ids.add(post_id)

            except Exception as e:
                logger.warning(f"处理单个帖子时出错: {e}")
                continue
        
        if time_limit_reached:
            break

        await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        await page.wait_for_timeout(2000)

    logger.info(f"抓取完成。在 {url} 找到 {len(scraped_posts)} 个帖子。")
    return scraped_posts
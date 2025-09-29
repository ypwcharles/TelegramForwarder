import asyncio
from playwright.async_api import Page, Route
import logging
import re
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

# 资源类型黑名单
RESOURCE_EXCLUSIONS = ["image", "stylesheet", "font"]

# 全局抓取超时时间（秒），用于防止单页面长期卡住
SCRAPE_GLOBAL_TIMEOUT_SECONDS = 150

# Playwright默认超时（毫秒）
DEFAULT_OPERATION_TIMEOUT_MS = 20_000
DEFAULT_NAVIGATION_TIMEOUT_MS = 60_000

async def intercept_route(route: Route):
    """拦截并中止不需要的网络请求"""
    if route.request.resource_type in RESOURCE_EXCLUSIONS:
        await route.abort()
    else:
        await route.continue_()

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

    为避免单页面卡死，外层增加全局超时；并在异常/超时情况下提供清晰日志提示。
    """
    try:
        return await asyncio.wait_for(
            _scrape_page_impl(page, url, time_limit_hours),
            timeout=SCRAPE_GLOBAL_TIMEOUT_SECONDS,
        )
    except asyncio.TimeoutError:
        logger.error(
            f"抓取超时: {url} 超过 {SCRAPE_GLOBAL_TIMEOUT_SECONDS}s，已跳过该页面。"
        )
        # 兜底尝试移除路由拦截，防止下次调用受影响
        try:
            await page.unroute("**/*", intercept_route)
        except Exception:
            pass
        return []
    except Exception as e:
        logger.error(f"抓取页面时出现异常: URL: {url}, 错误: {e}")
        try:
            await page.unroute("**/*", intercept_route)
        except Exception:
            pass
        return []


async def _scrape_page_impl(page: Page, url: str, time_limit_hours: int) -> list[dict[str, str]]:
    logger.info(f"开始使用页面对象抓取 URL: {url}")

    # 设置默认超时，避免隐式等待过长
    try:
        page.set_default_timeout(DEFAULT_OPERATION_TIMEOUT_MS)
        page.set_default_navigation_timeout(DEFAULT_NAVIGATION_TIMEOUT_MS)
        logger.debug(
            f"已设置默认超时: 操作 {DEFAULT_OPERATION_TIMEOUT_MS}ms, 导航 {DEFAULT_NAVIGATION_TIMEOUT_MS}ms"
        )
    except Exception:
        # 某些旧版本playwright可能不支持，忽略
        pass

    # 启用请求拦截（在 finally 中确保清理）
    await page.route("**/*", intercept_route)

    POST_SELECTOR = "div[data-test=\"community-post\"]"
    AUTHOR_NAME_SELECTOR = "span[data-test=\"post-username\"]"
    CONTENT_SELECTOR = "div.text"
    TIMESTAMP_SELECTOR = "span.tooltip"
    READ_MORE_SELECTOR = "Read all"

    scraped_posts: list[dict[str, str]] = []
    processed_post_ids: set[str] = set()
    time_limit_reached = False

    try:
        logger.debug("开始导航到页面 (domcontentloaded)...")
        await page.goto(url, wait_until="domcontentloaded", timeout=DEFAULT_NAVIGATION_TIMEOUT_MS)
        logger.debug("页面导航完成。开始等待帖子选择器...")

        await page.wait_for_selector(POST_SELECTOR, timeout=30_000)
        logger.debug("帖子选择器已出现。")

        # 处理 Cookie 弹窗（如果存在）
        try:
            cookie_button = page.get_by_role("button", name=re.compile("Accept|Allow all"))
            if await cookie_button.is_visible(timeout=2_000):
                await cookie_button.click()
                await page.wait_for_timeout(1_000)
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
                        logger.debug(
                            f"遇到超出时间窗口的帖子(time='{time_str}'). 提前停止后续抓取。"
                        )
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
            await page.wait_for_timeout(2_000)

        logger.info(f"抓取完成。在 {url} 找到 {len(scraped_posts)} 个帖子。")
        return scraped_posts

    except asyncio.CancelledError:
        # 在全局超时导致取消时，也记录上下文，便于排查
        logger.error(f"抓取被取消(可能因超时): {url}")
        raise
    except Exception as e:
        logger.error(f"抓取流程异常: {url}, 错误: {e}")
        return []
    finally:
        # 禁用请求拦截（确保清理）
        try:
            await page.unroute("**/*", intercept_route)
        except Exception:
            pass

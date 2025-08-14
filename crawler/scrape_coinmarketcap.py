import asyncio
import json
from datetime import datetime, timedelta
import re
from playwright.async_api import async_playwright

# --- 配置 ---
URL = "https://coinmarketcap.com/community/coins/chainlink/latest/"
SCROLL_PAUSE_TIME = 2  # 每次滚动后等待加载的时间（秒）
MAX_SCROLLS = 20  # 最大滚动次数，防止无限循环
TIME_LIMIT_HOURS = 24  # 只抓取最近24小时内的帖子

# --- CSS 选择器 (根据2025年8月的页面结构，未来可能需要调整) ---
# 单个帖子的容器
POST_SELECTOR = "div[data-test=\"community-post\"]"
# 作者名
AUTHOR_NAME_SELECTOR = "span[data-test=\"post-username\"]"
# 作者Handle
AUTHOR_HANDLE_SELECTOR = "span[data-test=\"post-handle\"]"
# 发布时间
TIMESTAMP_SELECTOR = "span.tooltip"
# 帖子内容
CONTENT_SELECTOR = "div.text"
# “阅读更多”按钮
READ_MORE_SELECTOR = "Read all"

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

    # 如果格式不匹配（例如 "August 10"），则返回一个较早的日期以停止抓取
    return now - timedelta(days=365)

async def scrape_coinmarketcap():
    """
    主抓取函数
    """
    print("正在启动浏览器...")
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        print(f"正在导航到: {URL}")
        try:
            await page.goto(URL, wait_until="domcontentloaded", timeout=60000)
        except Exception as e:
            print(f"页面加载失败: {e}")
            await browser.close()
            return

        print("页面加载完成。开始抓取帖子...")

        scraped_posts = []
        processed_post_ids = set() # 用于去重
        time_limit_reached = False
        
        # 尝试接受 Cookie (如果存在)
        try:
            cookie_button = page.get_by_role("button", name=re.compile("Accept|Allow all"))
            await cookie_button.click(timeout=5000)
            print("已点击Cookie接受按钮ảng。")
            await page.wait_for_timeout(1000) # 等待弹窗消失
        except Exception:
            print("未找到Cookie按钮，或按钮不可见。继续操作...")


        for i in range(MAX_SCROLLS):
            if time_limit_reached:
                break

            print(f"--- 第 {i+1}/{MAX_SCROLLS} 次滚动 ---")
            
            posts_on_page = await page.query_selector_all(POST_SELECTOR)
            print(f"在当前页面找到 {len(posts_on_page)} 个帖子元素ảng。")

            if not posts_on_page and i == 0:
                print("错误：在页面上找不到任何帖子。请检查 POST_SELECTOR 是否正确ảng。")
                break

            for post_element in posts_on_page:
                try:
                    post_id = await post_element.get_attribute('data-post-id')
                    if not post_id or post_id in processed_post_ids:
                        continue # 跳过已处理或没有ID的帖子

                    timestamp_el = await post_element.query_selector(TIMESTAMP_SELECTOR)
                    time_str = await timestamp_el.inner_text() if timestamp_el else ""
                    
                    post_time = parse_relative_time(time_str)
                    
                    if datetime.now() - post_time > timedelta(hours=TIME_LIMIT_HOURS):
                        print(f"找到一个发布于 '{time_str}' 的帖子，已超过{TIME_LIMIT_HOURS}小时。停止抓取ảng。")
                        time_limit_reached = True
                        break

                    # 点击 "Read all"
                    try:
                        # 使用 get_by_text 定位器，更稳定
                        read_more_button = post_element.get_by_text(READ_MORE_SELECTOR)
                        if await read_more_button.is_visible(timeout=200):
                            await read_more_button.click()
                            await page.wait_for_timeout(200)
                    except Exception:
                        pass

                    author_name_el = await post_element.query_selector(AUTHOR_NAME_SELECTOR)
                    author_handle_el = await post_element.query_selector(AUTHOR_HANDLE_SELECTOR)
                    content_el = await post_element.query_selector(CONTENT_SELECTOR)

                    author_name = await author_name_el.inner_text() if author_name_el else "N/A"
                    author_handle = await author_handle_el.inner_text() if author_handle_el else "N/A"
                    content = await content_el.inner_text() if content_el else ""

                    post_data = {
                        "post_id": post_id,
                        "author_name": author_name.strip(),
                        "author_handle": author_handle.strip(),
                        "timestamp_str": time_str.replace("·", "").strip(),
                        "timestamp_iso": post_time.isoformat(),
                        "content": content.strip(),
                        "url": f"https://coinmarketcap.com/community/post/{post_id}"
                    }
                    
                    scraped_posts.append(post_data)
                    processed_post_ids.add(post_id)

                except Exception as e:
                    # print(f"处理单个帖子时出错: {e}")
                    continue
            
            if time_limit_reached:
                break

            await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            print("滚动页面...")
            await page.wait_for_timeout(SCROLL_PAUSE_TIME * 1000)

        print("抓取完成。正在关闭浏览器...")
        await browser.close()

        output_filename = "coinmarketcap_chainlink_posts.json"
        # 去重，以防万一
        unique_posts = {p['post_id']: p for p in scraped_posts}.values()

        with open(output_filename, 'w', encoding='utf-8') as f:
            json.dump(list(unique_posts), f, ensure_ascii=False, indent=4)

        print(f"成功抓取 {len(unique_posts)} 条帖子，已保存到 {output_filename}")

if __name__ == "__main__":
    asyncio.run(scrape_coinmarketcap())
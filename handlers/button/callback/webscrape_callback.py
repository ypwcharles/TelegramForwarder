import logging
import asyncio
from telethon import Button
from telethon.errors import MessageNotModifiedError
from managers.state_manager import state_manager
from handlers.button.webscrape_manager import (
    create_webscrape_text, create_webscrape_buttons, 
    create_task_settings_text, create_task_settings_buttons,
    create_ai_settings_buttons, create_model_selection_buttons_for_task,
    create_schedule_buttons
)
from models.models import get_session, WebScrapeConfig
from scheduler.web_scrape_scheduler import execute_scrape_task
from scheduler.web_scrape_scheduler import get_web_scrape_scheduler
from utils.common import get_bot_client

logger = logging.getLogger(__name__)

async def _edit_message(event, text, **kwargs):
    """一个安全的编辑消息的辅助函数，可以忽略 MessageNotModifiedError。"""
    try:
        await event.edit(text, **kwargs)
    except MessageNotModifiedError:
        logger.warning("消息未被修改，忽略错误。")
    except Exception as e:
        logger.error(f"编辑消息时发生未知错误: {e}")
        await event.answer("处理请求时出错，请查看日志。", alert=True)

async def handle_webscrape_callback(event, data):
    """处理所有以 'ws_' 开头的回调"""
    parts = data.split(':', 2)
    action = parts[0]
    task_id = parts[1] if len(parts) > 1 else None

    # ... (rest of the routing logic remains the same)
    if action == 'ws_add_new': await handle_ws_add_new(event)
    elif action == 'ws_back_to_list': await handle_ws_back_to_list(event)
    elif action == 'ws_close': await handle_ws_close(event)
    elif action == 'ws_cancel_add': await handle_ws_cancel_add(event)
    elif not task_id or not task_id.isdigit():
        await event.answer("无效的回调请求。", alert=True)
        return
    elif action == 'ws_task': await handle_ws_task_settings(event, task_id)
    elif action == 'ws_edit_coins': await handle_ws_edit_coins(event, task_id)
    elif action == 'ws_toggle_enable': await handle_ws_toggle_enable(event, task_id)
    elif action == 'ws_delete_task': await handle_ws_delete_task(event, task_id)
    elif action == 'ws_edit_schedule': await handle_ws_edit_schedule_menu(event, task_id)
    elif action == 'ws_set_schedule': await handle_ws_set_schedule(event, task_id, parts[2])
    elif action == 'ws_manual_schedule': await handle_ws_manual_schedule(event, task_id)
    elif action == 'ws_trigger_now': await handle_ws_trigger_now(event, task_id)
    elif action == 'ws_ai_settings': await handle_ws_ai_settings(event, task_id)
    elif action == 'ws_change_model': await handle_ws_change_model(event, task_id)
    elif action == 'ws_model_page': await handle_ws_model_page(event, task_id, parts[2])
    elif action == 'ws_select_model': await handle_ws_select_model(event, task_id, parts[2])
    elif action == 'ws_set_prompt': await handle_ws_set_prompt(event, task_id)
    elif action == 'ws_set_channel': await handle_ws_set_channel(event, task_id)

async def handle_ws_add_new(event):
    user_id, chat_id = event.sender_id, event.chat_id
    message = await event.get_message()
    state_manager.set_state(user_id, chat_id, 'awaiting_webscrape_task_name', message)
    await _edit_message(event, "**创建新任务**\n\n请发送任务名称：", buttons=[Button.inline("❌ 取消", "ws_cancel_add")], parse_mode='markdown')

async def handle_ws_cancel_add(event):
    user_id, chat_id = event.sender_id, event.chat_id
    state_manager.clear_state(user_id, chat_id)
    await handle_ws_back_to_list(event)

async def handle_ws_task_settings(event, task_id):
    session = get_session()
    try:
        task = session.query(WebScrapeConfig).get(int(task_id))
        text = await create_task_settings_text(task)
        buttons = await create_task_settings_buttons(task)
        await _edit_message(event, text, buttons=buttons, parse_mode='markdown')
    finally:
        session.close()

async def handle_ws_back_to_list(event):
    user_id = event.sender_id
    text = await create_webscrape_text(user_id)
    buttons = await create_webscrape_buttons(user_id)
    await _edit_message(event, text, buttons=buttons, parse_mode='markdown')

async def handle_ws_edit_coins(event, task_id):
    user_id, chat_id = event.sender_id, event.chat_id
    message = await event.get_message()
    state_manager.set_state(user_id, chat_id, f'awaiting_webscrape_coin_names:{task_id}', message)
    await _edit_message(event, """请输入**币种名称** (多个用逗号 `,` 分隔):""", buttons=[Button.inline("⬅️ 返回", f"ws_task:{task_id}")], parse_mode='markdown')

async def handle_ws_toggle_enable(event, task_id):
    session = get_session()
    try:
        task = session.query(WebScrapeConfig).get(int(task_id))
        task.is_enabled = not task.is_enabled
        session.commit()
        await event.answer(f"任务 '{task.task_name}' 已{'启用' if task.is_enabled else '禁用'}。")
        await handle_ws_task_settings(event, task_id)
    finally:
        session.close()

async def handle_ws_delete_task(event, task_id):
    session = get_session()
    try:
        task = session.query(WebScrapeConfig).get(int(task_id))
        session.delete(task)
        session.commit()
        await event.answer(f"任务 '{task.task_name}' 已删除。")
        await handle_ws_back_to_list(event)
    finally:
        session.close()

async def handle_ws_edit_schedule_menu(event, task_id):
    buttons = await create_schedule_buttons(int(task_id))
    await _edit_message(event, "请选择或手动输入定时 (Cron表达式)：", buttons=buttons)

async def handle_ws_set_schedule(event, task_id, cron_expression):
    session = get_session()
    try:
        task = session.query(WebScrapeConfig).get(int(task_id))
        task.schedule = cron_expression
        session.commit()
        
        # 重新调度任务
        scheduler = get_web_scrape_scheduler()
        if scheduler:
            await scheduler.reschedule_task(int(task_id))
        
        await event.answer(f"定时已更新为: {cron_expression}")
        await handle_ws_task_settings(event, task_id)
    finally:
        session.close()

async def handle_ws_manual_schedule(event, task_id):
    user_id, chat_id = event.sender_id, event.chat_id
    message = await event.get_message()
    state_manager.set_state(user_id, chat_id, f'awaiting_webscrape_schedule:{task_id}', message)
    await _edit_message(event, "请输入 Cron 表达式:", buttons=[Button.inline("⬅️ 返回", f"ws_task:{task_id}")], parse_mode='markdown')

async def handle_ws_trigger_now(event, task_id):
    await event.answer(f"正在手动触发任务 {task_id}...", alert=True)
    bot_client = await get_bot_client()
    asyncio.create_task(execute_scrape_task(int(task_id), bot_client))

async def handle_ws_close(event):
    await event.delete()

async def handle_ws_ai_settings(event, task_id):
    session = get_session()
    try:
        task = session.query(WebScrapeConfig).get(int(task_id))
        text = f"**AI 设置: {task.task_name}**\n\n当前模型: `{task.ai_model or '未设置'}`\n当前提示词: `{task.summary_prompt or '未设置'}`"
        buttons = await create_ai_settings_buttons(int(task_id))
        await _edit_message(event, text, buttons=buttons, parse_mode='markdown')
    finally:
        session.close()

async def handle_ws_set_prompt(event, task_id):
    user_id, chat_id = event.sender_id, event.chat_id
    message = await event.get_message()
    state_manager.set_state(user_id, chat_id, f'awaiting_webscrape_prompt:{task_id}', message)
    await _edit_message(event, "请输入新的AI总结提示词：", buttons=[Button.inline("⬅️ 返回AI设置", f"ws_ai_settings:{task_id}")], parse_mode='markdown')

async def handle_ws_set_channel(event, task_id):
    user_id, chat_id = event.sender_id, event.chat_id
    message = await event.get_message()
    state_manager.set_state(user_id, chat_id, f'awaiting_webscrape_channel:{task_id}', message)
    await _edit_message(event, "请发送目标频道的 **ID** 或**链接**:", buttons=[Button.inline("⬅️ 返回", f"ws_task:{task_id}")], parse_mode='markdown')

async def handle_ws_change_model(event, task_id):
    buttons = await create_model_selection_buttons_for_task(int(task_id))
    await _edit_message(event, "请选择一个AI模型：", buttons=buttons)

async def handle_ws_model_page(event, task_id, page):
    buttons = await create_model_selection_buttons_for_task(int(task_id), int(page))
    await _edit_message(event, "请选择一个AI模型：", buttons=buttons)

async def handle_ws_select_model(event, task_id, model_name):
    session = get_session()
    try:
        task = session.query(WebScrapeConfig).get(int(task_id))
        task.ai_model = model_name
        session.commit()
        await event.answer(f"AI模型已更新为: {model_name}")
        await handle_ws_ai_settings(event, task_id)
    finally:
        session.close()

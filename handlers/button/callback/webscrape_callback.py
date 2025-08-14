import logging
import asyncio
from telethon import Button
from managers.state_manager import state_manager
from handlers.button.webscrape_manager import (
    create_webscrape_text, create_webscrape_buttons, 
    create_task_settings_text, create_task_settings_buttons,
    create_rule_selection_buttons, create_schedule_buttons
)
from models.models import get_session, WebScrapeConfig
from scheduler.web_scrape_scheduler import execute_scrape_task
from utils.common import get_bot_client

logger = logging.getLogger(__name__)

async def handle_webscrape_callback(event, data):
    """处理所有以 'ws_' 开头的回调"""
    
    parts = data.split(':', 2)
    action = parts[0]
    task_id = parts[1] if len(parts) > 1 else None

    if action == 'ws_add_new':
        await handle_ws_add_new(event)
    elif action == 'ws_cancel_add':
        await handle_ws_cancel_add(event)
    elif action == 'ws_task':
        await handle_ws_task_settings(event, task_id)
    elif action == 'ws_back_to_list':
        await handle_ws_back_to_list(event)
    elif action == 'ws_edit_coins':
        await handle_ws_edit_coins(event, task_id)
    elif action == 'ws_toggle_enable':
        await handle_ws_toggle_enable(event, task_id)
    elif action == 'ws_delete_task':
        await handle_ws_delete_task(event, task_id)
    elif action == 'ws_link_rule_menu':
        await handle_ws_link_rule_menu(event, task_id)
    elif action == 'ws_link_rule':
        await handle_ws_link_rule(event, parts[1], parts[2])
    elif action == 'ws_edit_schedule':
        await handle_ws_edit_schedule_menu(event, task_id)
    elif action == 'ws_set_schedule':
        await handle_ws_set_schedule(event, parts[1], parts[2])
    elif action == 'ws_manual_schedule':
        await handle_ws_manual_schedule(event, task_id)
    elif action == 'ws_trigger_now':
        await handle_ws_trigger_now(event, task_id)
    elif action == 'ws_close':
        await handle_ws_close(event)

async def handle_ws_add_new(event):
    """处理'添加新任务'按钮的点击事件"""
    try:
        user_id = event.sender_id
        chat_id = event.chat_id
        message = await event.get_message()
        state_manager.set_state(user_id, chat_id, 'awaiting_webscrape_task_name', message)
        await event.edit(
            "**创建新的网页抓取任务**\n\n请直接在聊天中发送新任务的名称：",
            buttons=[Button.inline("❌ 取消", "ws_cancel_add")],
            parse_mode='markdown'
        )
    except Exception as e:
        logger.error(f"处理 ws_add_new 回调时出错: {e}")
        await event.answer("处理请求时出错，请查看日志。", alert=True)

async def handle_ws_cancel_add(event):
    """处理取消添加/编辑任务的操作"""
    user_id = event.sender_id
    chat_id = event.chat_id
    state_manager.clear_state(user_id, chat_id)
    await handle_ws_back_to_list(event)

async def handle_ws_task_settings(event, task_id):
    """显示特定任务的设置界面"""
    if not task_id or not task_id.isdigit():
        await event.answer("无效的任务ID。", alert=True)
        return

    session = get_session()
    try:
        task = session.query(WebScrapeConfig).get(int(task_id))
        if not task:
            await event.answer("找不到该任务。", alert=True)
            return
        
        text = await create_task_settings_text(task)
        buttons = await create_task_settings_buttons(task)
        await event.edit(text, buttons=buttons, parse_mode='markdown')

    except Exception as e:
        logger.error(f"显示任务设置时出错: {e}")
        await event.answer("获取任务详情时出错，请查看日志。", alert=True)
    finally:
        session.close()

async def handle_ws_back_to_list(event):
    """返回到任务列表"""
    try:
        user_id = event.sender_id
        text = await create_webscrape_text(user_id)
        buttons = await create_webscrape_buttons(user_id)
        await event.edit(text, buttons=buttons, parse_mode='markdown')
    except Exception as e:
        logger.error(f"返回任务列表时出错: {e}")
        await event.answer("返回列表时出错，请查看日志。", alert=True)

async def handle_ws_edit_coins(event, task_id):
    """处理'编辑币种'按钮的点击事件"""
    if not task_id or not task_id.isdigit():
        await event.answer("无效的任务ID。", alert=True)
        return

    try:
        user_id = event.sender_id
        chat_id = event.chat_id
        message = await event.get_message()
        state_manager.set_state(user_id, chat_id, f'awaiting_webscrape_coin_names:{task_id}', message)
        
        await event.edit(
            "请输入新的**币种名称**，多个名称请用英文逗号 `,` 分隔。\n" 
            "例如: `bitcoin,ethereum,chainlink`",
            buttons=[Button.inline("⬅️ 返回任务设置", f"ws_task:{task_id}")],
            parse_mode='markdown'
        )
    except Exception as e:
        logger.error(f"处理 ws_edit_coins 回调时出错: {e}")
        await event.answer("处理请求时出错，请查看日志。", alert=True)

async def handle_ws_toggle_enable(event, task_id):
    """处理启用/禁用任务的切换"""
    if not task_id or not task_id.isdigit():
        await event.answer("无效的任务ID。", alert=True)
        return
    
    session = get_session()
    try:
        task = session.query(WebScrapeConfig).get(int(task_id))
        if not task:
            await event.answer("找不到该任务。", alert=True)
            return
        
        task.is_enabled = not task.is_enabled
        session.commit()        
        await event.answer(f"任务 '{task.task_name}' 已{'启用' if task.is_enabled else '禁用'}。")
        await handle_ws_task_settings(event, task_id) # Refresh the settings view

    except Exception as e:
        logger.error(f"切换任务状态时出错: {e}")
        await event.answer("切换任务状态时出错，请查看日志。", alert=True)
    finally:
        session.close()

async def handle_ws_delete_task(event, task_id):
    """处理删除任务的按钮点击"""
    if not task_id or not task_id.isdigit():
        await event.answer("无效的任务ID。", alert=True)
        return

    session = get_session()
    try:
        task = session.query(WebScrapeConfig).get(int(task_id))
        if not task:
            await event.answer("找不到该任务。", alert=True)
            return
        
        session.delete(task)
        session.commit()
        
        await event.answer(f"任务 '{task.task_name}' 已被删除。" )
        await handle_ws_back_to_list(event) # Go back to the main list

    except Exception as e:
        logger.error(f"删除任务时出错: {e}")
        await event.answer("删除任务时出错，请查看日志。", alert=True)
    finally:
        session.close()

async def handle_ws_link_rule_menu(event, task_id):
    """显示可供关联的规则列表"""
    user_id = event.sender_id
    buttons = await create_rule_selection_buttons(user_id, task_id)
    await event.edit("请选择一个**转发规则**来处理抓取到的内容。", buttons=buttons, parse_mode='markdown')

async def handle_ws_link_rule(event, task_id, rule_id):
    """处理用户选择的转发规则，并将其关联到任务"""
    if not task_id or not task_id.isdigit() or not rule_id or not rule_id.isdigit():
        await event.answer("无效的任务或规则ID。", alert=True)
        return

    session = get_session()
    try:
        task = session.query(WebScrapeConfig).get(int(task_id))
        if not task:
            await event.answer("找不到该任务。", alert=True)
            return

        task.forward_rule_id = int(rule_id)
        session.commit()

        await event.answer(f"任务已成功关联到规则ID: {rule_id}")
        await handle_ws_task_settings(event, task_id) # Refresh the settings view

    except Exception as e:
        logger.error(f"关联规则时出错: {e}")
        await event.answer("关联规则时出错，请查看日志。", alert=True)
    finally:
        session.close()

async def handle_ws_edit_schedule_menu(event, task_id):
    """显示定时任务频率选择菜单"""
    if not task_id or not task_id.isdigit():
        await event.answer("无效的任务ID。", alert=True)
        return
    buttons = await create_schedule_buttons(task_id)
    await event.edit("请选择一个预设的执行频率，或手动输入：", buttons=buttons)

async def handle_ws_set_schedule(event, task_id, cron_expression):
    """处理预设的定时任务频率选择"""
    session = get_session()
    try:
        task = session.query(WebScrapeConfig).get(int(task_id))
        if not task:
            await event.answer("找不到该任务。", alert=True)
            return
        
        task.schedule = cron_expression
        session.commit()
        await event.answer(f"定时已更新为: {cron_expression}")
        await handle_ws_task_settings(event, task_id)
    finally:
        session.close()

async def handle_ws_manual_schedule(event, task_id):
    """处理'手动输入'定时的按钮点击事件"""
    if not task_id or not task_id.isdigit():
        await event.answer("无效的任务ID。", alert=True)
        return

    try:
        user_id = event.sender_id
        chat_id = event.chat_id
        message = await event.get_message()
        state_manager.set_state(user_id, chat_id, f'awaiting_webscrape_schedule:{task_id}', message)
        
        await event.edit(
            "请输入新的**定时规则 (Cron表达式)**。\n" 
            "例如: `0 */2 * * *` (每2小时执行一次)\n" 
            "您可以使用 [Crontab Guru](https://crontab.guru/) 来生成表达式。",
            buttons=[Button.inline("⬅️ 返回任务设置", f"ws_task:{task_id}")],
            parse_mode='markdown',
            link_preview=False
        )
    except Exception as e:
        logger.error(f"处理 ws_manual_schedule 回调时出错: {e}")
        await event.answer("处理请求时出错，请查看日志。", alert=True)

async def handle_ws_trigger_now(event, task_id):
    """处理手动触发任务的按钮点击"""
    if not task_id or not task_id.isdigit():
        await event.answer("无效的任务ID。", alert=True)
        return
    
    try:
        await event.answer(f"正在手动触发任务 {task_id}，请稍候...", alert=True)
        bot_client = await get_bot_client()
        asyncio.create_task(execute_scrape_task(int(task_id), bot_client))
    except Exception as e:
        logger.error(f"手动触发任务时出错: {e}")
        await event.answer("手动触发失败，请查看日志。", alert=True)

async def handle_ws_close(event):
    """处理关闭按钮，删除消息"""
    try:
        await event.delete()
    except Exception as e:
        logger.warning(f"关闭设置消息时出错: {e}")
        await event.answer("无法删除消息，可能权限不足或消息已过期。", alert=True)

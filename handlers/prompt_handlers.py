import logging
from models.models import get_session, ForwardRule, RuleSync, WebScrapeConfig, Chat
from managers.state_manager import state_manager
from utils.common import get_ai_settings_text
from handlers import bot_handler
from utils.auto_delete import async_delete_user_message
from utils.common import get_bot_client, get_main_module, get_user_client
import traceback
from utils.auto_delete import send_message_and_delete
from models.models import PushConfig
from telethon import Button
from handlers.button.webscrape_manager import create_task_settings_text, create_task_settings_buttons, create_ai_settings_buttons
from cron_validator import CronValidator
from scheduler.web_scrape_scheduler import get_web_scrape_scheduler

logger = logging.getLogger(__name__)

async def handle_prompt_setting(event, client, sender_id, chat_id, current_state, message):
    """处理等待用户输入的逻辑"""
    if event.message.text and event.message.text.startswith('/'):
        return False

    logger.info(f"开始处理用户输入状态, state: {current_state}")
    
    if not current_state:
        return False

    # --- WebScrape 流程 ---
    if current_state == 'awaiting_webscrape_task_name':
        return await handle_add_webscrape_task_name(event, client, sender_id, chat_id, message)
    
    task_id = None
    try:
        state_parts = current_state.split(':')
        if len(state_parts) > 1:
            task_id = int(state_parts[1])
    except (ValueError, IndexError):
        pass

    if not task_id:
        return False # 如果状态需要task_id但无法解析，则不处理

    if current_state.startswith('awaiting_webscrape_coin_names:'):
        return await handle_set_webscrape_field(event, sender_id, chat_id, message, task_id, 'coin_names', 'awaiting_webscrape_channel')
    elif current_state.startswith('awaiting_webscrape_schedule:'):
        return await handle_set_webscrape_schedule(event, sender_id, chat_id, message, task_id)
    elif current_state.startswith('awaiting_webscrape_channel:'):
        return await handle_set_webscrape_channel(event, sender_id, chat_id, message, task_id)
    elif current_state.startswith('awaiting_webscrape_prompt:'):
        return await handle_set_webscrape_field(event, sender_id, chat_id, message, task_id, 'summary_prompt', None) # End of flow
    
    # --- 其他流程 ---
    # (Existing logic for other prompt types can remain here)

    return False # Fallback

async def handle_add_webscrape_task_name(event, client, sender_id, chat_id, message):
    session = get_session()
    try:
        task_name = event.message.text.strip()
        if not task_name:
            await event.reply("任务名称不能为空，请重新输入。")
            return True

        new_task = WebScrapeConfig(user_id=sender_id, task_name=task_name, coin_names="", schedule="0 */1 * * *", is_enabled=False)
        session.add(new_task)
        session.commit()
        logger.info(f"为用户 {sender_id} 创建了新任务: {task_name} (ID: {new_task.id})")

        state_manager.set_state(sender_id, chat_id, f'awaiting_webscrape_coin_names:{new_task.id}', message)
        await async_delete_user_message(client, chat_id, event.message.id, 0)
        await message.edit(
            f"✅ 任务 **'{task_name}'** 已创建。\n\n下一步，请输入要抓取的**币种名称** (多个用逗号 `,` 分隔):",
            buttons=[Button.inline("❌ 取消", f"ws_delete_task:{new_task.id}")],
            parse_mode='markdown'
        )
        return True
    finally:
        session.close()

async def handle_set_webscrape_field(event, sender_id, chat_id, message, task_id, field_name, next_state_base):
    session = get_session()
    try:
        task = session.query(WebScrapeConfig).get(task_id)
        if not task: return True

        value = event.message.text.strip()
        if not value:
            await event.reply("输入不能为空，请重试。")
            return True

        setattr(task, field_name, value)
        session.commit()
        logger.info(f"任务 {task.id} 的 '{field_name}' 已更新为: {value}")
        await async_delete_user_message(event.client, chat_id, event.message.id, 0)

        if next_state_base:
            state_manager.set_state(sender_id, chat_id, f'{next_state_base}:{task.id}', message)
            next_prompt = {
                'awaiting_webscrape_channel': "✅ 币种已设置。\n\n下一步，请发送目标频道的 **ID** 或**链接**:"
            }.get(next_state_base, "请输入下一步内容：")
            await message.edit(next_prompt, buttons=[Button.inline("⬅️ 返回", f"ws_task:{task_id}")])
        else: # This is the end of a flow
            state_manager.clear_state(sender_id, chat_id)
            # 刷新AI设置界面
            text = f"**AI 设置: {task.task_name}**\n\n当前模型: `{task.ai_model or '未设置'}`\n当前提示词: `{task.summary_prompt or '未设置'}`"
            buttons = await create_ai_settings_buttons(task_id)
            await message.edit(text, buttons=buttons, parse_mode='markdown')
        return True
    finally:
        session.close()

async def handle_set_webscrape_schedule(event, sender_id, chat_id, message, task_id):
    session = get_session()
    try:
        task = session.query(WebScrapeConfig).get(task_id)
        if not task: return True

        cron_expression = event.message.text.strip()
        try:
            CronValidator.parse(cron_expression)
        except ValueError:
            await event.reply("无效的 Cron 表达式，请重试。")
            return True

        task.schedule = cron_expression
        session.commit()
        
        # 重新调度任务
        scheduler = get_web_scrape_scheduler()
        if scheduler:
            await scheduler.reschedule_task(task_id)
        
        state_manager.clear_state(sender_id, chat_id)
        await async_delete_user_message(event.client, chat_id, event.message.id, 0)
        
        text = await create_task_settings_text(task)
        buttons = await create_task_settings_buttons(task)
        await message.edit(text, buttons=buttons, parse_mode='markdown')
        return True
    finally:
        session.close()

async def handle_set_webscrape_channel(event, sender_id, chat_id, message, task_id):
    session = get_session()
    try:
        task = session.query(WebScrapeConfig).get(task_id)
        if not task: return True

        channel_input = event.message.text.strip()
        try:
            client = await get_user_client() # 使用用户客户端来识别链接
            entity = await client.get_entity(channel_input)
            task.target_channel_id = str(entity.id)
            session.commit()
            logger.info(f"任务 {task.id} 的目标频道已更新为: {entity.id}")

            state_manager.clear_state(sender_id, chat_id)
            await async_delete_user_message(client, chat_id, event.message.id, 0)
            
            text = await create_task_settings_text(task)
            buttons = await create_task_settings_buttons(task)
            await message.edit(text, buttons=buttons, parse_mode='markdown')
        except Exception as e:
            logger.error(f"无法识别频道: {channel_input}, error: {e}")
            await event.reply("无法识别该频道，请确保链接或ID正确，且机器人是该频道的管理员。")
            return True # Keep state
        return True
    finally:
        session.close()
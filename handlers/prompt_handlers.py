import logging
from models.models import get_session, ForwardRule, RuleSync, WebScrapeConfig
from managers.state_manager import state_manager
from utils.common import get_ai_settings_text
from handlers import bot_handler
from utils.auto_delete import async_delete_user_message
from utils.common import get_bot_client, get_main_module
import traceback
from utils.auto_delete import send_message_and_delete
from models.models import PushConfig
from telethon import Button
from handlers.button.webscrape_manager import create_rule_selection_buttons, create_task_settings_text, create_task_settings_buttons
from cron_validator import CronValidator

logger = logging.getLogger(__name__)

async def handle_prompt_setting(event, client, sender_id, chat_id, current_state, message):
    """处理等待用户输入的逻辑"""
    # 如果收到的消息是命令，则忽略当前状态，让命令处理器去处理
    if event.message.text and event.message.text.startswith('/'):
        return False

    logger.info(f"开始处理提示词设置,用户ID:{sender_id},聊天ID:{chat_id},当前状态:{current_state}")
    
    if not current_state:
        return False

    # --- WebScrape 流程 ---
    if current_state == 'awaiting_webscrape_task_name':
        return await handle_add_webscrape_task_name(event, client, sender_id, chat_id, message)
    elif current_state.startswith('awaiting_webscrape_coin_names:'):
        task_id = current_state.split(':')[1]
        return await handle_add_webscrape_coin_names(event, client, sender_id, chat_id, message, task_id)
    elif current_state.startswith('awaiting_webscrape_schedule:'):
        task_id = current_state.split(':')[1]
        return await handle_set_webscrape_schedule(event, client, sender_id, chat_id, message, task_id)
    
    # --- 其他流程 ---
    rule_id = None
    field_name = None 
    prompt_type = None
    template_type = None

    if current_state.startswith("set_summary_prompt:"):
        rule_id = current_state.split(":")[1]
        field_name = "summary_prompt"
        prompt_type = "AI总结"
        template_type = "ai"
    elif current_state.startswith("set_ai_prompt:"):
        rule_id = current_state.split(":")[1]
        field_name = "ai_prompt"
        prompt_type = "AI"
        template_type = "ai"
    elif current_state.startswith("set_userinfo_template:"):
        rule_id = current_state.split(":")[1]
        field_name = "userinfo_template"
        prompt_type = "用户信息"
        template_type = "userinfo"
    elif current_state.startswith("set_time_template:"):
        rule_id = current_state.split(":")[1]
        field_name = "time_template"
        prompt_type = "时间"
        template_type = "time"
    elif current_state.startswith("set_original_link_template:"):
        rule_id = current_state.split(":")[1]
        field_name = "original_link_template"
        prompt_type = "原始链接"
        template_type = "link"
    elif current_state.startswith("add_push_channel:"):
        rule_id = current_state.split(":")[1]
        return await handle_add_push_channel(event, client, sender_id, chat_id, rule_id, message)
    else:
        return False

    session = get_session()
    try:
        rule = session.query(ForwardRule).get(int(rule_id))
        if rule:
            setattr(rule, field_name, event.message.text)
            session.commit()
            if rule.enable_sync:
                # ... (sync logic as before) ...
                pass
            state_manager.clear_state(sender_id, chat_id)
            await async_delete_user_message(client, chat_id, event.message.id, 0)
            await message.delete()
            # ... (send updated settings message) ...
            return True
    finally:
        session.close()
    return True

async def handle_add_push_channel(event, client, sender_id, chat_id, rule_id, message):
    # ... (implementation as before) ...
    pass

async def handle_add_webscrape_task_name(event, client, sender_id, chat_id, message):
    """处理用户输入的网页抓取任务名称"""
    session = get_session()
    try:
        task_name = event.message.text.strip()
        if not task_name:
            await event.reply("任务名称不能为空，请重新输入。")
            return True

        new_task = WebScrapeConfig(
            user_id=sender_id,
            task_name=task_name,
            coin_names="",
            forward_rule_id=0, # Placeholder
            is_enabled=False
        )
        session.add(new_task)
        session.commit()
        logger.info(f"为用户 {sender_id} 创建了新的网页抓取任务: {task_name} (ID: {new_task.id})")

        state_manager.set_state(sender_id, chat_id, f'awaiting_webscrape_coin_names:{new_task.id}', message)
        await async_delete_user_message(client, chat_id, event.message.id, 0)
        await message.edit(
            f"✅ 任务 **'{task_name}'** 已创建。\n\n下一步，请输入要抓取的**币种名称**，多个名称请用英文逗号 `,` 分隔。",
            buttons=[Button.inline("❌ 取消", f"ws_delete_task:{new_task.id}")],
            parse_mode='markdown'
        )
        return True
    except Exception as e:
        logger.error(f"创建网页抓取任务时出错: {e}")
        await message.edit("创建任务时发生错误，请检查日志。")
        state_manager.clear_state(sender_id, chat_id)
        return True
    finally:
        session.close()

async def handle_add_webscrape_coin_names(event, client, sender_id, chat_id, message, task_id):
    """处理用户输入的币种名称"""
    session = get_session()
    try:
        task = session.query(WebScrapeConfig).get(int(task_id))
        if not task:
            await event.reply("找不到对应的任务，请重试。")
            state_manager.clear_state(sender_id, chat_id)
            return True

        coin_names = event.message.text.strip()
        if not coin_names:
            await event.reply("币种名称不能为空，请重新输入。")
            return True

        task.coin_names = coin_names
        session.commit()
        logger.info(f"任务 {task.id} 的币种已更新为: {coin_names}")

        state_manager.set_state(sender_id, chat_id, f'awaiting_webscrape_rule_link:{task_id}', message)
        await async_delete_user_message(client, chat_id, event.message.id, 0)

        buttons = await create_rule_selection_buttons(sender_id, task.id)
        await message.edit(
            f"✅ 币种已设置为: `{task.coin_names}`\n\n下一步，请选择一个**转发规则**来处理抓取到的内容。",
            buttons=buttons,
            parse_mode='markdown'
        )
        return True
    except Exception as e:
        logger.error(f"设置币种名称时出错: {e}")
        await message.edit("设置币种时发生错误，请检查日志。")
        state_manager.clear_state(sender_id, chat_id)
        return True
    finally:
        session.close()

async def handle_set_webscrape_schedule(event, client, sender_id, chat_id, message, task_id):
    """处理用户输入的定时任务 Cron 表达式"""
    session = get_session()
    try:
        task = session.query(WebScrapeConfig).get(int(task_id))
        if not task:
            await event.reply("找不到对应的任务，请重试。")
            state_manager.clear_state(sender_id, chat_id)
            return True

        cron_expression = event.message.text.strip()
        try:
            CronValidator.parse(cron_expression)
        except ValueError:
            await event.reply("无效的 Cron 表达式，请检查格式后重新输入。")
            return True # 保持状态，让用户重试

        task.schedule = cron_expression
        session.commit()
        logger.info(f"任务 {task.id} 的定时已更新为: {cron_expression}")

        state_manager.clear_state(sender_id, chat_id)
        await async_delete_user_message(client, chat_id, event.message.id, 0)

        # 刷新任务设置界面
        text = await create_task_settings_text(task)
        buttons = await create_task_settings_buttons(task)
        await message.edit(text, buttons=buttons, parse_mode='markdown')
        return True

    except Exception as e:
        logger.error(f"设置定时任务时出错: {e}")
        await message.edit("设置定时任务时发生错误，请检查日志。")
        state_manager.clear_state(sender_id, chat_id)
        return True
    finally:
        session.close()
from telethon import Button
from models.models import get_session, WebScrapeConfig, ForwardRule, Chat
import logging

logger = logging.getLogger(__name__)

async def create_webscrape_text(user_id: int) -> str:
    """为网页抓取功能创建主菜单文本"""
    session = get_session()
    try:
        tasks = session.query(WebScrapeConfig).filter_by(user_id=user_id).order_by(WebScrapeConfig.id).all()
        if not tasks:
            return "您还没有创建任何网页抓取任务。"

        text = "以下是您已创建的网页抓取任务:\n\n"
        for i, task in enumerate(tasks, 1):
            status = "✅" if task.is_enabled else "❌"
            rule_info = f"规则ID: {task.forward_rule_id}" if task.forward_rule_id else "未关联"
            text += f"{i}. {status} **{task.task_name}** (关联到 {rule_info})\n"
            text += f"   - 抓取币种: `{task.coin_names}`\n"
            text += f"   - 定时: `{task.schedule}`\n\n"
        text += "点击下方按钮可管理特定任务。"
        return text
    finally:
        session.close()

async def create_webscrape_buttons(user_id: int) -> list:
    """为网页抓取功能创建主菜单按钮"""
    session = get_session()
    try:
        tasks = session.query(WebScrapeConfig).filter_by(user_id=user_id).order_by(WebScrapeConfig.id).all()
        buttons = []
        task_buttons = [Button.inline(task.task_name, f"ws_task:{task.id}") for task in tasks]
        for i in range(0, len(task_buttons), 3):
            buttons.append(task_buttons[i:i+3])

        buttons.append([Button.inline("➕ 添加新任务", "ws_add_new"), Button.inline("✖️ 关闭", "ws_close")])
        return buttons
    finally:
        session.close()

async def create_task_settings_text(task: WebScrapeConfig) -> str:
    """为单个抓取任务创建设置文本"""
    session = get_session()
    try:
        status = "✅ 已启用" if task.is_enabled else "❌ 已禁用"
        rule_info = "未设置"
        if task.forward_rule_id:
            rule = session.query(ForwardRule).get(task.forward_rule_id)
            if rule:
                rule_info = f"ID: {rule.id} ({rule.source_chat.name} -> {rule.target_chat.name})"

        text = f"**正在管理任务: {task.task_name}**\n\n"
        text += f"- **状态**: {status}\n"
        text += f"- **币种**: `{task.coin_names}`\n"
        text += f"- **定时 (Cron)**: `{task.schedule}`\n"
        text += f"- **关联规则**: {rule_info}\n"
        return text
    finally:
        session.close()

async def create_task_settings_buttons(task: WebScrapeConfig) -> list:
    """为单个抓取任务创建设置按钮"""
    task_id = task.id
    status_text = "⏹️ 禁用" if task.is_enabled else "▶️ 启用"
    buttons = [
        [Button.inline("📝 编辑币种", f"ws_edit_coins:{task_id}"), Button.inline("⏰ 编辑定时", f"ws_edit_schedule:{task_id}")],
        [Button.inline("🔗 关联规则", f"ws_link_rule_menu:{task_id}"), Button.inline(status_text, f"ws_toggle_enable:{task_id}")],
        [Button.inline("▶️ 立即执行一次", f"ws_trigger_now:{task_id}")],
        [Button.inline("🗑️ 删除任务", f"ws_delete_task:{task_id}")],
        [Button.inline("⬅️ 返回列表", "ws_back_to_list")]
    ]
    return buttons

async def create_rule_selection_buttons(user_id: int, task_id: int) -> list:
    """创建一个按钮列表，让用户选择要关联的转发规则"""
    session = get_session()
    try:
        # 找到该用户作为目标的所有聊天
        user_chats = session.query(Chat).filter(Chat.target_rules.any(ForwardRule.target_chat.has(telegram_chat_id=str(user_id)))).all()
        chat_ids = [c.id for c in user_chats]
        
        # 找到所有与该用户相关的规则
        rules = session.query(ForwardRule).filter(ForwardRule.target_chat_id.in_(chat_ids)).all()
        
        buttons = []
        if not rules:
            buttons.append([Button.inline("没有可用的转发规则", "noop")])
        else:
            for rule in rules:
                button_text = f"{rule.source_chat.name} -> {rule.target_chat.name} (ID: {rule.id})"
                buttons.append([Button.inline(button_text, f"ws_link_rule:{task_id}:{rule.id}")])
        
        buttons.append([Button.inline("⬅️ 取消", f"ws_task:{task_id}")])
        return buttons
    finally:
        session.close()

async def create_schedule_buttons(task_id: int) -> list:
    """创建用于选择定时任务频率的按钮"""
    buttons = [
        [Button.inline("每小时", f"ws_set_schedule:{task_id}:0 * * * *")],
        [Button.inline("每3小时", f"ws_set_schedule:{task_id}:0 */3 * * *")],
        [Button.inline("每12小时", f"ws_set_schedule:{task_id}:0 */12 * * *")],
        [Button.inline("每天9点", f"ws_set_schedule:{task_id}:0 9 * * *")],
        [Button.inline("手动输入", f"ws_manual_schedule:{task_id}")],
        [Button.inline("⬅️ 返回", f"ws_task:{task_id}")]
    ]
    return buttons
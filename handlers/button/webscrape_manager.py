from telethon import Button
from models.models import get_session, WebScrapeConfig, ForwardRule, Chat
from utils.settings import load_ai_models
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
            target_info = f"频道ID: {task.target_channel_id}" if task.target_channel_id else "未设置"
            text += f"{i}. {status} **{task.task_name}** (发送到 {target_info})\n"
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
    status = "✅ 已启用" if task.is_enabled else "❌ 已禁用"
    target_info = task.target_channel_id if task.target_channel_id else "尚未设置"
    ai_model = task.ai_model if task.ai_model else "尚未设置"
    prompt = task.summary_prompt or "尚未设置"
    prompt_display = (prompt[:50] + '...') if len(prompt) > 50 else prompt

    text = f"**正在管理任务: {task.task_name}**\n\n"
    text += f"- **状态**: {status}\n"
    text += f"- **币种**: `{task.coin_names}`\n"
    text += f"- **定时 (Cron)**: `{task.schedule}`\n"
    text += f"- **目标频道 ID**: `{target_info}`\n"
    text += f"- **AI 模型**: `{ai_model}`\n"
    text += f"- **总结提示词**: `{prompt_display}`\n"
    return text

async def create_task_settings_buttons(task: WebScrapeConfig) -> list:
    """为单个抓取任务创建设置按钮"""
    task_id = task.id
    status_text = "⏹️ 禁用" if task.is_enabled else "▶️ 启用"
    buttons = [
        [Button.inline("📝 编辑币种", f"ws_edit_coins:{task_id}"), Button.inline("⏰ 编辑定时", f"ws_edit_schedule:{task_id}")],
        [Button.inline("🎯 设置频道", f"ws_set_channel:{task_id}"), Button.inline("🤖 AI 设置", f"ws_ai_settings:{task_id}")],
        [Button.inline(status_text, f"ws_toggle_enable:{task_id}"), Button.inline("▶️ 立即执行一次", f"ws_trigger_now:{task_id}")],
        [Button.inline("🗑️ 删除任务", f"ws_delete_task:{task_id}"), Button.inline("⬅️ 返回列表", "ws_back_to_list")]
    ]
    return buttons

async def create_ai_settings_buttons(task_id: int) -> list:
    """创建AI设置相关的按钮"""
    buttons = [
        [Button.inline("更改AI模型", f"ws_change_model:{task_id}")],
        [Button.inline("设置总结提示词", f"ws_set_prompt:{task_id}")],
        [Button.inline("⬅️ 返回", f"ws_task:{task_id}")]
    ]
    return buttons

async def create_model_selection_buttons_for_task(task_id: int, page: int = 0) -> list:
    """为网页抓取任务创建AI模型选择按钮（带分页）"""
    models_config = load_ai_models(type="list")
    buttons = []
    models_per_page = 10
    start_index = page * models_per_page
    end_index = start_index + models_per_page
    
    paginated_models = models_config[start_index:end_index]

    for model in paginated_models:
        buttons.append([Button.inline(model, f"ws_select_model:{task_id}:{model}")])

    nav_buttons = []
    if page > 0:
        nav_buttons.append(Button.inline("⬅️ 上一页", f"ws_model_page:{task_id}:{page-1}"))
    if end_index < len(models_config):
        nav_buttons.append(Button.inline("下一页 ➡️", f"ws_model_page:{task_id}:{page+1}"))
    
    if nav_buttons:
        buttons.append(nav_buttons)

    buttons.append([Button.inline("⬅️ 返回AI设置", f"ws_ai_settings:{task_id}")])
    return buttons

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

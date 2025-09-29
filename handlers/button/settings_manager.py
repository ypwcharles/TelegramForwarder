import os
from utils.settings import load_ai_models
from enums.enums import ForwardMode, MessageMode, PreviewMode, AddMode, HandleMode
from models.models import get_session
from telethon import Button
from utils.constants import RSS_ENABLED, UFB_ENABLED

AI_MODELS = load_ai_models()

# 规则配置字段定义
RULE_SETTINGS = {
    'enable_rule': {
        'display_name': '是否启用规则',
        'values': {
            True: '是',
            False: '否'
        },
        'toggle_action': 'toggle_enable_rule',
        'toggle_func': lambda current: not current
    },
    'add_mode': {
        'display_name': '当前关键字添加模式',
        'values': {
            AddMode.WHITELIST: '白名单',
            AddMode.BLACKLIST: '黑名单'
        },
        'toggle_action': 'toggle_add_mode',
        'toggle_func': lambda current: AddMode.BLACKLIST if current == AddMode.WHITELIST else AddMode.WHITELIST
    },
    'is_filter_user_info': {
        'display_name': '过滤关键字时是否附带发送者名称和ID',
        'values': {
            True: '是',
            False: '否'
        },
        'toggle_action': 'toggle_filter_user_info',
        'toggle_func': lambda current: not current
    },
    'forward_mode': {
        'display_name': '转发模式',
        'values': {
            ForwardMode.BLACKLIST: '仅黑名单',
            ForwardMode.WHITELIST: '仅白名单',
            ForwardMode.BLACKLIST_THEN_WHITELIST: '先黑名单后白名单', 
            ForwardMode.WHITELIST_THEN_BLACKLIST: '先白名单后黑名单'
        },
        'toggle_action': 'toggle_forward_mode',
        'toggle_func': lambda current: {
            ForwardMode.BLACKLIST: ForwardMode.WHITELIST,
            ForwardMode.WHITELIST: ForwardMode.BLACKLIST_THEN_WHITELIST,
            ForwardMode.BLACKLIST_THEN_WHITELIST: ForwardMode.WHITELIST_THEN_BLACKLIST,
            ForwardMode.WHITELIST_THEN_BLACKLIST: ForwardMode.BLACKLIST
        }[current]
    },
    'use_bot': {
        'display_name': '转发方式',
        'values': {
            True: '使用机器人',
            False: '使用用户账号'
        },
        'toggle_action': 'toggle_bot',
        'toggle_func': lambda current: not current
    },
    'is_replace': {
        'display_name': '替换模式',
        'values': {
            True: '开启',
            False: '关闭'
        },
        'toggle_action': 'toggle_replace',
        'toggle_func': lambda current: not current
    },
    'message_mode': {
        'display_name': '消息模式',
        'values': {
            MessageMode.MARKDOWN: 'Markdown',
            MessageMode.HTML: 'HTML'
        },
        'toggle_action': 'toggle_message_mode',
        'toggle_func': lambda current: MessageMode.HTML if current == MessageMode.MARKDOWN else MessageMode.MARKDOWN
    },
    'is_preview': {
        'display_name': '预览模式',
        'values': {
            PreviewMode.ON: '开启',
            PreviewMode.OFF: '关闭',
            PreviewMode.FOLLOW: '跟随原消息'
        },
        'toggle_action': 'toggle_preview',
        'toggle_func': lambda current: {
            PreviewMode.ON: PreviewMode.OFF,
            PreviewMode.OFF: PreviewMode.FOLLOW,
            PreviewMode.FOLLOW: PreviewMode.ON
        }[current]
    },
    'is_original_link': {
        'display_name': '原始链接',
        'values': {
            True: '附带',
            False: '不附带'
        },
        'toggle_action': 'toggle_original_link',
        'toggle_func': lambda current: not current
    },
    'is_delete_original': {
        'display_name': '删除原始消息',
        'values': {
            True: '开启',
            False: '关闭'
        },
        'toggle_action': 'toggle_delete_original',
        'toggle_func': lambda current: not current
    },
    'is_ufb': {
        'display_name': 'UFB同步',
        'values': {
            True: '开启',
            False: '关闭'
        },
        'toggle_action': 'toggle_ufb',
        'toggle_func': lambda current: not current
    },
    'is_original_sender': {
        'display_name': '原始发送者',
        'values': {
            True: '显示',
            False: '隐藏'
        },
        'toggle_action': 'toggle_original_sender',
        'toggle_func': lambda current: not current
    },
    'is_original_time': {
        'display_name': '发送时间',
        'values': {
            True: '显示',
            False: '隐藏'
        },
        'toggle_action': 'toggle_original_time',
        'toggle_func': lambda current: not current
    },
    # 添加延迟过滤器设置
    'enable_delay': {
        'display_name': '延迟处理',
        'values': {
            True: '开启',
            False: '关闭'
        },
        'toggle_action': 'toggle_enable_delay',
        'toggle_func': lambda current: not current
    },
    'delay_seconds': {
        'values': {
            None: 5,
            '': 5
        },
        'toggle_action': 'set_delay_time',
        'toggle_func': None
    },
    'handle_mode': {
        'display_name': '处理模式',
        'values': {
            HandleMode.FORWARD: '转发模式',
            HandleMode.EDIT: '编辑模式'
        },
        'toggle_action': 'toggle_handle_mode',
        'toggle_func': lambda current: HandleMode.EDIT if current == HandleMode.FORWARD else HandleMode.FORWARD
    },
    'enable_comment_button': {
        'display_name': '查看评论区',
        'values': {
            True: '开启',
            False: '关闭'
        },
        'toggle_action': 'toggle_enable_comment_button',
        'toggle_func': lambda current: not current
    },
    'only_rss': {
        'display_name': '只转发到RSS',
        'values': {
            True: '开启',
            False: '关闭'
        },
        'toggle_action': 'toggle_only_rss',
        'toggle_func': lambda current: not current
    },
    'close_settings': {
        'display_name': '关闭',
        'toggle_action': 'close_settings',
        'toggle_func': None
    },
    'enable_sync': {
        'display_name': '启用同步',
        'values': {
            True: '开启',
            False: '关闭'
        },
        'toggle_action': 'toggle_enable_sync',
        'toggle_func': lambda current: not current
    }
}


# 添加 AI 设置
AI_SETTINGS = {
    'is_ai': {
        'display_name': 'AI处理',
        'values': {
            True: '开启',
            False: '关闭'
        },
        'toggle_action': 'toggle_ai',
        'toggle_func': lambda current: not current
    },
    'ai_model': {
        'display_name': 'AI模型',
        'values': {
            None: '默认',
            '': '默认',
            **{model: model for model in AI_MODELS}
        },
        'toggle_action': 'change_model',
        'toggle_func': None
    },
    'ai_prompt': {
        'display_name': '设置AI处理提示词',
        'toggle_action': 'set_ai_prompt',
        'toggle_func': None
    },
    'enable_ai_upload_image': {
        'display_name': '上传图片',
        'values': {
            True: '开启',
            False: '关闭'
        },
        'toggle_action': 'toggle_ai_upload_image',
        'toggle_func': lambda current: not current
    },
    'is_keyword_after_ai': {
        'display_name': 'AI处理后再次执行关键字过滤',
        'values': {
            True: '开启',
            False: '关闭'
        },
        'toggle_action': 'toggle_keyword_after_ai',
        'toggle_func': lambda current: not current
    },
    'is_summary': {
        'display_name': 'AI总结',
        'values': {
            True: '开启',
            False: '关闭'
        },
        'toggle_action': 'toggle_summary',
        'toggle_func': lambda current: not current
    },
    'summary_time': {
        'display_name': '总结时间',
        'values': {
            None: '00:00',
            '': '00:00'
        },
        'toggle_action': 'set_summary_time',
        'toggle_func': None
    },
    'summary_prompt': {
        'display_name': '设置AI总结提示词',
        'toggle_action': 'set_summary_prompt',
        'toggle_func': None
    },
    'is_top_summary': {
        'display_name': '顶置总结消息',
        'values': {
            True: '是',
            False: '否'
        },
        'toggle_action': 'toggle_top_summary',
        'toggle_func': lambda current: not current
    },
    'summary_now': {
        'display_name': '立即执行总结',
        'toggle_action': 'summary_now',
        'toggle_func': None
    }

}

MEDIA_SETTINGS = {
    'enable_media_type_filter': {
        'display_name': '媒体类型过滤',
        'values': {
            True: '开启',
            False: '关闭'
        },
        'toggle_action': 'toggle_enable_media_type_filter',
        'toggle_func': lambda current: not current
    },
    'selected_media_types': {
        'display_name': '选择的媒体类型',
        'toggle_action': 'set_media_types',
        'toggle_func': None
    },
    'enable_media_size_filter': {
        'display_name': '媒体大小过滤',
        'values': {
            True: '开启',
            False: '关闭'
        },
        'toggle_action': 'toggle_enable_media_size_filter',
        'toggle_func': lambda current: not current
    },
    'max_media_size': {
        'display_name': '媒体大小限制',
        'values': {
            None: '5MB',
            '': '5MB'
        },
        'toggle_action': 'set_max_media_size',
        'toggle_func': None
    },
    'is_send_over_media_size_message': {
        'display_name': '媒体大小超限时发送提醒',
        'values': {
            True: '开启',
            False: '关闭'
        },
        'toggle_action': 'toggle_send_over_media_size_message',
        'toggle_func': lambda current: not current
    },
    'enable_extension_filter': {
        'display_name': '媒体扩展名过滤',
        'values': {
            True: '开启',
            False: '关闭'
        },
        'toggle_action': 'toggle_enable_media_extension_filter',
        'toggle_func': lambda current: not current
    },
    'extension_filter_mode': {
        'display_name': '媒体扩展名过滤模式',
        'values': {
            AddMode.BLACKLIST: '黑名单',
            AddMode.WHITELIST: '白名单'
        },
        'toggle_action': 'toggle_media_extension_filter_mode',
        'toggle_func': lambda current: AddMode.WHITELIST if current == AddMode.BLACKLIST else AddMode.BLACKLIST
    },
    'media_extensions': {
        'display_name': '设置媒体扩展名',
        'toggle_action': 'set_media_extensions',
        'toggle_func': None,
        'values': {}
    },
    'media_allow_text': {
        'display_name': '放行文本',
        'values': {
            True: '开启',
            False: '关闭'
        },
        'toggle_action': 'toggle_media_allow_text',
        'toggle_func': lambda current: not current
    }
}


OTHER_SETTINGS = {
    'copy_rule': {
        'display_name': '复制规则',
        'toggle_action': 'copy_rule',
        'toggle_func': None
    },
    'copy_keyword': {
        'display_name': '复制关键字',
        'toggle_action': 'copy_keyword',
        'toggle_func': None
    },
    'copy_replace': {
        'display_name': '复制替换',
        'toggle_action': 'copy_replace',
        'toggle_func': None
    },
    'clear_keyword': {
        'display_name': '清空所有关键字',
        'toggle_action': 'clear_keyword',
        'toggle_func': None
    },
    'clear_replace': {
        'display_name': '清空所有替换规则',
        'toggle_action': 'clear_replace',
        'toggle_func': None
    },
    'delete_rule': {
        'display_name': '删除规则',
        'toggle_action': 'delete_rule',
        'toggle_func': None
    },
    'null': {
        'display_name': '-----------',
        'toggle_action': 'null',
        'toggle_func': None
    },
    'set_userinfo_template': {
        'display_name': '设置用户信息模板',
        'toggle_action': 'set_userinfo_template',
        'toggle_func': None
    },
    'set_time_template': {
        'display_name': '设置时间模板',
        'toggle_action': 'set_time_template',
        'toggle_func': None
    },
    'set_original_link_template': {
        'display_name': '设置原始链接模板',
        'toggle_action': 'set_original_link_template',
        'toggle_func': None
    },
    'reverse_blacklist': {
        'display_name': '反转黑名单',
        'toggle_action': 'toggle_reverse_blacklist',
        'toggle_func': None
    },
    'reverse_whitelist': {
        'display_name': '反转白名单',
        'toggle_action': 'toggle_reverse_whitelist',
        'toggle_func': None
    }
}

PUSH_SETTINGS = {
    'enable_push_channel': {
        'display_name': '启用推送',
        'toggle_action': 'toggle_enable_push',
        'toggle_func': None
    },
    'add_push_channel': {
        'display_name': '➕ 添加推送配置',
        'toggle_action': 'add_push_channel',
        'toggle_func': None
    },
    'enable_only_push': {
        'display_name': '只转发到推送配置',
        'toggle_action': 'toggle_enable_only_push',
        'toggle_func': None
    }
}

async def create_settings_text(rule):
    """创建设置信息文本"""
    text = (
        "📋 管理转发规则\n\n"
        f"规则ID: `{rule.id}`\n" 
        f"{rule.source_chat.name} --> {rule.target_chat.name}"
    )
    return text

async def create_buttons(rule):
    """创建规则设置按钮"""
    buttons = []

    # 获取当前聊天的当前选中规则
    session = get_session()
    try:
        target_chat = rule.target_chat
        current_add_id = target_chat.current_add_id
        source_chat = rule.source_chat

        # 添加规则切换按钮
        is_current = current_add_id == source_chat.telegram_chat_id
        buttons.append([
            Button.inline(
                f"{'✅ ' if is_current else ''}应用当前规则",
                f"toggle_current:{rule.id}"
            )
        ])

        buttons.append([
            Button.inline(
                f"是否启用规则: {RULE_SETTINGS['enable_rule']['values'][rule.enable_rule]}",
                f"toggle_enable_rule:{rule.id}"
            )
        ])

        # 当前关键字添加模式
        buttons.append([
            Button.inline(
                f"当前关键字添加模式: {RULE_SETTINGS['add_mode']['values'][rule.add_mode]}",
                f"toggle_add_mode:{rule.id}"
            )
        ])

        # 是否过滤用户信息
        buttons.append([
            Button.inline(
                f"过滤关键字时是否附带发送者名称和ID: {RULE_SETTINGS['is_filter_user_info']['values'][rule.is_filter_user_info]}",
                f"toggle_filter_user_info:{rule.id}"
            )
        ])

        if RSS_ENABLED == 'false':
            # 处理模式
            buttons.append([
                Button.inline(
                    f"⚙️ 处理模式: {RULE_SETTINGS['handle_mode']['values'][rule.handle_mode]}",
                    f"toggle_handle_mode:{rule.id}"
                )
            ])
        else:
            # 处理模式
            buttons.append([
                Button.inline(
                    f"⚙️ 处理模式: {RULE_SETTINGS['handle_mode']['values'][rule.handle_mode]}",
                    f"toggle_handle_mode:{rule.id}"
                ),
                Button.inline(
                    f"⚠️ 只转发到RSS: {RULE_SETTINGS['only_rss']['values'][rule.only_rss]}",
                    f"toggle_only_rss:{rule.id}"
                )
            ])


        buttons.append([
            Button.inline(
                f"📥 过滤模式: {RULE_SETTINGS['forward_mode']['values'][rule.forward_mode]}",
                f"toggle_forward_mode:{rule.id}"
            ),
            Button.inline(
                f"🤖 转发方式: {RULE_SETTINGS['use_bot']['values'][rule.use_bot]}",
                f"toggle_bot:{rule.id}"
            )
        ])


        if rule.use_bot:  # 只在使用机器人时显示这些设置
            buttons.append([
                Button.inline(
                    f"🔄 替换模式: {RULE_SETTINGS['is_replace']['values'][rule.is_replace]}",
                    f"toggle_replace:{rule.id}"
                ),
                Button.inline(
                    f"📝 消息格式: {RULE_SETTINGS['message_mode']['values'][rule.message_mode]}",
                    f"toggle_message_mode:{rule.id}"
                )
            ])

            buttons.append([
                Button.inline(
                    f"👁 预览模式: {RULE_SETTINGS['is_preview']['values'][rule.is_preview]}",
                    f"toggle_preview:{rule.id}"
                ),
                Button.inline(
                    f"🔗 原始链接: {RULE_SETTINGS['is_original_link']['values'][rule.is_original_link]}",
                    f"toggle_original_link:{rule.id}"
                )
            ])

            buttons.append([
                Button.inline(
                    f"👤 原始发送者: {RULE_SETTINGS['is_original_sender']['values'][rule.is_original_sender]}",
                    f"toggle_original_sender:{rule.id}"
                ),
                Button.inline(
                    f"⏰ 发送时间: {RULE_SETTINGS['is_original_time']['values'][rule.is_original_time]}",
                    f"toggle_original_time:{rule.id}"
                )
            ])

            buttons.append([
                Button.inline(
                    f"🗑 删除原消息: {RULE_SETTINGS['is_delete_original']['values'][rule.is_delete_original]}",
                    f"toggle_delete_original:{rule.id}"
                ),
                Button.inline(
                    f"💬 评论区按钮: {RULE_SETTINGS['enable_comment_button']['values'][rule.enable_comment_button]}",
                    f"toggle_enable_comment_button:{rule.id}"
                )

            ])

            # 添加延迟过滤器按钮
            buttons.append([
                Button.inline(
                    f"⏱️ 延迟处理: {RULE_SETTINGS['enable_delay']['values'][rule.enable_delay]}",
                    f"toggle_enable_delay:{rule.id}"
                ),
                Button.inline(
                    f"⌛ 延迟秒数: {rule.delay_seconds or 5}秒",
                    f"set_delay_time:{rule.id}"
                )
            ])



            # 添加同步规则相关按钮
            buttons.append([
                Button.inline(
                    f"🔄 同步规则: {RULE_SETTINGS['enable_sync']['values'][rule.enable_sync]}",
                    f"toggle_enable_sync:{rule.id}"
                ),
                Button.inline(
                    f"📡 同步设置",
                    f"set_sync_rule:{rule.id}"
                )
            ])

            if UFB_ENABLED == 'true':
                buttons.append([
                    Button.inline(
                        f"☁️ UFB同步: {RULE_SETTINGS['is_ufb']['values'][rule.is_ufb]}",
                        f"toggle_ufb:{rule.id}"
                    )
                ])

            
            

            buttons.append([
                Button.inline(
                    "🤖 AI设置",
                    f"ai_settings:{rule.id}"
                ),
                Button.inline(
                    "🎬 媒体设置",
                    f"media_settings:{rule.id}"
                ),
                Button.inline(
                    "➕ 其他设置",
                    f"other_settings:{rule.id}"
                )
            ])

    
            buttons.append([
                Button.inline(
                    "🔔 推送设置",
                    f"push_settings:{rule.id}"
                )
            ])

            buttons.append([
                Button.inline(
                    "👈 返回",
                    "settings"
                ),
                Button.inline(
                    "❌ 关闭",
                    "close_settings"
                )
            ])


    finally:
        session.close()

    return buttons



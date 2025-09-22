# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概述

TelegramForwarder 是一个功能强大的 Telegram 消息自动化处理和转发工具，采用 Python 异步架构，通过 Telethon 库与 Telegram API 交互。主要功能包括消息监听、过滤、处理、转发、AI 处理、RSS 生成和多平台推送。

## 核心架构

### 双客户端架构
- **用户客户端** (`user_client`): 监听频道/群组消息和用户模式转发
- **机器人客户端** (`bot_client`): 处理命令和机器人模式转发
- 通过 `message_listener.py` 进行事件监听和分发

### 过滤器链模式 (Filter Chain Pattern)
消息处理通过责任链模式实现，按顺序执行：
```
InitFilter → DelayFilter → KeywordFilter → ReplaceFilter → MediaFilter → 
AIFilter → InfoFilter → CommentButtonFilter → RSSFilter → EditFilter → 
SenderFilter → ReplyFilter → PushFilter → DeleteOriginalFilter
```

## 常用开发命令

### 本地开发
```bash
# 安装依赖
pip install -r requirements.txt

# 运行主服务（需要先配置 .env 文件）
python main.py

# 运行 RSS 服务（可选）
python rss/main.py
```

### Docker 部署
```bash
# 首次运行（需要验证）
docker-compose run -it telegram-forwarder

# 后台运行
docker-compose up -d

# 更新
docker-compose down && docker-compose pull && docker-compose up -d
```

### 数据库操作
项目使用 SQLite + SQLAlchemy，数据库文件位于 `./db/forward.db`

## 关键模块说明

### 过滤器系统 (`filters/`)
- 每个过滤器继承自 `BaseFilter`
- 通过 `FilterChain` 管理执行顺序
- 支持中断处理链

### AI 服务适配器 (`ai/`)
- 支持多个 AI 服务商：OpenAI、Gemini、Claude、Grok、Deepseek、Qwen
- 统一的 `BaseAIProvider` 接口
- 配置文件：`config/ai_models.json`

### 数据模型 (`models/`)
- `models.py`: 数据库表定义
- `db_operations.py`: 封装所有 CRUD 操作

### 消息处理 (`message_listener.py`)
- 监听用户客户端消息
- 根据规则匹配和分发

### 命令处理 (`handlers/`)
- `bot_handler.py`: 机器人命令分发
- `command_handlers.py`: 具体命令执行
- `state_manager.py`: 多步交互状态管理

## 配置文件

### 环境变量 (`.env`)
必需配置：
- `API_ID`, `API_HASH`: Telegram API 凭据
- `BOT_TOKEN`: 机器人 Token
- `PHONE_NUMBER`: 用户手机号
- `USER_ID`: 用户 ID

可选配置：
- AI 服务 API Keys
- RSS 功能开关
- 推送服务配置

### 配置目录 (`config/`)
- `ai_models.json`: AI 模型配置
- `delay_times.txt`: 延迟时间选项
- `media_extensions.txt`: 媒体扩展名列表
- 其他自定义配置文件

## 开发注意事项

### 代码结构
- 保持模块化，单一职责原则
- 新增过滤器需继承 `BaseFilter`
- 使用异步编程模式 (async/await)

### 数据库操作
- 使用 `DBOperations` 类进行数据库操作
- 支持规则同步功能
- 注意事务处理

### 错误处理
- 完善的日志系统 (`utils/log_config.py`)
- 异常捕获和处理
- 用户友好的错误提示

### 测试
- 测试数据库：`db/forward_test.db`
- 测试会话文件：`sessions/test_*.session`

## 特色功能

1. **多 AI 集成**: 支持 6 个 AI 服务商
2. **多平台推送**: 通过 Apprise 支持 100+ 推送服务
3. **RSS 生成**: FastAPI 提供 RSS 服务（端口 9804）
4. **网页抓取**: Playwright 支持网页内容抓取
5. **定时任务**: 内置 APScheduler

## 部署架构

- 基于 `mcr.microsoft.com/playwright/python:v1.54.0` 镜像
- 支持多进程架构（主进程 + RSS 服务进程）
- 数据持久化：挂载卷映射
- 日志轮转：最大 10MB，保留 3 个文件
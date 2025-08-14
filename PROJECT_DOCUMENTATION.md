
# TelegramForwarder 项目文档

## 1. 项目概述

TelegramForwarder 是一个功能强大的、基于 Python 的 Telegram 消息自动化处理和转发工具。它使用 Telethon 库与 Telegram API 进行交互，能够以用户或机器人的身份监听指定频道/群组的消息，并根据用户定义的丰富规则对消息进行过滤、修改、处理，最终转发到目标聊天、推送到多种外部服务或生成 RSS Feed。

### 核心功能

- **多源多目标转发**：支持从多个源聊天转发到多个目标聊天。
- **强大的过滤系统**：基于过滤器链（Filter Chain）模式，消息依次通过关键字、替换、媒体、AI等多个处理单元。
- **灵活的关键字过滤**：支持黑/白名单、正则表达式和多种匹配模式。
- **内容修改与处理**：支持对消息文本进行正则替换和AI处理（如翻译、润色、总结）。
- **多AI服务商支持**：通过适配器模式，集成了 OpenAI、Gemini、Claude 等多种AI模型。
- **定时任务**：内置调度器，可实现定时AI总结、聊天信息更新等功能。
- **多平台推送**：集成了 Apprise 库，可将消息推送到超过100种服务（如 Discord, Slack, Email, Webhooks）。
- **RSS Feed 生成**：内置 FastAPI 服务器，可将处理后的消息转换为 RSS 订阅源。
- **高度可配置**：通过 `.env` 文件和 `config/` 目录下的配置文件进行灵活设置。
- **数据库持久化**：使用 SQLAlchemy 和 SQLite 存储所有规则和配置。

## 2. 架构设计

项目采用模块化的异步架构，主要由以下几个部分组成：

- **主程序 (`main.py`)**: 项目入口，负责初始化两个Telethon客户端（用户和机器人）、数据库、调度器，并启动所有服务。
- **消息监听器 (`message_listener.py`)**: 设置 Telethon 的事件监听器，是所有消息处理的起点。它接收新消息事件，并将其分发给相应的处理器。
- **过滤器链 (`filters/filter_chain.py`, `filters/process.py`)**: 项目的核心处理引擎。当一个新消息需要根据规则进行转发时，它会创建一个消息上下文（`MessageContext`），并让这个上下文对象依次通过一个预定义的过滤器链。每个过滤器负责一项单一功能（如关键字过滤、AI处理等），并可以修改上下文或决定是否中断处理链。
- **处理器 (`handlers/`)**:
    - **命令处理器 (`command_handlers.py`)**: 解析和处理用户通过机器人发送的命令（如 `/bind`, `/settings`）。
    - **回调处理器 (`button/callback/`)**: 处理用户点击内联按钮的交互。
    - **状态管理器 (`managers/state_manager.py`)**: 管理用户的会话状态，用于处理需要多步输入的命令（如设置提示词）。
- **数据模型 (`models/`)**: 使用 SQLAlchemy 定义了所有的数据表结构（如`ForwardRule`, `Keyword`, `Chat`等），并负责与 SQLite 数据库进行交互。
- **AI服务 (`ai/`)**: 采用适配器模式，为不同的AI提供商（OpenAI, Gemini, Claude等）提供了统一的接口（`BaseAIProvider`），使得可以轻松切换和扩展AI模型。
- **调度器 (`scheduler/`)**: 基于 `asyncio` 实现，用于处理定时任务。目前包含：
    - **AI总结调度器 (`summary_scheduler.py`)**: 根据用户设定的时间，定时拉取消息并进行AI总结。
    - **聊天信息更新器 (`chat_updater.py`)**: 定时更新数据库中存储的聊天名称等信息。
- **RSS服务 (`rss/`)**: 一个内嵌的 FastAPI Web 应用，负责生成和提供 RSS Feed。它有自己的路由、数据读写（CRUD）和模板。

## 3. 核心流程

### 3.1. 启动流程

1.  `main.py` 作为入口点被执行。
2.  加载 `.env` 环境变量。
3.  初始化日志配置 (`utils/log_config.py`)。
4.  初始化数据库 (`models/models.py`)，包括创建表和执行数据迁移。
5.  创建并启动两个 `TelethonClient` 实例：`user_client`（用于监听和以用户身份操作）和 `bot_client`（用于命令交互和以机器人身份操作）。
6.  `setup_listeners` (`message_listener.py`) 被调用，为两个客户端注册 `NewMessage` 事件的监听器。
7.  注册所有机器人命令 (`/start`, `/help` 等)。
8.  创建并启动 `SummaryScheduler` 和 `ChatUpdater` 实例，开始执行定时任务。
9.  如果配置了 `RSS_ENABLED=true`，则在一个新的进程中启动 FastAPI 服务器。
10. 程序进入 `asyncio` 事件循环，等待事件发生。

### 3.2. 消息处理流程

1.  **消息进入**: `user_client` 监听到源频道的新消息，触发 `handle_user_message` (`message_listener.py`)。
2.  **规则查询**: 程序根据消息来源的 `chat_id` 在数据库中查找所有匹配的 `ForwardRule`。
3.  **过滤器链处理**: 对每一个匹配的规则，程序调用 `process_forward_rule` (`filters/process.py`)，创建一个 `FilterChain` 和一个 `MessageContext`。
4.  **上下文传递**: `MessageContext` 对象包含了原始消息、规则配置以及一个用于在过滤器之间传递数据的状态。它会依次被送入以下过滤器：
    - `InitFilter`: 初始化上下文，特别是处理媒体组消息。
    - `DelayFilter`: 如果规则启用，会等待指定秒数后重新获取最新的消息内容，以应对消息被编辑的情况。
    - `KeywordFilter`: 根据规则的黑/白名单和模式（正常、反转）检查消息内容，决定是否继续。
    - `ReplaceFilter`: 对消息内容执行正则表达式替换。
    - `MediaFilter`: 处理媒体文件，如下载、根据类型或大小过滤。
    - `AIFilter`: 如果启用，将消息文本发送给指定的AI模型进行处理，并将结果替换回消息内容。
    - `InfoFilter`: 根据配置，在消息末尾添加原始链接、发送者、时间等信息。
    - `CommentButtonFilter`: 为频道消息添加指向评论区的按钮。
    - `RSSFilter`: 如果启用，将处理后的消息内容和元数据发送到内部的RSS服务。
    - `EditFilter`: 如果处理模式为“编辑”，则直接编辑原始消息（需要相应权限）。
    - `SenderFilter`: 如果处理模式为“转发”，将最终处理好的消息和媒体文件发送到目标聊天。
    - `ReplyFilter`: 为已转发的媒体组消息回复一个带评论区按钮的消息。
    - `PushFilter`: 如果启用，使用 Apprise 将消息推送到外部服务。
    - `DeleteOriginalFilter`: 如果启用，在所有处理完成后删除原始消息。
5.  **流程控制**: 任何一个过滤器都可以通过返回 `False` 来提前中断处理链，阻止后续的过滤器执行和最终的转发。

## 4. 模块详解

### `handlers/`
该模块负责处理所有来自用户的直接交互。

-   **`bot_handler.py`**: 作为命令处理的总入口，根据命令文本分发到 `command_handlers.py` 中的具体函数。
-   **`command_handlers.py`**: 包含了所有斜杠命令（`/`）的具体实现逻辑，如绑定规则、添加关键字、导出配置等。它直接与数据库操作模块交互。
-   **`button/callback/`**: 包含了所有内联按钮回调的处理逻辑。`callback_handlers.py` 是总入口，根据回调数据（如 `settings:123`）分发到具体的回调函数（如 `ai_callback.py`, `media_callback.py` 等）。
-   **`managers/state_manager.py`**: 一个简单的状态机，用于处理需要用户后续输入的场景（例如，发送 `/set_prompt` 后，程序会进入一个等待状态，捕获用户的下一条消息作为新的提示词）。

### `filters/`
这是项目的核心业务逻辑所在，以责任链模式实现。

-   **`filter_chain.py`**: 定义了 `FilterChain` 类，负责按顺序执行注册的过滤器。
-   **`context.py`**: 定义了 `MessageContext` 类，这是一个数据容器，在整个过滤器链中传递，保存着消息的各种状态和内容。
-   **`process.py`**: 定义了默认的过滤器链顺序，将所有过滤器串联起来。
-   **其他 `*_filter.py` 文件**: 每个文件实现一个具体的过滤/处理功能，如上文“消息处理流程”中所述。

### `models/`
定义了应用的数据库模型和操作。

-   **`models.py`**: 使用 SQLAlchemy 的 ORM 定义了所有数据表，如 `Chat`, `ForwardRule`, `Keyword`, `ReplaceRule`, `RSSConfig` 等，并定义了它们之间的关系。同时提供了数据库初始化 (`init_db`) 和会话获取 (`get_session`) 的函数。
-   **`db_operations.py`**: 封装了所有对数据库的增删改查操作（CRUD）。这是一个非常好的实践，将业务逻辑与底层的数据库会话管理解耦。例如，`add_keywords` 函数不仅处理关键字的添加，还处理了规则同步的逻辑。

### `ai/`
实现了对不同AI服务商的统一调用。

-   **`base.py`**: 定义了抽象基类 `BaseAIProvider`，规定了所有AI提供者都必须实现 `process_message` 方法。
-   **`openai_base_provider.py`**: 为所有兼容OpenAI接口的AI服务（如DeepSeek, Qwen）提供了一个通用的基础实现。
-   **`*_provider.py`**: 每个文件是针对特定AI服务商（如OpenAI, Gemini, Claude）的具体实现。
-   **`__init__.py`**: `get_ai_provider` 工厂函数，根据 `config/ai_models.json` 的配置和用户选择的模型名称，动态返回对应的AI提供者实例。

### `scheduler/`
负责所有定时任务。

-   **`summary_scheduler.py`**: 实现了定时总结功能。它会为每个启用了总结的规则创建一个 `asyncio.Task`。任务会计算到下一次执行时间的秒数，`await asyncio.sleep()`，然后执行总结逻辑（获取消息、调用AI、发送结果）。
-   **`chat_updater.py`**: 实现定时更新数据库中存储的聊天名称等元数据。

### `rss/`
一个独立的FastAPI应用，用于生成RSS Feed。

-   **`main.py`**: FastAPI应用的入口。
-   **`routes/`**: 定义了Web路由，如 `/login`, `/rss/dashboard` 等。
-   **`api/endpoints/feed.py`**: 提供了 `/rss/feed/{rule_id}` 等API端点，用于生成和提供RSS XML数据。
-   **`services/feed_generator.py`**: 核心的Feed生成逻辑，使用 `feedgen` 库将从 `entries.json` 文件中读取的数据转换为RSS格式。
-   **`crud/entry.py`**: 负责RSS条目的文件读写操作，每个规则的RSS条目都存储在一个独立的 `entries.json` 文件中。

## 5. 配置说明

-   **`.env`**: 存储所有敏感信息和基本配置。
    -   `API_ID`, `API_HASH`, `BOT_TOKEN`, `PHONE_NUMBER`: Telegram客户端的必要凭证。
    -   `USER_ID`, `ADMINS`: 定义了谁有权使用这个机器人。
    -   `*_API_KEY`, `*_API_BASE`: 各个AI服务商的API凭证和接口地址。
    -   `RSS_ENABLED`, `RSS_BASE_URL`: 控制是否启用RSS功能以及其访问地址。
-   **`config/`**: 存储非敏感的、可由用户自定义的列表类配置。
    -   `ai_models.json`: 定义了AI模型名称与服务商的对应关系。
    -   `summary_times.txt`, `delay_times.txt`, `max_media_size.txt`, `media_extensions.txt`: 为用户在UI上提供了预设的选项。

## 6. 扩展性分析

-   **添加新AI服务商**: 只需在 `ai/` 目录下新建一个 `your_provider.py` 文件，实现一个继承自 `BaseAIProvider` 的新类，然后在 `ai/__init__.py` 的工厂函数中加入对它的实例化逻辑，最后在 `config/ai_models.json` 中添加对应的模型名称即可。
-   **添加新过滤器**: 在 `filters/` 目录下创建一个新的过滤器类，继承自 `BaseFilter` 并实现 `_process` 方法。然后，在 `filters/process.py` 的 `process_forward_rule` 函数中，将新的过滤器实例添加到 `FilterChain` 的适当位置。
-   **添加新命令**: 在 `handlers/command_handlers.py` 中添加一个新的处理函数，然后在 `handlers/bot_handler.py` 的 `command_handlers` 字典中，将命令名称与新的处理函数关联起来。


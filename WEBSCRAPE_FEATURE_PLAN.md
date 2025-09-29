# 网页抓取与 AI 总结功能 - 实施方案 (V2)

本方案旨在为 TelegramForwarder 项目添加一个网页抓取与 AI 总结的新功能。方案根据项目现有架构进行设计，并采纳了关于使用 Playwright 和实现增量总结的核心需求。

---

### 1. 核心思路

功能分解为三个主要部分：**配置**、**执行**和**发送**。

1.  **配置 (User-Facing)**: 用户通过 Telegram 的交互式菜单（类似于现有的 `/settings`）来创建和管理抓取任务。每个任务包含目标 URL、调度时间、AI 模型、Prompt、目标频道等信息。这些配置将持久化存储在数据库中。
2.  **执行 (Backend)**: 一个定时调度器（复用现有的 `scheduler` 模块）会周期性地检查需要执行的任务。一旦触发，它会调用一个新的爬虫服务，抓取指定网页的**增量内容**，然后将内容交给 AI 模块（复用现有的 `ai` 提供商）进行总结。
3.  **发送 (Bot Action)**: AI 完成总结后，机器人将格式化的结果发送到用户指定的频道。

---

### 2. 数据库模型设计 (`models/models.py`)

为了实现增量总结，我们不仅需要存储任务配置，还需要记录**哪些信息已经被处理过**。因此，需要定义两张新表。

#### 表一: `WebScrapeConfig`

存储用户定义的抓取任务。

```python
class WebScrapeConfig(Base):
    __tablename__ = 'web_scrape_configs'

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    task_name = Column(String, nullable=False)
    url_template = Column(String, nullable=False)
    url_params = Column(JSON, nullable=True)
    schedule = Column(String, nullable=False, default='0 */1 * * *') # 默认每小时
    target_channel_id = Column(String, nullable=False)
    ai_provider = Column(String, nullable=True)
    prompt_template = Column(String, nullable=True)
    is_enabled = Column(Boolean, default=True, nullable=False)
    last_run_at = Column(DateTime, nullable=True)

    user = relationship('User')
    processed_posts = relationship('ProcessedPost', back_populates='scrape_config', cascade="all, delete-orphan")

    __table_args__ = (
        UniqueConstraint('user_id', 'task_name', name='unique_user_task_name'),
    )
```

#### 表二: `ProcessedPost`

作为记忆库，记录所有已被抓取和总结过的帖子，防止信息重复处理。

```python
class ProcessedPost(Base):
    __tablename__ = 'processed_posts'

    id = Column(Integer, primary_key=True)
    scrape_config_id = Column(Integer, ForeignKey('web_scrape_configs.id'), nullable=False)
    post_unique_id = Column(String, nullable=False, index=True)
    processed_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    scrape_config = relationship('WebScrapeConfig', back_populates='processed_posts')

    __table_args__ = (
        UniqueConstraint('scrape_config_id', 'post_unique_id', name='unique_config_post'),
    )
```

---

### 3. 用户交互与配置 (`handlers/`)

复用现有的基于内联按钮的设置菜单框架，确保体验一致。

1.  **入口命令**: 在 `handlers/command_handlers.py` 中新增 `/webscrape` 命令作为功能入口。
2.  **管理面板**: 展示用户所有已创建的抓取任务，并提供 "➕ 添加新任务" 按钮。
3.  **配置流程**: 通过点击任务或按钮，进入详细配置界面，通过与机器人对话的方式设置 URL、定时、频道、AI 等参数。所有更改实时更新到数据库。

---

### 4. 爬虫模块实现 (`crawler/`)

基于用户提供的 `scrape_coinmarketcap.py` 示例，使用 Playwright 构建。

1.  **创建新文件**: `crawler/web_scraper.py`。
2.  **核心函数**: `async def scrape_posts(url: str) -> List[Dict[str, str]]`
    *   使用 Playwright 导航到 `url` 并获取动态渲染后的 HTML。
    *   定位页面上所有独立的帖子元素。
    *   对每个帖子，提取其**内容** (`content`) 和**唯一标识符** (`unique_id`)。唯一标识符优先使用帖子URL或 `data-post-id` 等属性，若无则计算内容哈希值。
    *   返回一个字典列表，如 `[{'unique_id': 'post_123', 'content': '...'}, ...]`。

---

### 5. 调度器集成 (`scheduler/`)

扩展现有调度器模块，实现任务的自动化执行。

1.  **任务加载**: 机器人启动时，从数据库加载所有启用的 `WebScrapeConfig` 任务。
2.  **动态调度**: 使用 `apscheduler`，根据每个任务的 Cron 表达式 (`schedule` 字段) 添加、更新或移除定时作业。

---

### 6. 任务执行逻辑

由调度器在指定时间触发的核心工作单元。

1.  **执行函数**: `async def execute_scrape_and_summarize(task_id: int)`
2.  **抓取**: 调用 `crawler.web_scraper.scrape_posts()` 获取当前页面的所有帖子。
3.  **查询记忆**: 从 `ProcessedPost` 表中，获取该任务所有**已处理过**的 `post_unique_id`。
4.  **筛选增量**: 对比步骤2和3的结果，筛选出“新帖子”。
5.  **判断与执行**:
    *   若无新帖子，则记录日志并结束。
    *   若有新帖子，将其内容拼接成一个长文本。
6.  **AI 总结**: 调用相应的 AI 服务对长文本进行总结。
7.  **发送结果**: 将总结发送到指定频道。
8.  **更新记忆**: **成功发送后**，将新帖子的 `unique_id` 写入 `ProcessedPost` 表，防止下次重复处理。

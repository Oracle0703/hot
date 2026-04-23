# 热点信息采集系统规格说明（spec.md）

## 1. 项目概述

| 项目 | 内容 |
| --- | --- |
| 项目名称 | 热点信息采集系统 |
| 目标用户 | 运营团队、内容编辑、内部管理员 |
| 核心问题 | 运营每天早上需要手工打开多个网页、筛选游戏相关帖子、汇总热点并整理成文档，耗时约 30 分钟，过程重复且易漏项 |
| 当前目标 | 将热点采集、筛选、进度查看、结果汇总和文档导出整合为一个通用化内部系统，支持每天自动或手动执行 |
| 成功标准 | 运营连续 5 个工作日可依赖该系统完成晨间热点收集，人工整理时间压缩到 5 分钟以内 |

## 2. 约束与决策

| 类别 | 决策 |
| --- | --- |
| 部署形态 | 不使用 Docker，直接部署在可访问目标网站的机器上 |
| 数据库策略 | 开发默认 SQLite；生产推荐 MySQL |
| 技术栈 | Python 单语言栈，FastAPI + SQLAlchemy + Playwright |
| 页面模式 | 服务端 HTML + 轻量 JS 轮询，降低复杂度 |
| 调度方式 | 应用内轻量后台轮询器，按天创建 `scheduled` 任务 |
| 文档格式 | 生成 Markdown 和 DOCX |
| 登录策略 | 允许复用人工登录后的浏览器会话，不做验证码破解 |
| 合规边界 | 仅采集公司明确允许访问的页面，不实现代理池、批量账号、反爬绕过 |

## 3. 业务目标

| 一级目标 | 说明 |
| --- | --- |
| 采集源可配置 | 通过 URL、抓取模式、选择器、关键词等配置支持不同站点 |
| 执行过程可追踪 | 能看到任务状态、来源进度、成功失败和错误日志 |
| 输出结果可复用 | 自动生成标准化报告并支持历史追溯 |
| 方案通用性强 | 优先用通用规则支持新站点，必要时才加站点插件 |

## 4. 功能范围

| 范围 | 内容 |
| --- | --- |
| MVP 已覆盖 | 采集源 CRUD、手动执行、定时执行、HTTP/Playwright 双模式、进度页、任务日志、Markdown/DOCX 报告、历史报告页 |
| 下一阶段 | 来源校验试抓、采集源编辑增强、失败重试、登录态管理、真实站点模板 |
| 暂不实现 | AI 摘要、多租户权限、办公工具推送、复杂分布式爬虫 |

## 5. 推荐架构

| 层级 | 模块 | 职责 |
| --- | --- | --- |
| 展示层 | 页面路由 | 首页、采集源、任务详情、报告、调度页 |
| 接口层 | JSON API | 采集源 CRUD、任务查询、报告下载 |
| 服务层 | `SourceService` / `JobService` / `ReportService` / `SchedulerService` | 业务编排与状态管理 |
| 执行层 | `JobDispatcher` / `JobRunner` / `SchedulerLoop` | 后台调度、任务消费与进度更新 |
| 采集层 | `HttpCollector` / `PlaywrightCollector` | 获取页面内容 |
| 解析层 | `GenericCssParser` + 可扩展站点插件 | 将 HTML/DOM 提取为统一帖子模型 |
| 存储层 | SQLite/MySQL + 报告文件目录 | 保存配置、任务、日志、结果、报告 |

## 6. 核心数据模型

### 6.1 采集源 `sources`

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `id` | UUID | 主键 |
| `name` | string | 采集源名称 |
| `site_name` | string | 站点名称 |
| `entry_url` | string | 列表页或入口 URL |
| `fetch_mode` | enum | `http` / `playwright` |
| `parser_type` | enum | `generic_css` / `site_plugin` |
| `list_selector` | string | 列表选择器 |
| `title_selector` | string | 标题选择器 |
| `link_selector` | string | 链接选择器 |
| `meta_selector` | string | 时间/作者/热度选择器 |
| `include_keywords` | list[string] | 包含关键词 |
| `exclude_keywords` | list[string] | 排除关键词 |
| `max_items` | int | 最大抓取条数 |
| `enabled` | bool | 是否启用 |

### 6.2 任务 `collection_jobs`

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `id` | UUID | 任务 ID |
| `trigger_type` | enum | `manual` / `scheduled` |
| `status` | enum | `pending` / `running` / `success` / `partial_success` / `failed` |
| `total_sources` | int | 总采集源数 |
| `completed_sources` | int | 已完成来源数 |
| `success_sources` | int | 成功来源数 |
| `failed_sources` | int | 失败来源数 |
| `current_source` | string | 当前执行来源 |
| `started_at` | datetime | 开始时间 |
| `finished_at` | datetime | 结束时间 |

### 6.3 调度配置 `scheduler_settings`

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `id` | int | 固定为 `1` 的单例配置 |
| `enabled` | bool | 是否启用定时调度 |
| `daily_time` | string | 每日触发时间，格式 `HH:MM` |
| `last_triggered_on` | date | 最近一次成功创建任务的日期 |

### 6.4 采集结果 `collected_items`

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `id` | UUID | 主键 |
| `job_id` | UUID | 所属任务 |
| `source_id` | UUID | 来源采集源 |
| `title` | string | 帖子标题 |
| `url` | string | 原始链接 |
| `published_at` | datetime | 发布时间 |
| `heat_score` | string | 热度值 |
| `excerpt` | text | 摘要 |
| `raw_payload` | json | 原始解析结果 |
| `normalized_hash` | string | 用于去重的归一化哈希 |

### 6.5 报告 `reports`

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `id` | UUID | 报告 ID |
| `job_id` | UUID | 对应任务 |
| `markdown_path` | string | Markdown 文件路径 |
| `docx_path` | string | DOCX 文件路径 |
| `created_at` | datetime | 生成时间 |

## 7. 关键流程

### 7.1 手动执行流程

| 步骤 | 行为 |
| --- | --- |
| 1 | 运营在首页点击“立即采集” |
| 2 | 系统创建一条 `manual` 任务 |
| 3 | `JobDispatcher` 异步消费待执行任务 |
| 4 | `JobRunner` 逐个执行启用的采集源 |
| 5 | 页面通过 `/jobs/{id}/progress` 和 `/jobs/{id}/logs/view` 轮询显示状态 |
| 6 | 任务完成后自动生成 Markdown / DOCX 报告 |

### 7.2 定时执行流程

| 步骤 | 行为 |
| --- | --- |
| 1 | `SchedulerLoop` 定期调用 `SchedulerService.run_due_jobs(now)` |
| 2 | 若已到 `daily_time` 且当日尚未触发，则创建一条 `scheduled` 任务 |
| 3 | 调度器调用 `JobDispatcher.dispatch_pending_jobs()` 触发后台执行 |
| 4 | 后续执行、进度、报告链路与手动任务完全一致 |

### 7.3 新来源接入流程

| 步骤 | 行为 |
| --- | --- |
| 1 | 在 `/sources/new` 填写名称、URL、抓取模式、选择器、关键词 |
| 2 | 保存后进入 `/sources` 确认来源已启用 |
| 3 | 执行一次手动任务验证抓取结果 |
| 4 | 如通用规则不足，再补站点专用 parser |

## 8. API 与页面

| 类型 | 路径 | 用途 |
| --- | --- | --- |
| 页面 | `/` | 首页工作台 |
| 页面 | `/sources` | 采集源列表 |
| 页面 | `/sources/new` | 新增采集源 |
| 页面 | `/jobs/{job_id}` | 任务详情 |
| 页面 | `/reports` | 报告列表 |
| 页面 | `/reports/{report_id}` | 报告详情 |
| 页面 | `/scheduler` | 定时调度配置 |
| API | `GET /api/sources` | 采集源列表 |
| API | `POST /api/sources` | 新增采集源 |
| API | `PUT /api/sources/{source_id}` | 更新采集源 |
| API | `DELETE /api/sources/{source_id}` | 删除采集源 |
| API | `POST /api/jobs` | 创建手动任务 |
| API | `GET /api/jobs/{job_id}` | 查询任务详情 |
| API | `GET /api/jobs/{job_id}/logs` | 查询任务日志 |
| API | `GET /api/reports/{report_id}/download` | 下载 Markdown / DOCX |

## 9. 采集策略

| 维度 | 设计 |
| --- | --- |
| 模式选择 | 优先 HTTP；站点依赖 JS 或登录态时切换 Playwright |
| 解析方式 | 默认通用 CSS Selector；特殊站点扩展站点插件 |
| 过滤方式 | 站点结构提取后，再按 include/exclude 关键词过滤 |
| 去重策略 | 以 `normalized_hash` 为主，优先按 URL 标准化去重 |
| 执行策略 | 当前默认串行，优先稳定和可观察性 |
| 报告策略 | 任务完成后自动落盘并挂到任务详情与报告列表 |

## 10. 非功能要求

| 类别 | 要求 |
| --- | --- |
| 可用性 | 20 个以内采集源时可稳定完成日常任务 |
| 可维护性 | 新站点优先通过配置接入，不要求每站都写定制代码 |
| 可扩展性 | 数据库、采集器、报告输出都可独立扩展 |
| 可排障性 | 任一来源失败时能通过任务日志快速定位 |
| 部署成本 | 单机即可运行，默认 SQLite 免安装 |

## 11. 风险与对策

| 风险 | 对策 |
| --- | --- |
| 目标站点结构变动 | 使用通用规则 + fixture 测试，必要时加站点插件 |
| JS 站点抓取不稳定 | 提供 Playwright 模式并暴露超时与等待配置 |
| 登录态失效 | 后续补充受控目录存储和失效提示 |
| 报告格式后续扩张 | 先保持结构化输出，为 AI 摘要和推送预留空间 |
| 测试环境依赖不全 | 表单改为手动解析，不依赖 `python-multipart` |

## 12. 验收标准

| 编号 | 验收项 | 通过标准 |
| --- | --- | --- |
| AC-01 | 采集源管理 | 可新增、查看、更新、删除采集源 |
| AC-02 | 双模式采集 | 至少支持 HTTP 和 Playwright 两类来源 |
| AC-03 | 手动执行 | 首页可一键创建任务并看到进度变化 |
| AC-04 | 定时执行 | 配置后每天到点自动创建并执行任务 |
| AC-05 | 报告生成 | 任务完成后可下载 Markdown 和 DOCX |
| AC-06 | 历史追溯 | 可查看历史报告和任务日志 |
| AC-07 | 数据库切换 | 本地默认 SQLite，生产可切 MySQL |

## 13. 当前基线

| 项目 | 结果 |
| --- | --- |
| 代码状态 | 主链路已可运行 |
| 调度能力 | 已打通最小闭环 |
| 测试状态 | `46 passed` |
| 开发入口 | 参考 `README.md` |
| 后续任务 | 参考 `plan.md` |

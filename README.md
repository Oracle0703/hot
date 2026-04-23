# 热点信息采集系统

内部使用的热点信息采集工具，目标是把“配置采集源 -> 执行采集任务 -> 查看进度 -> 生成报告”打通，并支持每天定时自动执行。

## 快速开始

| 步骤 | 命令/操作 | 说明 |
| --- | --- | --- |
| 1 | `.\scripts\bootstrap.ps1` | 创建虚拟环境、安装依赖并初始化运行目录 |
| 2 | 复制 `.env.example` 或编辑 `data\app.env` | 配置数据库、Cookie、钉钉通知等本地运行参数 |
| 3 | `.\scripts\run.ps1` | 启动开发服务，默认访问 `http://127.0.0.1:8000/` |
| 4 | 页面内配置采集源并执行任务 | 在首页、采集源页、调度页和报告页完成日常操作 |

如需生成给运营同学使用的完整离线包，可直接执行：

```powershell
.\scripts\build_offline_release.ps1
```

生成结果位于 `release\HotCollector-Offline-时间戳\` 和对应 `.zip` 压缩包。

## 当前实现状态

| 模块 | 状态 | 说明 |
| --- | --- | --- |
| Web 页面 | 已完成 | 首页、采集源管理、任务详情、报告列表/详情、定时调度页可用 |
| 采集源 CRUD | 已完成 | 支持 API 和表单两种入口 |
| 采集执行 | 已完成 | 支持手动触发和后台异步执行 |
| 调度能力 | 已完成 | 内置轻量轮询器，每天按配置时间创建 `scheduled` 任务 |
| 报告生成 | 已完成 | 自动生成 Markdown 和 DOCX 两种格式 |
| 数据库 | 已完成 | 默认 SQLite，本地免安装；可切换 MySQL |
| 启动器 | 已完成 | 已提供 `launcher.py`、PyInstaller spec、发布组装脚本 |
| 启动脚本 | 已完成 | 已提供 `bootstrap.ps1`、`run.ps1`、`build_package.ps1`、`prepare_release.ps1` |
| 测试覆盖 | 已完成 | 单元、集成、脚本 dry-run 回归已覆盖 |

## 技术选型

| 维度 | 当前方案 |
| --- | --- |
| Web 框架 | FastAPI |
| ORM | SQLAlchemy 2.x |
| 默认数据库 | SQLite |
| 生产数据库 | MySQL (`pymysql`) |
| HTTP 采集 | `httpx` |
| HTML 解析 | `beautifulsoup4` |
| 浏览器采集 | Playwright |
| 报告导出 | `python-docx` |
| 调度方式 | 应用内后台线程轮询，不依赖 Docker |
| 打包方式 | PyInstaller `onedir` 目录包 |

## 目录说明

| 路径 | 说明 |
| --- | --- |
| `app/main.py` | 应用入口与生命周期装配 |
| `app/runtime_paths.py` | 打包/源码运行时路径识别 |
| `launcher.py` | 启动器入口，负责启动服务并自动打开浏览器 |
| `app/api/` | 页面与 API 路由 |
| `app/models/` | 数据模型 |
| `app/services/` | 采集、任务、报告、调度服务 |
| `app/collectors/` | HTTP/Playwright 采集器与解析器 |
| `app/workers/` | 任务执行器 |
| `scripts/bootstrap.ps1` | 初始化虚拟环境、依赖和目录 |
| `scripts/run.ps1` | 启动开发服务 |
| `scripts/build_package.ps1` | 执行 PyInstaller 打包 |
| `scripts/prepare_release.ps1` | 组装最终发布目录 |
| `scripts/build_offline_release.ps1` | 一键生成完整离线发布包和 zip |
| `scripts/prepare_upgrade_release.ps1` | 组装仅包含程序文件的覆盖升级包目录 |
| `scripts/build_upgrade_release.ps1` | 打包生成固定目录覆盖升级用的 zip |
| `hot_collector.spec` | PyInstaller 打包配置 |
| `README-运营版.txt` | 面向运营同学的简版说明 |
| `.gitignore` | 本地环境、运行数据和打包产物忽略规则 |
| `data/.gitkeep` | 保留运行数据目录结构，真实运行数据不提交 |
| `outputs/reports/` | 报告输出目录 |
| `tests/` | 单元与集成测试 |
| `plan.md` | 下一阶段开发计划 |
| `spec.md` | 产品规格与架构说明 |

## 仓库提交与本地数据

本项目会在运行时生成配置、数据库、日志、报告和浏览器登录态。为避免误提交账号信息或大体积产物，仓库只保留源码、脚本、文档和必要占位文件。

| 类型 | 路径 | Git 策略 | 说明 |
| --- | --- | --- | --- |
| 本地配置 | `data/app.env` | 忽略 | 可能包含 Cookie、Token、Webhook、Secret |
| SQLite 数据库 | `data/*.db` | 忽略 | 运行时业务数据，不作为源码提交 |
| 浏览器登录态 | `data/bilibili-user-data/`、`data/bilibili-storage-state.json` | 忽略 | 包含站点登录状态和缓存 |
| 日志/报告 | `logs/`、`outputs/` | 忽略 | 每次运行自动生成 |
| 打包产物 | `build/`、`dist/`、`release/`、`.pyinstaller/` | 忽略 | 可通过脚本重新生成 |
| 运行目录占位 | `data/.gitkeep` | 提交 | 仅用于保留目录结构 |
| 配置模板 | `.env.example` | 提交 | 只放无敏感信息的示例配置 |

如需共享示例数据，建议放到 `tests/fixtures/`、`docs/` 或单独的 `samples/` 目录，不要直接放进 `data/`。

## 开发运行

### 1. 初始化环境

```powershell
.\scripts\bootstrap.ps1
```

如需同时安装 Playwright 浏览器：

```powershell
.\scripts\bootstrap.ps1 -InstallPlaywright
```

脚本行为：

| 项目 | 说明 |
| --- | --- |
| Python 选择 | 优先使用仓库内 `.venv\Scripts\python.exe`，不存在时回退系统 Python |
| 依赖安装 | 执行 `pip install -r requirements.txt` |
| 浏览器安装 | 仅在传入 `-InstallPlaywright` 时执行 `playwright install chromium` |
| 目录初始化 | 自动确认 `data/` 和 `outputs/reports/` 存在 |
| 调试模式 | 支持 `-DryRun` 仅打印命令，不真正执行 |

### 2. 配置数据库

| 场景 | 配置 |
| --- | --- |
| 本地默认 | 不配置 `DATABASE_URL`，自动使用 `sqlite:///./data/hot_topics.db` |
| 使用 MySQL | 设置 `DATABASE_URL=mysql+pymysql://user:password@127.0.0.1:3306/hot_topic` |

### 3. 可选环境变量

| 变量 | 默认值 | 说明 |
| --- | --- | --- |
| `APP_NAME` | `热点信息采集系统` | 页面标题和应用名 |
| `APP_ENV` | `development` | 环境标识 |
| `APP_DEBUG` | `true` | 是否开启调试 |
| `DATABASE_URL` | `sqlite:///./data/hot_topics.db` | 数据库连接串 |
| `REPORTS_ROOT` | `outputs/reports` | 报告输出目录 |
| `ENABLE_SCHEDULER` | `true` | 是否启用后台定时轮询 |
| `SCHEDULER_POLL_SECONDS` | `30` | 调度轮询间隔，单位秒 |
| `ENABLE_DINGTALK_NOTIFIER` | `false` | 是否启用钉钉 Webhook 摘要通知 |
| `DINGTALK_WEBHOOK` | 空 | 钉钉群自定义机器人 Webhook 地址 |
| `DINGTALK_SECRET` | 空 | 机器人加签 Secret，未启用加签可留空 |
| `DINGTALK_KEYWORD` | 空 | 机器人关键词校验内容，配置后会自动写入消息标题和正文 |
| `BILIBILI_COOKIE` | 空 | B站个人主页视频采集 `bilibili_profile_videos_recent` 必填，填写浏览器导出的完整 Cookie 字符串 |
| `X_AUTH_TOKEN` | 空 | X/Twitter 个人主页采集所需 Cookie 值 |
| `X_CT0` | 空 | X/Twitter 个人主页采集所需 Cookie 值 |
| `REPORT_SHARE_DIR` | 空 | 报告复制脚本的默认共享目录 |
| `ENABLE_SITE_PROXY_RULES` | `false` | 是否启用站点代理规则 |
| `OUTBOUND_PROXY_URL` | 空 | 出站代理地址，例如 `http://127.0.0.1:7890` |
| `OUTBOUND_PROXY_BYPASS_DOMAINS` | `bilibili.com,hdslb.com,bilivideo.com` | 不走代理的域名列表 |
| `SOURCE_FETCH_INTERVAL_SECONDS` | `0` | 不同采集源之间的基础等待秒数 |
| `BILIBILI_SOURCE_INTERVAL_SECONDS` | `0` | B站采集源额外等待秒数 |
| `BILIBILI_RETRY_DELAY_SECONDS` | `5` | B站页面/API 重试等待秒数 |

可复制 `.env.example` 为本地环境变量模板。

推荐把长期运行配置写入 `data/app.env`。`launcher.py`、`scripts/run.ps1` 和 `scripts/send_dingtalk_test_message.py` 都会自动读取这个文件。

配置安全建议：

| 建议 | 说明 |
| --- | --- |
| 不提交 `data/app.env` | 该文件通常包含 Cookie、Token、Webhook 和 Secret |
| 不提交浏览器目录 | `data/bilibili-user-data/` 会保存真实登录态 |
| 示例文件只写空值 | `.env.example` 不应包含任何真实账号或密钥 |
| 优先页面维护 Cookie | B站 Cookie 建议通过系统页面同步，减少手工编辑错误 |

B站个人主页视频采集示例：

```env
BILIBILI_COOKIE=SESSDATA=你的值; bili_jct=你的值; DedeUserID=你的值
```

如果 `bilibili_profile_videos_recent` 未配置或 Cookie 已失效，任务会直接报错，不会再静默返回空结果。

钉钉机器人示例：

```env
ENABLE_DINGTALK_NOTIFIER=true
DINGTALK_WEBHOOK=https://oapi.dingtalk.com/robot/send?access_token=xxxx
DINGTALK_SECRET=
DINGTALK_KEYWORD=热点报告
```

### 3.1 获取钉钉群 `openConversationId`

如需后续接入钉钉应用机器人并向群发送报告，可先用仓库内脚本监听群事件，打印目标群的 `openConversationId`。

安装依赖：

```powershell
python -m pip install -r requirements.txt
```

运行脚本：

```powershell
python .\scripts\dingtalk_print_open_conversation_id.py --client-id "你的ClientId" --client-secret "你的ClientSecret"
```

说明：

| 项目 | 说明 |
| --- | --- |
| 默认事件 | `chat_update_title` |
| 推荐动作 | 启动脚本后，去目标钉钉群修改一次群名称 |
| 成功标志 | 终端打印 `找到 openConversationId: cid...` |
| 依赖 | 需要在钉钉开发者后台为应用开启 `Stream Mode` 和对应群事件订阅 |

### 4. 启动应用

```powershell
.\scripts\run.ps1
```

常用参数：

| 命令 | 说明 |
| --- | --- |
| `.\scripts\run.ps1` | 默认以 `127.0.0.1:8000` 启动，并开启 `--reload` |
| `.\scripts\run.ps1 -BindHost 0.0.0.0 -Port 9000` | 自定义监听地址和端口 |
| `.\scripts\run.ps1 -NoReload` | 关闭自动重载 |
| `.\scripts\run.ps1 -DryRun` | 仅打印启动命令 |

## 面向运营的打包发布

### 0. 一键生成完整离线包

推荐优先使用离线包脚本，它会自动执行 PyInstaller 打包、组装发布目录、补齐运行库并生成 zip。

```powershell
.\scripts\build_offline_release.ps1
```

说明：

| 项目 | 说明 |
| --- | --- |
| 输出目录 | `release\HotCollector-Offline-时间戳\` |
| 输出压缩包 | `release\HotCollector-Offline-时间戳.zip` |
| 包含内容 | 程序文件、启动/停止脚本、默认 `data\app.env`、运行库、浏览器目录、运营说明 |
| 适用场景 | 给一台固定电脑做首次完整部署 |
| Git 状态 | `release/` 已被 `.gitignore` 忽略，生成后无需提交 |

### 1. 打包应用

```powershell
.\scripts\build_package.ps1
```

说明：

| 项目 | 说明 |
| --- | --- |
| 打包输出 | `dist\HotCollectorLauncher\` |
| 打包形态 | `onedir` 目录包，不做单文件 exe |
| 入口程序 | `HotCollectorLauncher.exe` |
| 技术原因 | 对 SQLite、日志、报告目录和 Playwright 路径更稳定 |

### 2. 组装最终发布目录

```powershell
.\scripts\prepare_release.ps1
```

如果本机已经安装过 Playwright 浏览器，也可以一起带入发布目录：

```powershell
.\scripts\prepare_release.ps1 -PlaywrightBrowsersPath "$env:USERPROFILE\AppData\Local\ms-playwright"
```

输出结构：

| 路径 | 用途 |
| --- | --- |
| `release\HotCollector\HotCollectorLauncher.exe` | 启动器主程序 |
| `release\HotCollector\启动系统.bat` | 给运营双击启动 |
| `release\HotCollector\停止系统.bat` | 给运营关闭系统 |
| `release\HotCollector\data\` | SQLite 数据和本地配置 |
| `release\HotCollector\logs\` | 启动日志 |
| `release\HotCollector\outputs\reports\` | 报告输出 |
| `release\HotCollector\playwright-browsers\` | 随包分发的浏览器依赖 |
| `release\HotCollector\README-运营版.txt` | 运营使用说明 |

### 2.1 生成覆盖升级包

如需给运营同学发“固定目录覆盖升级包”，可执行：

```powershell
.\scripts\build_upgrade_release.ps1
```

说明：

| 项目 | 说明 |
| --- | --- |
| 输出目录 | `release\HotCollector-Upgrade-时间戳\` |
| 输出压缩包 | `release\HotCollector-Upgrade-时间戳.zip` |
| 包含内容 | `HotCollectorLauncher.exe`、`_internal\`、启动/停止脚本、运营说明 |
| 不包含内容 | `data\`、`logs\`、`outputs\`、`playwright-browsers\` |
| 适用场景 | 固定安装目录下直接覆盖程序文件，但继续沿用原有配置、数据库和报告 |

### 3. 运营实际使用方式

| 步骤 | 操作 |
| --- | --- |
| 1 | 把 `release\HotCollector\` 整个目录复制到固定电脑 |
| 2 | 双击 `启动系统.bat` 或 `HotCollectorLauncher.exe` |
| 3 | 稍等几秒，浏览器会自动打开 `http://127.0.0.1:38080/` |
| 4 | 在页面里维护采集源、执行任务、下载报告 |
| 5 | 关闭时双击 `停止系统.bat` |

## 使用流程

| 步骤 | 操作 |
| --- | --- |
| 1 | 打开 `/sources/new` 新增采集源，填写名称、URL、抓取模式、选择器和关键词 |
| 2 | 返回 `/sources` 确认采集源已启用 |
| 3 | 在首页 `/` 点击“立即采集”创建手动任务 |
| 4 | 跳转到任务详情页，查看成功数、失败数和日志 |
| 5 | 任务完成后进入 `/reports` 或任务详情页下载 Markdown / DOCX 报告 |
| 6 | 如需每天自动执行，在 `/scheduler` 中启用并配置执行时间 |
| 7 | 如需群通知，配置 `ENABLE_DINGTALK_NOTIFIER=true` 与钉钉 Webhook 相关环境变量，任务完成后会自动发送摘要消息 |

如需先验证钉钉机器人是否可用，可单独发送一条测试消息：

```powershell
python .\scripts\send_dingtalk_test_message.py  # 会自动读取 data\app.env
```

补充说明：

| 场景 | 要求 |
| --- | --- |
| `bilibili_site_search` | 仅支持 `https://www.bilibili.com` 站内搜索页 |
| `bilibili_profile_videos_recent` | 支持 `https://space.bilibili.com/<mid>` 个人主页，且必须配置 `BILIBILI_COOKIE` |

## 调度说明

| 项目 | 说明 |
| --- | --- |
| 配置入口 | `/scheduler` |
| 默认时间 | `08:00` |
| 触发条件 | 当前时间达到 `daily_time` 且当天尚未触发 |
| 去重规则 | 通过 `last_triggered_on` 保证同一天只创建一次任务 |
| 执行方式 | 调度器只负责创建任务，实际采集仍由现有 `JobDispatcher` 异步执行 |

## 报告输出

| 项目 | 说明 |
| --- | --- |
| 存储目录 | `outputs/reports/YYYY-MM-DD/` |
| 文件格式 | `.md`、`.docx` |
| 页面入口 | `/reports`、`/reports/{id}` |
| 下载接口 | `/api/reports/{id}/download?format=md|docx` |

## 测试

运行全量测试：

```powershell
python -m pytest -q
```

脚本/打包专项测试：

```powershell
python -m pytest tests\integration\test_scripts.py -q
```

## 已知边界

| 项目 | 说明 |
| --- | --- |
| 登录态站点 | 当前只支持通过 Playwright 复用已有浏览器会话，不支持验证码破解 |
| 表单处理 | 当前使用手动解析请求体，不依赖 `python-multipart` |
| 页面层 | 当前是服务端 HTML + 轻量 JS 轮询，不是前后端分离架构 |
| 打包策略 | 第一版优先做目录包和固定电脑部署，不追求单文件 exe |
| 多人使用 | 当前更适合固定电脑部署，不是完整的多人协同 SaaS 方案 |

## 下一步建议

| 优先级 | 建议 |
| --- | --- |
| P1 | 增加采集源编辑页、删除确认和校验试抓 |
| P1 | 补充真实站点规则示例和导入脚本 |
| P1 | 增加启动器单实例更强校验和停止脚本回收优化 |
| P2 | 为 Playwright 登录态增加受控目录存储和失效提示 |
| P2 | 增加失败任务重试与报告重生成功能 |
| P3 | 增加 AI 摘要、热点排序和消息推送 |

## 报告快捷操作

打开最新全局报告目录：

```powershell
.\scripts\open_latest_report.ps1
```

直接打开最新 DOCX：

```powershell
.\scripts\open_latest_report.ps1 -OpenDocx
```

复制最新报告到共享目录：

```powershell
.\scripts\copy_latest_report.ps1 -Destination "D:\共享目录\热点报告"
```

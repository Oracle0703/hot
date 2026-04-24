# 开发指南

本文档面向后续维护者，说明如何在本地开发、测试、调试和扩展项目。

## 环境要求

| 项目 | 建议 |
| --- | --- |
| 操作系统 | Windows 优先，发布脚本基于 PowerShell |
| Python | 3.11 或兼容版本 |
| 虚拟环境 | 使用仓库内 `.venv/`，不提交 |
| 浏览器依赖 | Playwright Chromium，按需安装 |
| 数据库 | 默认 SQLite；需要外部数据库时配置 MySQL URL |

## 本地初始化

```powershell
.\scripts\bootstrap.ps1
```

如需安装 Playwright 浏览器：

```powershell
.\scripts\bootstrap.ps1 -InstallPlaywright
```

脚本会创建 `.venv/`、安装 `requirements.txt`，并确认 `data/`、`outputs/reports/` 等运行目录存在。

## 启动开发服务

```powershell
.\scripts\run.ps1
```

| 参数 | 说明 |
| --- | --- |
| `-BindHost 0.0.0.0` | 修改监听地址 |
| `-Port 9000` | 修改端口 |
| `-NoReload` | 关闭热重载 |
| `-DryRun` | 只打印命令，不真正启动 |

默认访问地址是 `http://127.0.0.1:8000/`。

## 配置规则

| 来源 | 优先级 | 说明 |
| --- | --- | --- |
| 进程环境变量 | 高 | 适合临时覆盖 |
| `data/app.env` | 中 | 适合本地长期运行配置 |
| `app/config.py` 默认值 | 低 | 代码内默认兜底 |

维护要求：

| 要求 | 说明 |
| --- | --- |
| 新增配置先改 `.env.example` | 示例值必须为空或安全默认值 |
| 页面写配置统一走服务 | 优先使用 `AppEnvService`，避免多个写入口 |
| 不在日志输出敏感值 | Cookie、Token、Secret、Webhook 需要脱敏 |
| 不提交 `data/app.env` | 该文件已被 `.gitignore` 忽略 |

## 目录职责

| 路径 | 职责 |
| --- | --- |
| `app/api/` | 页面和 API 路由，只做请求解析和响应组装 |
| `app/services/` | 业务流程、配置、调度、报告、通知 |
| `app/services/strategies/` | 站点专用采集策略 |
| `app/collectors/` | 通用 HTTP/Playwright 采集能力 |
| `app/models/` | SQLAlchemy 表模型 |
| `app/schemas/` | 请求/响应或服务层数据结构 |
| `app/workers/` | 后台任务执行流程 |
| `tests/unit/` | 单元测试 |
| `tests/integration/` | 页面/API/脚本级集成测试 |
| `scripts/` | 开发、运行、发布、运维脚本 |
| `docs/` | 长期维护文档与功能设计记录 |

## 新增采集策略

建议流程：

| 步骤 | 动作 |
| --- | --- |
| 1 | 在 `app/services/strategies/` 新增策略模块 |
| 2 | 明确输入来源配置、必需环境变量和输出字段 |
| 3 | 在执行分流处注册策略 |
| 4 | 为正常结果、空结果、配置缺失、站点异常写单元测试 |
| 5 | 如需要登录态，补充 `docs/` 下的运维说明 |

策略实现原则：

| 原则 | 说明 |
| --- | --- |
| 显式失败 | Cookie 缺失、URL 不支持、风控失败应给出可理解错误 |
| 输出统一 | 返回字段尽量与现有报告链路一致 |
| 站点隔离 | 不把站点特殊逻辑散落到通用采集器 |
| 可测试 | HTML 样例放 `tests/fixtures/`，不要放 `data/` |

## 测试

运行全量测试：

```powershell
python -m pytest -q
```

运行脚本相关测试：

```powershell
python -m pytest tests\integration\test_scripts.py -q
```

建议分层验证：

| 改动类型 | 推荐验证 |
| --- | --- |
| 服务层逻辑 | 对应 `tests/unit/` 单测 |
| 页面/API | 对应 `tests/integration/` 测试 |
| 采集策略 | 策略单测 + 必要的 fixture |
| 打包脚本 | `tests/integration/test_scripts.py` + 实际 dry-run |
| 发布脚本 | 本地执行对应 `scripts/build_*.ps1` |

## 提交前检查

| 检查项 | 命令/方式 |
| --- | --- |
| 工作区状态 | `git status --short --ignored` |
| 敏感文件忽略 | `git check-ignore -v data\app.env data\hot_topics.db` |
| 测试 | `python -m pytest -q` |
| 文档链接 | 搜索是否有本机绝对路径 |
| 打包产物 | 确认 `build/`、`dist/`、`release/` 未被提交 |


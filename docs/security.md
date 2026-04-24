# 安全与数据边界

本文档定义项目中敏感数据、运行数据和可提交内容的边界。

## 安全目标

| 目标 | 说明 |
| --- | --- |
| 防止密钥入库 | Cookie、Token、Webhook、Secret 不进入 Git |
| 防止登录态泄露 | 浏览器用户目录和 storage state 不提交、不打入升级包 |
| 控制日志风险 | 日志不打印完整敏感值 |
| 明确数据归属 | 运行数据库、报告、缓存属于部署环境，不属于源码 |
| 支持可恢复 | 升级前可备份配置和数据库 |

## 敏感数据清单

| 数据 | 常见位置 | 风险 | 策略 |
| --- | --- | --- | --- |
| B站 Cookie | `data/app.env`、页面配置 | 可代表用户登录态 | 不提交，必要时脱敏展示 |
| X/Twitter Cookie | `X_AUTH_TOKEN`、`X_CT0` | 可代表用户登录态 | 不提交，不打印 |
| 钉钉 Webhook | `DINGTALK_WEBHOOK` | 可向群发消息 | 不提交，日志脱敏 |
| 钉钉 Secret | `DINGTALK_SECRET` | 可伪造签名请求 | 不提交，不打印 |
| 浏览器状态 | `data/bilibili-user-data/`、`data/bilibili-storage-state.json` | 包含站点登录状态 | 不提交，不放升级包 |
| SQLite 数据库 | `data/hot_topics.db` | 可能包含业务数据和历史任务 | 不提交 |

## Git 忽略边界

| 路径 | 策略 |
| --- | --- |
| `data/*` | 忽略 |
| `data/.gitkeep` | 保留目录占位 |
| `logs/` | 忽略 |
| `outputs/` | 忽略 |
| `build/`、`dist/`、`release/` | 忽略 |
| `.venv/`、`.pyinstaller/` | 忽略 |
| `playwright-browsers/` | 忽略 |
| `packaging/prerequisites/*.exe` | 忽略二进制缓存 |
| `.env.example` | 提交，但只能放安全示例 |

## 配置文件规则

| 文件 | 是否提交 | 要求 |
| --- | --- | --- |
| `.env.example` | 是 | 只放空值或安全默认值 |
| `.env`、`.env.*` | 否 | 本机私有配置 |
| `data/app.env` | 否 | 运行时配置，可能包含真实密钥 |
| `README.md` | 是 | 可说明变量名，不写真实值 |
| `README-运营版.txt` | 是 | 可说明操作步骤，不写真实值 |

## 日志与错误信息

| 场景 | 要求 |
| --- | --- |
| Cookie 缺失 | 可以提示缺少配置名，不输出配置值 |
| Webhook 失败 | 可以输出 HTTP 状态和错误摘要，不输出完整 Webhook |
| 采集失败 | 可以输出站点、来源、错误类型，不输出完整认证头 |
| 调试页面 | 只展示脱敏状态，例如“已配置/未配置” |
| 测试断言 | 测试值使用假值，不复用真实运行配置 |

## 发布包边界

| 包类型 | 是否包含运行数据 |
| --- | --- |
| 完整离线包 | 包含默认空配置和目录结构，不应包含开发机真实 `data/app.env` |
| 覆盖升级包 | 不包含 `data/`、`logs/`、`outputs/`、`playwright-browsers/` |
| Git 仓库 | 只保留 `data/.gitkeep`，不保留真实运行数据 |

## 维护检查命令

提交前检查敏感文件是否被忽略：

```powershell
git check-ignore -v data\app.env data\hot_topics.db data\bilibili-user-data logs outputs build dist release
```

查看被忽略文件：

```powershell
git status --short --ignored
```

搜索常见敏感键：

```powershell
rg -n "SESSDATA|DINGTALK_WEBHOOK|DINGTALK_SECRET|X_AUTH_TOKEN|X_CT0" .
```

如果误提交了敏感值，应立即轮换对应 Cookie/Token/Secret，并清理 Git 历史后再公开仓库。


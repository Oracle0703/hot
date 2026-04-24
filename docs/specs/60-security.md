# 60 安全与合规

状态：草案（阶段 4 落地全部条目）

## 60.1 敏感数据范围

| 类别   | 字段                                       |
| ------ | ------------------------------------------ |
| 凭证   | `BILIBILI_COOKIE`、`X_AUTH_TOKEN`、`X_CT0` |
| 通知   | `DINGTALK_WEBHOOK`、`DINGTALK_SECRET`      |
| 网络   | `OUTBOUND_PROXY_URL`（可能含 user:pass）   |
| 数据库 | MySQL `DATABASE_URL` 中的口令段            |

所有上述字段在 `config/schema.py` 标记 `sensitive=True`。

## 60.2 配置加密（REQ-SEC-001）

| 项   | 行为                                                             |
| ---- | ---------------------------------------------------------------- |
| 触发 | 设置环境变量 `CONFIG_ENCRYPTION_KEY`（Fernet 32 字节 base64）    |
| 文件 | 自动从 `app.env` 迁移到 `app.env.enc`（密文），原文件备份后删除  |
| 内存 | 仅在内存中持明文，禁止落盘                                       |
| 关闭 | 缺少 key 时回退明文，并在 `/system/health/extended` 返回 warning |

密钥保存推荐方式：环境变量（跨机迁移最透明）。备选：同目录 `.key` 文件、Windows DPAPI（仅本机）。

## 60.3 URL 白名单（REQ-SEC-010）

中间件 `app/services/network_access_policy.py` 增强：

- 采集源 `entry_url` 保存与执行前都校验 `scheme in {http, https}`，否则 422 + `URL_SCHEME_NOT_ALLOWED`。
- 出站 httpx / Playwright 客户端在创建时挂载 hook，禁止 `file://`、`gopher://`、`data://`、`ftp://`。

## 60.4 钉钉加签

`dingtalk_webhook_service` 已实现 HMAC-SHA256 + timestamp，本规格作为合规基线锁定。

## 60.5 日志脱敏

| 内容                              | 处理                                                              |
| --------------------------------- | ----------------------------------------------------------------- |
| Cookie / Token / Webhook / Secret | 写日志前正则掩码                                                  |
| 异常堆栈                          | 仅 DEBUG 级别 `logger.exception`；生产仅记录 `reason_code + 摘要` |
| HTTP body                         | 默认不打印，仅在策略启用 `dump_payload=True` 时记录               |

## 60.6 登录态边界

| 路径                               | 内容           | 防护                                              |
| ---------------------------------- | -------------- | ------------------------------------------------- |
| `data/bilibili-user-data/`         | 浏览器 profile | `.gitignore`；过期由 `bilibili_auth_service` 检测 |
| `data/bilibili-storage-state.json` | storage state  | `.gitignore`；可被加密层覆盖                      |

## 60.7 发布完整性（REQ-SEC-020）

| 产物            | 校验                                              |
| --------------- | ------------------------------------------------- |
| `release/*.zip` | 同目录生成 `SHA256SUMS.txt`，由发布脚本输出       |
| 升级包          | 同上                                              |
| 校验命令        | 文档示例：`Get-FileHash -Algorithm SHA256 <file>` |

## 60.8 验证

`TC-SEC-*`。

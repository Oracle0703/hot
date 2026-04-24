# 测试用例总表（docs/test-cases.md）

> 状态截至 阶段 3.4：用例表已按当前实现回对，`pytest -q` = 364 passed / 0 skipped。
> 编号规则：`TC-<域>-<3 位序号>`。新增用例时同时在 `tests/` 下放骨架文件（`@pytest.mark.skip(reason="TC-... 待实现")`）。
> 已实现用例去掉 `skip`，并在 [`../CHANGELOG.md`](../CHANGELOG.md) 记录。
> 状态：`todo` 待实现 / `wip` 实现中 / `done` 已通过。

## 索引

| 域    | 范围                                     | 主测试文件                                                                                                        |
| ----- | ---------------------------------------- | ----------------------------------------------------------------------------------------------------------------- |
| CFG   | 配置 Schema 与 app_env 服务              | `tests/unit/test_config_schema.py` / `tests/unit/test_app_env_service.py`                                         |
| SYS   | 版本、健康、备份、日志轮转、停止脚本     | `tests/unit/test_version_service.py` / `tests/unit/test_log_rotation.py` / `tests/integration/test_system_api.py` |
| STRAT | 策略注册、generic_css、bilibili、dry_run | `tests/unit/test_strategy_registry.py` 等                                                                         |
| DISP  | 重试、取消                               | `tests/unit/test_retry_policy.py` / `tests/unit/test_job_dispatcher_cancel.py`                                    |
| RPT   | 报告并发安全                             | `tests/unit/test_report_concurrency.py`                                                                           |
| SEC   | URL 白名单、配置加密                     | `tests/unit/test_url_whitelist.py` / `tests/unit/test_config_encryption.py`                                       |
| MIG   | Alembic 迁移                             | `tests/unit/test_alembic_migrations.py`                                                                           |
| API   | 系统 API、配置中心、试抓、脚本 -DryRun   | `tests/integration/test_system_api.py` 等                                                                         |
| E2E   | 全链路冒烟                               | `tests/e2e/test_full_smoke.py`                                                                                    |

---

## CFG — 配置 Schema 与 app_env 服务

| 用例       | 场景                           | 输入                                           | 期望                                                   | 状态 |
| ---------- | ------------------------------ | ---------------------------------------------- | ------------------------------------------------------ | ---- |
| TC-CFG-001 | 默认值加载                     | 进程未设置任何相关环境变量                     | `Settings` 各字段返回 schema 默认值                    | done |
| TC-CFG-002 | 环境变量覆盖默认               | `APP_NAME=foo`                                 | `settings.app_name == "foo"`                           | done |
| TC-CFG-003 | app.env 覆盖默认但低于环境变量 | env 文件含 `APP_NAME=bar`，进程 `APP_NAME=foo` | `settings.app_name == "foo"`                           | done |
| TC-CFG-004 | 布尔解析                       | `APP_DEBUG=1/yes/true/on` 与 `0/no/false/off`  | 分别为 True / False                                    | done |
| TC-CFG-005 | 整型解析非法值                 | `SCHEDULER_POLL_SECONDS=abc`                   | 抛 `ValidationError`，提示字段名                       | done |
| TC-CFG-006 | URL 校验                       | `DINGTALK_WEBHOOK=ftp://x`                     | 抛错 `URL_SCHEME_NOT_ALLOWED`                          | done |
| TC-CFG-007 | 时间格式校验                   | `daily_time=25:00`                             | 校验失败提示 `HH:MM`                                   | done |
| TC-CFG-008 | B站 Cookie 必须含 SESSDATA     | `BILIBILI_COOKIE=foo=bar`                      | 校验失败 `COOKIE_MISSING_SESSDATA`                     | done |
| TC-CFG-009 | 敏感字段标记                   | schema 列出全部 sensitive 字段                 | 含 `BILIBILI_COOKIE/X_*/DINGTALK_*/OUTBOUND_PROXY_URL` | done |
| TC-CFG-010 | 字段分组完整                   | schema.groups                                  | 含 8 个分组且每组至少 1 字段                           | done |
| TC-CFG-011 | 默认值掩码                     | 长字段长度 ≥ 8                                 | 返回前 4+`***`+后 4                                    | done |
| TC-CFG-012 | 默认值掩码短字段               | 长字段长度 < 8                                 | 返回 `***`                                             | done |
| TC-CFG-013 | 配置导出 yaml 顺序             | 任意配置                                       | 按 group → field 字典序                                | done |
| TC-CFG-014 | 配置自检：钉钉 mock 通过       | 钉钉 webhook mock 200                          | `dingtalk.ok=True`                                     | done |
| TC-CFG-015 | 配置自检：钉钉 mock 失败       | 钉钉 webhook mock 401                          | `dingtalk.ok=False` 且含 reason                        | done |
| TC-CFG-101 | app_env 读取存在文件           | `data/app.env` 含已保存字段                    | 各分组读取接口返回 env_file 中已持久化的值             | done |
| TC-CFG-102 | app_env 写入加锁               | 并发 2 个 update                               | 无字段丢失                                             | done |
| TC-CFG-103 | app_env 原子替换               | 写过程模拟异常                                 | 主文件保持替换前状态                                   | done |
| TC-CFG-104 | app_env 首次生成占位文件       | 文件不存在                                     | `ensure_env_file()` 生成受管 key 占位内容              | done |
| TC-CFG-105 | export(mask=True) 返回脱敏     | 含 BILIBILI_COOKIE                             | 输出文本不含完整 cookie                                | done |
| TC-CFG-106 | export(mask=False) 仅 DEBUG    | APP_DEBUG=false                                | 返回 403                                               | done |
| TC-CFG-107 | schema 汇总多字段错误          | 多字段同时非法                                 | `ValidationError.errors()` 返回多条字段错误            | done |

## SYS — 版本、健康、备份、日志、停止脚本

| 用例       | 场景                          | 输入                                                      | 期望                                                         | 状态 |
| ---------- | ----------------------------- | --------------------------------------------------------- | ------------------------------------------------------------ | ---- |
| TC-SYS-001 | VERSION 文件存在              | 写入 version=1.0.0 commit=abc1234 built_at=2026-04-23T... | `version_service.get()` 返回对应值                           | done |
| TC-SYS-002 | VERSION 文件缺失回退 git      | 无 VERSION 但仓库有 git                                   | `commit` 不为 unknown                                        | done |
| TC-SYS-003 | VERSION 与 git 都缺失         | 全无                                                      | 返回 `dev-unknown`                                           | done |
| TC-SYS-004 | 启动时间与 uptime 单调递增    | 调用两次间隔 0.5s                                         | 第二次 uptime > 第一次                                       | done |
| TC-SYS-101 | RotatingFileHandler 装配      | 启动 app                                                  | logger 含 RotatingFileHandler 且 maxBytes=10MB backupCount=5 | done |
| TC-SYS-102 | 日志达到阈值轮转              | 写入超过 10MB 内容                                        | 出现 `app.log.1` 文件                                        | done |
| TC-SYS-103 | launcher.log 同样轮转         | 同上                                                      | `launcher.log.1` 出现                                        | done |
| TC-SYS-201 | backup_database -DryRun       | 调用脚本                                                  | 输出预期目标路径，不实际复制                                 | done |
| TC-SYS-202 | backup_database 实际备份      | 含 SQLite 文件                                            | `data/backups/hot_topics-<ts>.db` 出现                       | done |
| TC-SYS-203 | backup_database 保留策略      | 已有 15 份备份                                            | 最旧 1 份被删除，剩 14 份                                    | done |
| TC-SYS-204 | restore_database 校验文件     | `-File` 不存在                                            | 退出码 1 + 错误信息                                          | done |
| TC-SYS-205 | restore_database 实际恢复     | 合法备份 + 服务停                                         | 主库被替换                                                   | done |
| TC-SYS-301 | stop.ps1 删 PID 文件          | PID 文件存在                                              | 调用后 PID 文件消失                                          | done |
| TC-SYS-302 | stop_system.bat 调用 stop.ps1 | bat 调用                                                  | 与 ps1 行为一致                                              | done |

## STRAT — 策略与解析器

| 用例         | 场景                         | 输入                              | 期望                                                    | 状态 |
| ------------ | ---------------------------- | --------------------------------- | ------------------------------------------------------- | ---- |
| TC-STRAT-001 | 注册新策略                   | `@register("echo")` 装饰一个类    | `registry.get("echo")` 返回该实例                       | done |
| TC-STRAT-002 | 重复注册抛错                 | 注册同名两次                      | 抛 `StrategyAlreadyRegistered`                          | done |
| TC-STRAT-003 | 未知策略错误码               | `registry.get("nope")`            | 抛 `StrategyNotFound`                                   | done |
| TC-STRAT-004 | describe 必填                | 任一策略                          | `StrategyMeta.name/display_name/required_fields` 不为空 | done |
| TC-STRAT-005 | StrategyError 含 reason_code | fetch 抛网络错                    | reason_code in 枚举集                                   | done |
| TC-STRAT-006 | cancel_event 中断            | fetch 中 set event                | 抛 `StrategyCancelled`                                  | done |
| TC-STRAT-101 | generic_css 命中列表         | fixture HTML + 选择器             | 返回 ItemDTO 列表                                       | done |
| TC-STRAT-102 | generic_css 选择器未命中     | fixture HTML + 错误选择器         | DryRunResult.diagnostics.list_hits=0 + warning          | done |
| TC-STRAT-103 | generic_css 关键词包含/排除  | include=['热点'] exclude=['广告'] | 仅命中条目保留                                          | done |
| TC-STRAT-104 | generic_css max_items 截断   | max_items=1                       | 最多返回 1 条                                           | done |
| TC-STRAT-105 | generic_css URL 去重         | 同 URL 重复出现                   | 仅保留 1 条                                             | done |
| TC-STRAT-201 | bilibili 策略：登录失效     | 页面要求登录/提示刷新 Cookie      | 抛出可识别异常                                           | done |
| TC-STRAT-202 | bilibili 策略：风控可重试   | 风控/异常跳转                     | 按配置退避并重试 1 次                                    | done |
| TC-STRAT-203 | bilibili 策略：成功路径      | mock OK                           | 返回 ≥1 条 ItemDTO                                      | done |
| TC-STRAT-301 | dry_run 返回 ≤5 条           | 实际可命中 20 条                  | items 长度 ≤ 5                                          | done |
| TC-STRAT-302 | dry_run 含诊断               | 任意                              | diagnostics 含 list_hits/title_hits/filtered_out        | done |

## DISP — 任务分发、重试、取消

| 用例        | 场景                | 输入                          | 期望                                             | 状态 |
| ----------- | ------------------- | ----------------------------- | ------------------------------------------------ | ---- |
| TC-DISP-001 | retry_policy 默认值 | source 未设置                 | max_attempts=1                                   | done |
| TC-DISP-002 | NETWORK 触发重试    | 第 1 次抛 NETWORK 第 2 次成功 | 任务整体成功，attempt=2 记录                     | done |
| TC-DISP-003 | PARSE 不触发重试    | 第 1 次抛 PARSE               | 任务记 1 次失败，无 attempt=2                    | done |
| TC-DISP-004 | 超过 max_attempts   | 全部失败                      | 任务标记 partial_success/failed                  | done |
| TC-DISP-005 | backoff 指数退避    | backoff=1 max_attempts=3      | 实际等待近似 1,2 秒                              | done |
| TC-DISP-101 | 协作式取消          | 运行中设置 cancel_event       | 当前来源结束后任务变 cancelled                   | done |
| TC-DISP-102 | 强制取消            | force=true                    | httpx/playwright 调用立即抛 cancel               | done |
| TC-DISP-103 | 取消接口在无任务时  | 无 running 任务               | 返回 cancelled_job_id=null reason=no_running_job | done |
| TC-DISP-104 | 取消后状态不可逆    | 已 cancelled 再次取消         | 返回 already_cancelled                           | done |

## RPT — 报告并发安全

| 用例       | 场景                 | 输入                | 期望                       | 状态 |
| ---------- | -------------------- | ------------------- | -------------------------- | ---- |
| TC-RPT-001 | 并发写不丢内容       | 两个进程同时 upsert | 最终文件无截断             | done |
| TC-RPT-002 | 写中途异常保留旧文件 | 模拟 IOError        | 主文件未被破坏             | done |
| TC-RPT-003 | 临时文件保留         | 异常路径            | `hot-report.md.tmp.*` 保留 | done |
| TC-RPT-004 | docx 同样原子        | 并发写 docx         | 最终可用 python-docx 打开  | done |

## SEC — 安全

| 用例       | 场景                        | 输入                                | 期望                         | 状态 |
| ---------- | --------------------------- | ----------------------------------- | ---------------------------- | ---- |
| TC-SEC-001 | URL 白名单：file://         | source.entry_url=file:///etc/passwd | 422 + URL_SCHEME_NOT_ALLOWED | done |
| TC-SEC-002 | URL 白名单：gopher          | gopher://x                          | 同上                         | done |
| TC-SEC-003 | URL 白名单：https 通过      | https://example.com                 | 通过                         | done |
| TC-SEC-101 | Fernet 加密往返             | 设 KEY 后写入                       | 文件密文 + 内存明文          | done |
| TC-SEC-102 | 缺少 KEY 回退明文 + warning | 删除 KEY 重启                       | health.issues 含 warning     | done |
| TC-SEC-103 | 非法 KEY 降级明文          | `CONFIG_ENCRYPTION_KEY` 非法        | `status.reason=CONFIG_ENCRYPTION_KEY_INVALID` 且回退明文 | done |
| TC-SEC-201 | SHA256 校验文件生成        | build_offline_release.ps1           | 同目录 `<zip>.sha256` 存在且哈希匹配                    | done |

## MIG — Alembic 迁移

| 用例       | 场景                    | 输入                                    | 期望                                         | 状态 |
| ---------- | ----------------------- | --------------------------------------- | -------------------------------------------- | ---- |
| TC-MIG-001 | upgrade head 在新库     | 空 SQLite                               | alembic_version 表 + 业务表全部存在          | done |
| TC-MIG-002 | upgrade head 在旧库     | 已含 ensure_schema_compatibility 的旧库 | 不丢数据，迁移完成                           | done |
| TC-MIG-003 | downgrade -1 可执行     | 升级后                                  | 表结构回退                                   | done |
| TC-MIG-004 | AUTO_MIGRATE=false 跳过 | 启动                                    | 不执行迁移，但记录 warning                   | done |
| TC-MIG-005 | 迁移前自动备份          | 待执行迁移                              | `data/backups/auto-pre-migrate-<ts>.db` 出现 | done |

## API — HTTP 接口

| 用例       | 场景                                        | 输入                             | 期望                              | 状态 |
| ---------- | ------------------------------------------- | -------------------------------- | --------------------------------- | ---- |
| TC-API-001 | GET /system/info                            | 默认                             | 返回字段齐全且 uptime > 0         | done |
| TC-API-002 | GET /system/health/extended OK              | 全部健康                         | 200 + issues 为空                 | done |
| TC-API-003 | GET /system/health/extended DB 异常         | DB 不可达                        | 503 + reason DATABASE_UNREACHABLE | done |
| TC-API-004 | POST /system/jobs/cancel-running 无任务     | 无 running                       | 200 + cancelled_job_id=null       | done |
| TC-API-005 | POST /system/jobs/cancel-running 有任务     | 模拟 running                     | 200 + cancelled_job_id=<id>       | done |
| TC-API-006 | GET /system/config/export?mask=true         | 默认                             | text/yaml + 不含真实 Cookie       | done |
| TC-API-007 | GET /system/config/export?mask=false 在生产 | APP_DEBUG=false                  | 403                               | done |
| TC-API-101 | 配置中心页面渲染                            | GET /scheduler 或 /config-center | 200 + 含每个 group                | done |
| TC-API-102 | 配置中心保存非法                            | POST 非法字段                    | 422 + 行级错误                    | done |
| TC-API-103 | 配置中心保存合法                            | POST 合法字段                    | 200 + 文件已写                    | done |
| TC-API-201 | dry-run 未保存来源                          | POST /api/sources/dry-run        | 200 + items + diagnostics         | done |
| TC-API-202 | dry-run 已保存来源                          | POST /api/sources/{id}/dry-run   | 同上                              | done |
| TC-API-301 | stop.ps1 -DryRun                            | 调用                             | 输出预期 PID 操作不实际终止       | done |
| TC-API-302 | backup/restore -DryRun                      | 调用                             | 输出路径不实际操作                | done |

## E2E — 端到端冒烟

| 用例       | 场景                                  | 输入             | 期望                             | 状态 |
| ---------- | ------------------------------------- | ---------------- | -------------------------------- | ---- |
| TC-E2E-001 | 首次启动冒烟                          | 空 runtime root  | 启动成功 + DB 创建 + /health=200 | done |
| TC-E2E-002 | 配置 → 试抓 → 任务 → 报告 → 钉钉 mock | mock 钉钉        | 全链路成功，hot-report.md 生成   | done |
| TC-E2E-003 | 升级前后数据保留                      | 升级包覆盖       | 配置/任务/报告全部保留           | done |
| TC-E2E-004 | 取消任务                              | 启动后取消       | 任务 cancelled 无僵尸            | done |
| TC-E2E-005 | 多任务并发收尾                        | 同时完成两个任务 | 全局报告内容完整                 | done |

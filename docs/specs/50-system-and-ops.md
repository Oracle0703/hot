# 50 系统页、备份、版本、日志（运维基座）

状态：已落地（阶段 1，v1）

## 50.1 系统页接口（REQ-SYS-001）

| 路径                          | 方法 | 描述                                                                                            |
| ----------------------------- | ---- | ----------------------------------------------------------------------------------------------- |
| `/system/info`                | GET  | 应用版本、Git commit、构建时间、Python 版本、运行时根、进程启动时间、运行时长                   |
| `/system/health/extended`     | GET  | 数据库可达、调度器存活、最近任务、磁盘剩余、Cookie 有效期估算；任意异常返回 503 + `reason_code` |
| `/system/jobs/cancel-running` | POST | 协作式取消正在运行任务；`{"force": true}` 强制中断                                              |
| `/system/config/export`       | GET  | 导出当前生效配置 yaml；默认 `mask=true` 自动脱敏                                                |

## 50.2 版本信息来源

`app/services/version_service.py`：

| 来源                                                                | 优先级 |
| ------------------------------------------------------------------- | ------ |
| 仓库根 `VERSION` 文件（构建时写入 `version`、`commit`、`built_at`） | 1      |
| `git rev-parse --short HEAD`（开发模式回退）                        | 2      |
| 默认 `dev-unknown`                                                  | 3      |

构建脚本（`scripts/build_package.ps1` 等）在打包前写入 `VERSION`。运行时只读。

## 50.3 日志轮转（REQ-SYS-010）

统一 `logging.handlers.RotatingFileHandler`：

| 文件                 | maxBytes | backupCount |
| -------------------- | -------- | ----------- |
| `logs/launcher.log`  | 10 MB    | 5           |
| `logs/app.log`       | 10 MB    | 5           |
| `logs/scheduler.log` | 10 MB    | 5           |

由 `app/main.py` 启动时统一注册；`launcher.py` 替换原 `FileHandler`。

## 50.4 备份与恢复（REQ-SYS-020）

仓库内脚本：

| 脚本                           | 行为                                                                                                |
| ------------------------------ | --------------------------------------------------------------------------------------------------- |
| `scripts/backup_database.ps1`  | 拷贝 SQLite 到 `data/backups/hot_topics-YYYYMMDD-HHMMSS.db`，保留最近 N 份（默认 14，`-Keep` 可调） |
| `scripts/restore_database.ps1` | `-File <backup>` 校验存在 → 停止服务 → 替换主库 → 提示重启                                          |

升级前自动调用：`scripts/build_upgrade_release.ps1` 在使用方说明中要求"先停 → 先备份 → 再覆盖"。

## 50.5 启停脚本（REQ-SYS-030）

| 脚本                      | 行为                                                                   |
| ------------------------- | ---------------------------------------------------------------------- |
| `scripts/status.ps1`      | 统一调用 `launcher.py --probe` / `HotCollectorLauncher.exe --probe` 探测本地实例状态；`-PrintJson` 透传结构化状态结果 |
| `scripts/stop.ps1`        | 读取 `data/launcher.pid`，并结合本地端口探测判断是否 stale PID；仅在确认实例仍监听时发送 `Stop-Process`，否则只清理 PID 文件；`-PrintJson` 可输出结构化停止结果 |
| `scripts/status_system.bat` | 调用 `status.ps1`，用于批处理或外部壳层接入 |
| `scripts/stop_system.bat` | 调用 `stop.ps1`，无窗口提示                                            |

发布脚本（`prepare_release.ps1`、`build_offline_release.ps1`）会在发布目录生成 `查看状态.bat`、`停止系统.bat` 等用户侧入口，与"启动系统.bat"对齐。

## 50.6 系统状态卡片（REQ-SYS-040）

首页与配置中心展示：

| 卡片     | 字段                                          |
| -------- | --------------------------------------------- |
| 版本     | `version` / `commit` / `built_at`             |
| 调度器   | `alive` / `last_tick_at` / `next_due_at`      |
| 钉钉     | 最近一次发送结果（成功/失败 + 时间）          |
| 关键凭证 | B站 / X Cookie 有效期估算（红色横幅显示失效） |

## 50.7 配置脱敏导出

| 字段                  | 行为                                                |
| --------------------- | --------------------------------------------------- |
| `sensitive=True` 字段 | 默认掩码 `前 4 + *** + 后 4`，长度 < 8 时全部 `***` |
| `mask=false`          | 仅在 DEBUG 模式下允许，且记录审计日志               |

## 50.8 验证

`TC-SYS-*`、`TC-API-001~020`。

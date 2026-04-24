# 90 发布与升级

状态：已落地（zip + 同名 .sha256 + version_service 自检）

## 90.1 发布形态

| 类型       | 脚本                                | 内容                              |
| ---------- | ----------------------------------- | --------------------------------- |
| 完整离线包 | `scripts/build_offline_release.ps1` | 程序 + Python + Playwright 浏览器 |
| 升级包     | `scripts/build_upgrade_release.ps1` | 仅程序文件，覆盖现有目录          |
| 开发包     | `scripts/build_package.ps1`         | PyInstaller onedir                |

## 90.2 版本注入（REQ-SYS-002）

构建脚本在打包前写入仓库根 `VERSION` 文件：

```
version=1.x.y
commit=<git rev-parse --short HEAD>
built_at=2026-04-23T10:22:31+08:00
channel=offline|upgrade|dev
```

`app/services/version_service.py` 在运行时读取。

## 90.3 完整性（REQ-SEC-020）

发布脚本在产出 zip 后生成同名 `<zip>.sha256`(单行)：

```
<sha256>  HotCollector-Offline-20260423-102231.zip
```

升级包同理：`HotCollector-Upgrade-20260423-102231.zip.sha256`。

运维同学覆盖前用 `Get-FileHash -Algorithm SHA256 <file>` 比对。

## 90.4 升级流程

1. 双击 `停止系统.bat`（即 `stop_system.bat`）。
2. 双击 `备份数据库.bat` 或运行 `scripts/backup_database.ps1`。
3. 用升级包覆盖安装目录（不删除 `data/`、`logs/`、`outputs/`、`playwright-browsers/`）。
4. 双击 `启动系统.bat`，启动时自动执行 `alembic upgrade head`。
5. 打开 `/system/info` 确认 `version` 与 `commit` 已更新。

## 90.5 回滚

| 步骤 | 操作                                                      |
| ---- | --------------------------------------------------------- |
| 1    | 停服务                                                    |
| 2    | `scripts/restore_database.ps1 -File data/backups/<ts>.db` |
| 3    | 用上一版升级包覆盖                                        |
| 4    | 启动并核对 `/system/info`                                 |

## 90.6 验证

`TC-SYS-*`、`TC-SEC-020*`。

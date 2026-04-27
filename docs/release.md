# 发布与交付指南

本文档沉淀当前发布流程，区分开发运行、完整离线包和覆盖升级包。

## 发布产物类型

| 类型               | 适用场景               | 脚本                                | 输出                                      |
| ------------------ | ---------------------- | ----------------------------------- | ----------------------------------------- |
| PyInstaller 原始包 | 技术验证               | `scripts/build_package.ps1`         | `dist/HotCollectorLauncher/`              |
| 桌面壳运行目录     | release 组装前准备     | `scripts/build_desktop_shell.ps1`   | `build/HotCollectorDesktopShell/`         |
| 完整离线包         | 首次部署给运营电脑     | `scripts/build_offline_release.ps1` | `release/HotCollector-Offline-时间戳.zip` |
| 固定目录发布       | 本机组装目录           | `scripts/prepare_release.ps1`       | `release/HotCollector/`                   |
| 覆盖升级包         | 已部署机器升级程序文件 | `scripts/build_upgrade_release.ps1` | `release/HotCollector-Upgrade-时间戳.zip` |

## 完整离线包

推荐首次部署时使用：

```powershell
.\scripts\build_offline_release.ps1
```

流程：

| 步骤 | 动作                                      |
| ---- | ----------------------------------------- |
| 0    | 调用 `build_desktop_shell.ps1` 组装 Electron 桌面壳 |
| 1    | 调用 `build_package.ps1` 执行 PyInstaller |
| 2    | 调用 `prepare_release.ps1` 组装发布目录   |
| 3    | 复制 Playwright 浏览器目录                |
| 4    | 准备 VC++ 运行库                          |
| 5    | 使用 `tar.exe` 生成 zip                   |

完整包包含：

| 内容                       | 说明                 |
| -------------------------- | -------------------- |
| `HotCollectorLauncher.exe` | 主启动器             |
| `_internal/`               | PyInstaller 运行依赖 |
| `启动系统.bat`             | 运营双击启动入口     |
| `打开桌面版.bat`           | Electron 桌面壳入口  |
| `查看状态.bat`             | 输出当前实例状态 JSON |
| `停止系统.bat`             | 停止本机运行进程     |
| `desktop-shell/`           | Electron 最小桌面壳运行目录 |
| `安装依赖.bat`             | 安装 VC++ 运行库     |
| `data/app.env`             | 默认运行配置模板     |
| `outputs/reports/`         | 报告输出目录         |
| `outputs/weekly-covers/`   | 周榜封面缓存目录占位 |
| `playwright-browsers/`     | 随包浏览器依赖       |
| `README-运营版.txt`        | 运营说明             |

## 覆盖升级包

已部署过的电脑建议使用升级包：

```powershell
.\scripts\build_upgrade_release.ps1
```

升级包设计原则：

| 原则             | 说明                                  |
| ---------------- | ------------------------------------- |
| 不覆盖运行数据   | 不包含 `data/`、`logs/`、`outputs/`   |
| 不覆盖浏览器状态 | 不包含 `playwright-browsers/`         |
| 只替换程序文件   | 包含 exe、`_internal/`、桌面壳目录和启动/状态/停止脚本 |
| 保留用户配置     | 原有 `data/app.env` 继续沿用          |
| 保留数据库       | 原有 `data/hot_topics.db` 继续沿用    |
| 保留周榜状态     | 原有人工评分、推送记录和封面缓存继续沿用 |

## 周榜相关发布说明

| 项目 | 说明 |
| --- | --- |
| 页面入口 | 发布包启动后可访问 `/weekly`，也可从首页“最近一周热点”进入 |
| 配置项 | 如需批量推送，需要在 `data/app.env` 或配置页维护 `ENABLE_DINGTALK_NOTIFIER`、`DINGTALK_WEBHOOK`、`WEEKLY_GRADE_PUSH_THRESHOLD` |
| 持久化数据 | 人工评分、推送时间、推送批次号存放在 `data/hot_topics.db` |
| 缓存目录 | 封面本地缓存位于 `outputs/weekly-covers/` |
| 升级影响 | 覆盖升级包不包含 `data/` 和 `outputs/`，因此周榜评分、推送状态和封面缓存都会保留 |

## 发布前检查

| 检查项     | 建议                                            |
| ---------- | ----------------------------------------------- |
| 测试       | 执行 `python -m pytest -q`                      |
| 敏感数据   | 确认 `data/app.env`、数据库、浏览器登录态未提交 |
| README     | 确认版本说明、运行方式、配置说明同步            |
| 运营说明   | 确认 `README-运营版.txt` 与实际包结构一致       |
| 周榜链路   | 至少验证 `/weekly` 可访问、可保存评分、可显示推送状态 |
| 打包验证   | 本地执行目标发布脚本                            |
| 压缩包验证 | 解压或列出 zip，确认关键文件存在                |

## 版本

当前已落地的统一版本入口：

| 项目     | 现状                                                                                                              |
| -------- | ----------------------------------------------------------------------------------------------------------------- |
| 版本源   | `app/services/version_service.py` 读取 `app/version.txt`（打包时由 `scripts/prepare_release.ps1` 写入）           |
| 版本规则 | `MAJOR.MINOR.PATCH`，发布时填入构建号                                                                             |
| 发布记录 | `CHANGELOG.md`，按阶段累加                                                                                        |
| Git 标签 | 每次正式发布打 `vX.Y.Z`                                                                                           |
| 包内信息 | 启动后访问 `/system/info` 可见 `version` / `commit` / `built_at`                                                  |
| 完整性   | 发布脚本同时输出同名 `<zip>.sha256`，详见 [docs/specs/90-release-and-upgrade.md](specs/90-release-and-upgrade.md) |

## 回滚建议

| 场景             | 回滚方式                              |
| ---------------- | ------------------------------------- |
| 升级包异常       | 恢复上一个程序目录备份                |
| 数据库异常       | 恢复升级前备份的 `data/hot_topics.db` |
| 配置异常         | 恢复升级前备份的 `data/app.env`       |
| 浏览器登录态异常 | 重新通过系统页面登录并同步            |

正式升级前建议手动备份：

```powershell
Copy-Item data data-backup-$(Get-Date -Format yyyyMMdd-HHmmss) -Recurse
```

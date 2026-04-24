# 发布与交付指南

本文档沉淀当前发布流程，区分开发运行、完整离线包和覆盖升级包。

## 发布产物类型

| 类型 | 适用场景 | 脚本 | 输出 |
| --- | --- | --- | --- |
| PyInstaller 原始包 | 技术验证 | `scripts/build_package.ps1` | `dist/HotCollectorLauncher/` |
| 完整离线包 | 首次部署给运营电脑 | `scripts/build_offline_release.ps1` | `release/HotCollector-Offline-时间戳.zip` |
| 固定目录发布 | 本机组装目录 | `scripts/prepare_release.ps1` | `release/HotCollector/` |
| 覆盖升级包 | 已部署机器升级程序文件 | `scripts/build_upgrade_release.ps1` | `release/HotCollector-Upgrade-时间戳.zip` |

## 完整离线包

推荐首次部署时使用：

```powershell
.\scripts\build_offline_release.ps1
```

流程：

| 步骤 | 动作 |
| --- | --- |
| 1 | 调用 `build_package.ps1` 执行 PyInstaller |
| 2 | 调用 `prepare_release.ps1` 组装发布目录 |
| 3 | 复制 Playwright 浏览器目录 |
| 4 | 准备 VC++ 运行库 |
| 5 | 使用 `tar.exe` 生成 zip |

完整包包含：

| 内容 | 说明 |
| --- | --- |
| `HotCollectorLauncher.exe` | 主启动器 |
| `_internal/` | PyInstaller 运行依赖 |
| `启动系统.bat` | 运营双击启动入口 |
| `停止系统.bat` | 停止本机运行进程 |
| `安装依赖.bat` | 安装 VC++ 运行库 |
| `data/app.env` | 默认运行配置模板 |
| `outputs/reports/` | 报告输出目录 |
| `playwright-browsers/` | 随包浏览器依赖 |
| `README-运营版.txt` | 运营说明 |

## 覆盖升级包

已部署过的电脑建议使用升级包：

```powershell
.\scripts\build_upgrade_release.ps1
```

升级包设计原则：

| 原则 | 说明 |
| --- | --- |
| 不覆盖运行数据 | 不包含 `data/`、`logs/`、`outputs/` |
| 不覆盖浏览器状态 | 不包含 `playwright-browsers/` |
| 只替换程序文件 | 包含 exe、`_internal/`、启动/停止脚本 |
| 保留用户配置 | 原有 `data/app.env` 继续沿用 |
| 保留数据库 | 原有 `data/hot_topics.db` 继续沿用 |

## 发布前检查

| 检查项 | 建议 |
| --- | --- |
| 测试 | 执行 `python -m pytest -q` |
| 敏感数据 | 确认 `data/app.env`、数据库、浏览器登录态未提交 |
| README | 确认版本说明、运行方式、配置说明同步 |
| 运营说明 | 确认 `README-运营版.txt` 与实际包结构一致 |
| 打包验证 | 本地执行目标发布脚本 |
| 压缩包验证 | 解压或列出 zip，确认关键文件存在 |

## 版本建议

当前仓库尚未引入统一版本文件。后续建议补充：

| 项目 | 建议 |
| --- | --- |
| 版本源 | `pyproject.toml` 或 `app/version.py` |
| 版本规则 | 采用 `MAJOR.MINOR.PATCH` |
| 发布记录 | 新增 `CHANGELOG.md` |
| Git 标签 | 每次正式发布打 `vX.Y.Z` |
| 包内信息 | 启动页或日志打印版本号、构建时间、Git commit |

## 回滚建议

| 场景 | 回滚方式 |
| --- | --- |
| 升级包异常 | 恢复上一个程序目录备份 |
| 数据库异常 | 恢复升级前备份的 `data/hot_topics.db` |
| 配置异常 | 恢复升级前备份的 `data/app.env` |
| 浏览器登录态异常 | 重新通过系统页面登录并同步 |

正式升级前建议手动备份：

```powershell
Copy-Item data data-backup-$(Get-Date -Format yyyyMMdd-HHmmss) -Recurse
```


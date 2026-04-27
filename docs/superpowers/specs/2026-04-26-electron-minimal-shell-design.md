# Electron 最小桌面壳设计

## 目标

在不改动 Python Web 主体架构的前提下，新增一个最小 Electron 桌面壳，并把它纳入现有 `release` / 离线包 / 升级包发布链路。

## 范围

| 项目 | 本次是否包含 | 说明 |
| --- | --- | --- |
| 单窗口 Electron 壳体 | 是 | 负责启动本地服务、轮询 manifest、加载 Web UI |
| 纳入 `prepare_release.ps1` | 是 | 发布目录新增 `desktop-shell\` 与 `打开桌面版.bat` |
| 纳入离线包与升级包 | 是 | `build_offline_release.ps1` / `build_upgrade_release.ps1` 自动带上桌面壳 |
| 托盘 / 系统通知 | 否 | 后续独立任务 |
| 多账号体系 | 否 | 后续独立任务 |
| 独立账号态状态页 | 否 | 后续独立任务 |

## 设计

| 模块 | 方案 |
| --- | --- |
| Electron 源码 | 新增 `desktop-shell/electron/`，放置 `package.json`、`main.js` 等最小壳体文件 |
| Electron 运行时构建 | 新增 `scripts/build_desktop_shell.ps1`，负责安装依赖并组装可随 release 分发的桌面壳目录 |
| 发布集成 | `prepare_release.ps1` / `prepare_upgrade_release.ps1` 从桌面壳构建输出目录复制产物，并生成 `打开桌面版.bat` |
| 壳体启动服务 | 壳体优先探测 `HotCollectorLauncher.exe --probe --print-json`；未运行时以 `--no-browser` 启动服务，避免外部浏览器弹出 |
| 壳体加载页面 | 轮询 `GET /system/desktop-manifest`，成功后使用 `service.entry_url` 加载主窗口 |

## 测试策略

| 类别 | 覆盖点 |
| --- | --- |
| 集成测试 | `prepare_release.ps1`、`prepare_upgrade_release.ps1` 会复制桌面壳目录并生成 `打开桌面版.bat` |
| 脚本 dry-run | `build_offline_release.ps1`、`build_upgrade_release.ps1` 会串起 `build_desktop_shell.ps1` |
| 最终验证 | 运行相关 pytest 用例，检查 `git diff --check` |

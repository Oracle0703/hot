# Electron 托盘与系统通知设计

## 目标

在现有 Electron 最小壳体基础上，补齐 Windows 固定电脑场景下最需要的本地体验：托盘常驻、窗口最小化到托盘，以及基于现有系统状态源的系统通知。

## 范围

| 项目 | 本次是否包含 | 说明 |
| --- | --- | --- |
| 托盘常驻图标 | 是 | Electron 主进程新增 `Tray` |
| 托盘菜单 | 是 | 打开主界面、打开账号态页、启动服务、停止服务、查看状态、退出 |
| 关闭窗口最小化到托盘 | 是 | 默认点击关闭按钮不退出 |
| 系统通知 | 是 | 至少覆盖服务启动成功、账号态异常、系统健康异常、恢复正常 |
| 状态轮询 | 是 | 主进程定时读取 `probe`、`/system/auth-state`、`/system/health/extended` |
| 通知去重 | 是 | 仅在状态迁移时通知，不做重复刷屏 |
| 动态彩色托盘图标 | 否 | 首版先用单图标 + tooltip 文案 |
| 任务成功通知 | 否 | 当前没有稳定任务事件流，首版先不接 |
| 开机自启 | 否 | 后续独立功能 |
| 多账号托盘子菜单 | 否 | 当前仍是单用户模型 |

## 当前现状

| 模块 | 现状 |
| --- | --- |
| Electron 壳体 | 已有单窗口 `desktop-shell/electron/main.js`，能启动服务、请求 `desktop-manifest`、加载 Web 主界面 |
| 本地运行状态 | 已有 `HotCollectorLauncher.exe --probe --print-json` 和 `/system/health/extended` |
| 账号态状态源 | 已有 `/system/auth-state` |
| 发布链路 | Electron 壳体已纳入 `release/HotCollector/desktop-shell/` 与 `打开桌面版.bat` |

## 方案选择

| 方案 | 做法 | 优点 | 缺点 | 结论 |
| --- | --- | --- | --- | --- |
| A | 纯轮询：托盘和通知都基于 `probe`、`/system/auth-state`、`/system/health/extended` | 复用现有契约；不改 Python 内核；最稳 | 通知存在轮询延迟 | 推荐 |
| B | 日志驱动：盯进程输出或日志文件生成通知 | 理论上更快 | 脆弱，耦合日志文案 | 不取 |
| C | 混合：运行状态走轮询，任务结果走日志 | 功能更全 | 复杂度明显上升，不适合 V1 | 暂不取 |

## V1 行为设计

### 托盘行为

| 场景 | 行为 |
| --- | --- |
| 首次启动 | 创建主窗口，同时创建托盘 |
| 点击关闭按钮 | 阻止默认退出，改为隐藏窗口到托盘 |
| 双击托盘图标 | 恢复并聚焦主窗口 |
| 右键托盘图标 | 打开托盘菜单 |
| 选择“退出” | 真正退出 Electron；如服务仍在运行，不额外停止 Python 内核 |

### 托盘菜单

| 菜单项 | 动作 |
| --- | --- |
| 打开主界面 | 显示窗口，定位到当前主界面 |
| 打开账号态页 | 显示窗口并跳到 `/auth-state` |
| 启动服务 | 若未运行，则调用当前 `launch` 控制面 |
| 停止服务 | 调用当前 `stop` 控制面 |
| 查看状态 | 主动刷新当前托盘状态 |
| 退出 | 退出 Electron 主进程 |

## 状态源设计

| 状态源 | 用途 |
| --- | --- |
| `probe` | 判断服务是否在运行，决定“启动/停止”菜单与运行态 tooltip |
| `/system/auth-state` | 判断账号态是否 `ok/warning/error/missing` |
| `/system/health/extended` | 判断系统整体健康是否 `ok/error` |
| `desktop-manifest` | 提供 `entry_url`、`control.*` 以及 `/auth-state` 导航入口 |

轮询顺序：

| 步骤 | 动作 |
| --- | --- |
| 1 | 先跑 `probe`，确认服务是否运行 |
| 2 | 若未运行，则只更新托盘 tooltip，不请求 HTTP 接口 |
| 3 | 若运行中，则请求 `desktop-manifest`、`/system/auth-state`、`/system/health/extended` |
| 4 | 计算聚合状态，更新托盘文案与通知 |

## 状态模型

建议在 Electron 主进程内维护一份归一化状态：

| 字段 | 说明 |
| --- | --- |
| `running` | 服务是否运行 |
| `entryUrl` | 当前主界面 URL |
| `authStatus` | 账号态总状态 |
| `healthStatus` | 系统健康状态 |
| `tooltip` | 托盘当前文案 |
| `lastNotificationKey` | 最近一次已发送通知键 |

聚合优先级：

| 条件 | 托盘状态 |
| --- | --- |
| `running=false` | 未运行 |
| `running=true` 且 `healthStatus=error` | 健康异常 |
| `running=true` 且 `authStatus in {warning,error}` | 账号态异常 |
| 其余 | 运行中 |

## 通知规则

| 事件 | 触发条件 | 通知内容方向 |
| --- | --- | --- |
| 服务启动成功 | `running` 从 `false -> true` | 服务已启动，可开始使用 |
| 账号态告警 | `authStatus` 从 `ok/missing -> warning/error` | B站登录态缺失/失效，提示去 `/auth-state` 或 `/scheduler` |
| 系统健康异常 | `healthStatus` 从 `ok -> error` | 系统健康检查失败 |
| 异常恢复 | `authStatus` 或 `healthStatus` 从异常回到 `ok` | 状态已恢复 |

去重规则：

| 规则 | 说明 |
| --- | --- |
| 同一状态不重复弹 | 例如连续轮询 20 次都还是 `auth-warning`，只通知一次 |
| 仅在状态迁移时通知 | 用状态键比较前后差异 |
| 服务停止默认不弹通知 | 避免用户主动关闭服务时被打扰 |

## 文件结构

| 文件 | 责任 |
| --- | --- |
| `desktop-shell/electron/main.js` | 托盘、通知、窗口与轮询主逻辑 |
| `desktop-shell/electron/assets/*` | 托盘图标资源 |
| `tests/integration/test_scripts.py` | 保证桌面壳构建与 release 产物契约不回退 |
| `README.md` / `docs/desktop-shell-integration.md` | 说明托盘/通知行为 |

## 错误处理

| 场景 | 处理 |
| --- | --- |
| 服务未运行 | 托盘显示“未运行”，禁用依赖 HTTP 的跳转动作 |
| `desktop-manifest` 请求失败 | 不阻断托盘存在，保留最后已知 URL |
| `/system/auth-state` 请求失败 | 记为诊断失败，不强制退出 |
| `stop` 失败 | 弹一条错误通知，并保持托盘状态不变 |
| Electron Notification 不可用 | 降级为只更新托盘状态 |

## 测试策略

| 类别 | 覆盖点 |
| --- | --- |
| 主进程单元/脚本测试 | 轮询状态归一化、通知去重、菜单行为分支 |
| 发布集成测试 | `build_desktop_shell.ps1`、`prepare_release.ps1` 仍能正确组装壳体 |
| 回归测试 | `desktop-manifest`、`/system/auth-state`、`probe` 既有契约不回退 |

## 暂不包含

| 项目 | 原因 |
| --- | --- |
| 任务级完成通知 | 当前没有稳定、低耦合的任务事件源 |
| 动态多图标 | 先减少资源与打包复杂度 |
| 开机自启 | 会引入安装器/注册表边界 |
| 多账号子菜单 | 当前单用户模型未扩展 |

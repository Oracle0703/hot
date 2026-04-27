# 账号态状态页设计

## 目标

在当前单用户内核上新增一个独立“账号态状态页”，让运营和桌面壳都能统一读取本地登录态健康快照，而不是继续把账号态信息混在 `/scheduler` 页面里。

## 范围

| 项目 | 本次是否包含 | 说明 |
| --- | --- | --- |
| 独立页面 `/auth-state` | 是 | 作为单用户账号态巡检入口 |
| 系统接口 `GET /system/auth-state` | 是 | 返回统一账号态快照，供 Web 与桌面壳复用 |
| 状态聚合服务 | 是 | 聚合 Cookie、storage state、user-data 目录等本地状态 |
| `desktop-manifest` 导航追加 | 是 | 让桌面壳可直接显示入口 |
| 首版平台范围 | 仅 B 站 | 当前仓库里只有 B 站登录同步链路完整闭环 |
| 多账号 | 否 | 仍保持单用户模型 |
| 托盘 / 通知 | 否 | 后续消费统一状态源时再接 |
| 联网有效性探测 | 否 | 首版只做本地状态可观测，不做带副作用的实时校验 |

## 当前现状

| 能力 | 现状 |
| --- | --- |
| 登录态路径 | `AuthStateService` 已统一产出 `data/<platform>-user-data/` 与 `data/<platform>-storage-state.json` |
| B 站登录同步 | `BilibiliBrowserAuthService` 已支持浏览器登录并把 Cookie 与 storage state 写回本地 |
| 页面入口 | 只有 `/scheduler` 内嵌 B 站 Cookie 配置与浏览器登录按钮 |
| 系统状态接口 | 目前只有 `/system/info`、`/system/health/extended`、`/system/desktop-manifest`，没有账号态专属接口 |

## 设计原则

| 原则 | 说明 |
| --- | --- |
| 状态源唯一 | Web 页面、桌面壳、后续托盘/通知都应消费同一份账号态快照 |
| 本地可观测优先 | 先判断本地文件与配置是否完整，不在首版引入联网登录校验 |
| 单平台先闭环 | 先把 B 站账号态页做稳，再扩展到更多平台 |
| 页面与设置分离 | `/auth-state` 用于巡检，`/scheduler` 继续承担配置和登录动作 |

## 方案选择

| 方案 | 做法 | 优点 | 缺点 | 结论 |
| --- | --- | --- | --- | --- |
| A | 新增 `/auth-state` + `/system/auth-state` + 轻量聚合服务 | 结构清晰，后续桌面壳/托盘可复用 | 要补一个小服务和新页面 | 推荐 |
| B | 把账号态卡片继续塞进 `/scheduler` | 实现快 | 页面职责继续膨胀，不利于后续扩展 | 不取 |
| C | 只在 Electron 壳体里做账号态卡片 | 桌面端体验直接 | Web 无统一入口，状态源分裂 | 不取 |

## 接口设计

### `GET /system/auth-state`

返回单用户账号态快照，首版包含：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `status` | string | 总状态：`ok` / `warning` / `missing` / `error` |
| `runtime_root` | string | 当前运行根目录 |
| `platforms` | list | 平台状态列表，首版只有 `bilibili` |
| `checked_at` | string | 本次状态生成时间 |

单个平台对象字段：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `platform` | string | 平台标识，首版固定 `bilibili` |
| `display_name` | string | 展示名 |
| `status` | string | 平台状态 |
| `cookie_configured` | bool | `data/app.env` 中是否已配置 Cookie |
| `storage_state_exists` | bool | `data/bilibili-storage-state.json` 是否存在 |
| `user_data_dir_exists` | bool | `data/bilibili-user-data/` 是否存在 |
| `storage_state_file` | string | 状态文件路径 |
| `user_data_dir` | string | 浏览器目录路径 |
| `action_hint` | string | 建议动作，例如“去 `/scheduler` 重新同步登录态” |
| `issues` | list[str] | 本平台问题列表 |

## 状态规则

| 状态 | 规则 |
| --- | --- |
| `ok` | Cookie 已配置，且 storage state 文件存在 |
| `warning` | Cookie 已配置，但 storage state 不存在；或 user-data 目录不存在 |
| `missing` | Cookie 未配置，且本地状态文件不存在 |
| `error` | 文件读取异常、状态文件内容明显非法，或状态构建过程抛错 |

总状态规则：

| 规则 | 结果 |
| --- | --- |
| 任一平台 `error` | 总状态 `error` |
| 无 `error` 但存在 `warning` | 总状态 `warning` |
| 全部 `missing` | 总状态 `missing` |
| 其余 | 总状态 `ok` |

## 页面设计

### `/auth-state`

页面结构：

| 区块 | 内容 |
| --- | --- |
| 顶部摘要 | 总状态、运行目录、首要建议动作 |
| 平台卡片 | B 站账号态卡片，展示 Cookie / storage state / user-data 三项状态 |
| 诊断明细 | 路径、问题列表、建议动作 |
| 快捷操作 | 返回首页、打开 `/scheduler` 去重新同步登录态 |

视觉与交互：

| 项目 | 方案 |
| --- | --- |
| 色彩 | 复用现有 `theme-dark` 和 `stat-card` / `status-badge` 风格 |
| 操作 | 不在本页直接发起登录，只给出明确跳转 |
| 空态 | 若当前没有任何平台配置，明确显示“尚未配置登录态” |

## 数据流

| 步骤 | 动作 |
| --- | --- |
| 1 | `AuthStateStatusService` 调用 `AuthStateService` 获取 B 站路径 |
| 2 | 服务读取 `AppEnvService().get_bilibili_settings()` 判断 Cookie 是否存在 |
| 3 | 服务检查 storage state 文件与 user-data 目录是否存在 |
| 4 | 服务计算平台状态与总状态，输出统一快照 |
| 5 | `/system/auth-state` 直接返回该快照 |
| 6 | `/auth-state` 页面复用同一份快照渲染 |

## 错误处理

| 场景 | 处理 |
| --- | --- |
| `data/app.env` 读取失败 | 平台状态记为 `error`，问题列表写入读取异常 |
| storage state 文件不存在 | 记为 `warning` 或 `missing`，提示去 `/scheduler` 重新同步 |
| user-data 目录不存在 | 不阻断页面，记为 `warning` |
| 页面渲染时服务异常 | 页面显示错误卡片，不影响其它系统页 |

## 测试策略

| 类别 | 覆盖点 |
| --- | --- |
| 单元测试 | 状态聚合服务在 `ok` / `warning` / `missing` / `error` 四种场景下的结果 |
| 集成测试 | `GET /system/auth-state` 响应结构、`/auth-state` 页面内容、`desktop-manifest.navigation` 新增入口 |
| 回归测试 | `/scheduler` 现有 B 站登录保存与浏览器同步流程不回退 |

## 暂不包含

| 项目 | 原因 |
| --- | --- |
| 多账号列表 | 当前模型仍是单用户运行目录 |
| 自动登录有效性校验 | 会引入联网副作用与风控 |
| 桌面壳托盘气泡 | 应在统一状态源稳定后再接 |

# 多账号来源绑定设计

## 目标

在现有单用户内核之上，补齐一个最小可用的多账号闭环：同一平台可以维护多份账号登录态，采集源可显式绑定某个账号执行，同时保持旧来源与默认账号路径继续可用。

## 范围

| 项目 | 本次是否包含 | 说明 |
| --- | --- | --- |
| B站多账号实体 | 是 | 引入轻量账号表，管理账号标识、默认账号和启用状态 |
| 来源绑定账号执行 | 是 | `Source` 可选择某个账号运行 |
| 账号隔离登录态路径 | 是 | Cookie、storage state、user-data-dir 按账号隔离 |
| 默认账号回退 | 是 | 老来源未绑定账号时，回退到平台默认账号 |
| 账号状态页升级 | 是 | `/auth-state` 从单用户卡片升级为账号列表快照 |
| 账号管理接口/页面 | 是 | 至少支持列出账号、创建槽位、设默认、发起登录 |
| 熔断桶升级到账号级 | 是 | 避免单个账号异常影响同平台全部来源 |
| 首版平台范围 | 仅 B站 | 当前只有 B站登录同步链路完整 |
| 通用多平台账号中心 | 否 | 后续再抽象到更多平台 |
| 多账号托盘子菜单 | 否 | 桌面壳继续消费聚合状态，不扩托盘层级 |
| 账号级并发调度优化 | 否 | 本轮只做可绑定、可执行、可观测 |

## 当前现状

| 模块 | 现状 |
| --- | --- |
| 来源模型 | `Source` 只有 `source_group` / `schedule_group` / `collection_strategy`，没有账号绑定字段 |
| 登录态路径 | `AuthStateService` 固定输出 `data/<platform>-user-data/` 与 `data/<platform>-storage-state.json` |
| B站登录同步 | `BilibiliBrowserAuthService` 只会把浏览器登录结果写回单一 B站路径，并更新全局 `BILIBILI_COOKIE` |
| B站采集策略 | `bilibili_profile_videos_recent` 直接读取全局 `BILIBILI_COOKIE` 与平台级 storage state |
| 账号态页面 | `/auth-state` 与 `/system/auth-state` 当前只展示单用户快照 |
| 熔断粒度 | `JobRunner` 仍按 `platform:single-user` 建桶 |

## 设计原则

| 原则 | 说明 |
| --- | --- |
| 先做最小闭环 | 首版只把 B站“账号管理 + 来源绑定 + 执行”做通，不提前做全平台通用中心 |
| 显式绑定优先 | 采集源应能明确知道自己使用哪个账号，不依赖隐式猜测 |
| 兼容旧数据 | 老来源和现有桌面壳入口不能因多账号改造直接失效 |
| 路径隔离清晰 | 每个账号都有独立 Cookie / storage state / user-data 目录，避免污染 |
| 默认账号兜底 | 未绑定来源仍能运行，但语义收敛为“使用平台默认账号” |
| 状态源统一 | Web 页面、系统接口、桌面壳继续消费统一的账号态快照 |

## 方案选择

| 方案 | 做法 | 优点 | 缺点 | 结论 |
| --- | --- | --- | --- | --- |
| A | 只做账号池管理，不让来源绑定账号 | 改动小 | 采集仍是单账号执行，多账号价值很弱 | 不取 |
| B | 新增账号表，来源可绑定账号，未绑定时走默认账号 | 能形成真正可用闭环；改动范围可控 | 首版仍只覆盖 B站 | 推荐 |
| C | 直接抽象 `SiteAccount` / `AuthProfile` / `SourceBinding` 完整体系 | 长期模型完整 | 本轮跨度过大，会同时拉高调度、页面和迁移复杂度 | 暂不取 |

## 数据模型

### 新增 `site_accounts`

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `id` | UUID | 主键 |
| `platform` | string(50) | 平台标识，首版固定支持 `bilibili` |
| `account_key` | string(100) | 稳定账号键，用于路径命名与熔断桶，例如 `default` / `creator-a` |
| `display_name` | string(100) | 页面展示名 |
| `enabled` | bool | 是否可被来源选择 |
| `is_default` | bool | 是否为该平台默认账号，同平台最多 1 个 |
| `created_at` / `updated_at` | datetime | 审计字段 |

约束：

| 约束 | 说明 |
| --- | --- |
| `(platform, account_key)` 唯一 | 防止同平台重复账号槽位 |
| 同平台默认账号唯一 | 创建或切换默认账号时要清理旧默认 |
| `account_key` 只允许安全字符 | 限制为小写字母、数字、`-`，便于目录命名 |

### 扩展 `sources`

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `account_id` | UUID nullable | 来源绑定的账号；为空表示使用默认账号或无需账号 |

兼容规则：

| 场景 | 规则 |
| --- | --- |
| 旧来源 | 迁移后 `account_id = NULL` |
| B站来源未绑定账号 | 执行时回退到 `bilibili` 平台默认账号 |
| 非账号依赖来源 | 允许 `account_id = NULL` 持续存在 |

## 登录态路径设计

`AuthStateService.build_paths(platform, account_key)` 升级为账号感知：

| 类型 | 旧路径 | 新路径 |
| --- | --- | --- |
| user data | `data/bilibili-user-data/` | `data/bilibili-<account_key>-user-data/` |
| storage state | `data/bilibili-storage-state.json` | `data/bilibili-<account_key>-storage-state.json` |

兼容规则：

| 场景 | 规则 |
| --- | --- |
| `account_key == default` | 继续复用旧单用户路径，避免现有登录态立刻失效 |
| 非默认账号 | 使用新账号隔离路径 |
| 老代码仍只传 `platform` | 通过默认账号分支兜底，逐步迁移到显式账号 |

## 接口与页面设计

### 账号管理 API

首版只补最小集合：

| 接口 | 作用 |
| --- | --- |
| `GET /api/site-accounts` | 列出账号 |
| `POST /api/site-accounts` | 创建账号槽位 |
| `PUT /api/site-accounts/{account_id}` | 更新展示名、启用状态 |
| `POST /api/site-accounts/{account_id}/set-default` | 设为平台默认账号 |
| `POST /api/site-accounts/{account_id}/bilibili/login` | 用该账号槽位发起浏览器登录 |

### 来源 API / 表单

| 位置 | 变更 |
| --- | --- |
| `SourceCreate` / `SourceUpdate` / `SourceRead` | 新增 `account_id` |
| `/api/sources` | 支持保存和返回账号绑定 |
| `/sources` 新建/编辑页 | 对 B站策略展示“执行账号”下拉；其他策略隐藏或禁用 |

### 账号态页面

| 位置 | 变更 |
| --- | --- |
| `/system/auth-state` | 从单用户快照升级为“平台账号列表 + 聚合状态”；同时保留总状态字段给桌面壳 |
| `/auth-state` | 渲染多个 B站账号卡片，显示默认账号、Cookie、storage state、user-data 状态 |
| `/scheduler` | 不再承载单一 B站账号假设，只保留跳转或当前账号相关入口 |

## 执行链路设计

### 来源解析

| 步骤 | 动作 |
| --- | --- |
| 1 | `Source` 执行前先解析当前来源是否需要账号 |
| 2 | 若来源显式绑定 `account_id`，加载对应 `site_accounts` 记录 |
| 3 | 若未绑定但策略属于 B站账号依赖来源，则加载平台默认账号 |
| 4 | 若没有可用默认账号，则抛出明确错误，提示先配置账号 |

### B站策略

| 模块 | 变更 |
| --- | --- |
| `BilibiliBrowserAuthService` | 登录时接收目标账号，把 Cookie / storage state 写入对应账号路径 |
| `AppEnvService` | 不再只维护单个全局 B站 Cookie，需要按账号读取与写入 |
| `bilibili_profile_videos_recent` | 不再直接读取全局 `BILIBILI_COOKIE`，改为按来源解析后的账号上下文取 cookie/storage state |
| 其他 B站策略 | 后续按同样模式迁移；本轮至少保证已有账号依赖路径不被单账号假设卡死 |

### 熔断桶

| 旧规则 | 新规则 |
| --- | --- |
| `platform:single-user` | `platform:<account_key>` |

效果：

| 场景 | 结果 |
| --- | --- |
| 账号 A 触发风控 | 只熔断 A，不阻塞账号 B |
| 默认账号异常 | 仅影响绑定默认账号或未显式绑定的来源 |

## 状态快照设计

`/system/auth-state` 首版升级为聚合结构：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `status` | string | 总状态，供桌面壳继续使用 |
| `runtime_root` | string | 当前运行目录 |
| `platforms` | list | 平台列表 |
| `checked_at` | string | 生成时间 |

平台对象增加账号层：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `platform` | string | 平台标识 |
| `display_name` | string | 平台名 |
| `status` | string | 平台聚合状态 |
| `accounts` | list | 账号列表 |

账号对象字段：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `account_id` | string | 账号主键 |
| `account_key` | string | 稳定账号键 |
| `display_name` | string | 展示名 |
| `is_default` | bool | 是否默认账号 |
| `enabled` | bool | 是否启用 |
| `status` | string | `ok` / `warning` / `missing` / `error` |
| `cookie_configured` | bool | Cookie 是否存在 |
| `storage_state_exists` | bool | storage state 是否存在 |
| `user_data_dir_exists` | bool | user-data 目录是否存在 |
| `issues` | list[str] | 问题列表 |
| `action_hint` | string | 建议动作 |

## 错误处理

| 场景 | 处理 |
| --- | --- |
| 来源绑定了不存在或禁用账号 | 创建/保存来源时阻止；运行时作为显式错误落日志 |
| 同平台没有默认账号且来源未绑定 | 运行失败，提示先设置默认账号 |
| 账号登录同步失败 | 不覆盖其他账号状态；只回写当前账号失败信息 |
| 路径读取异常 | 该账号状态记为 `error`，不影响其他账号 |
| 删除默认账号 | 首版可禁止删除，或要求先切换默认账号 |

## 测试策略

| 类别 | 覆盖点 |
| --- | --- |
| 单元测试 | 账号路径生成、默认账号解析、来源绑定校验、账号级状态聚合、熔断桶键生成 |
| 集成测试 | `site_accounts` API、来源保存 `account_id`、`/auth-state` 多账号渲染、`/system/auth-state` 多账号结构 |
| 策略测试 | B站策略按来源账号读取 cookie/storage state，未绑定时回退默认账号 |
| 迁移测试 | 老库升级后新增 `site_accounts` 与 `sources.account_id`，旧来源数据保留 |
| 回归测试 | Electron 仍能消费 `/system/auth-state.status`，单用户默认路径继续可用 |

## 暂不包含

| 项目 | 原因 |
| --- | --- |
| YouTube / X 多账号 | 当前没有完整登录同步闭环，不适合一起推 |
| 账号共享权限模型 | 超出本地单机版边界 |
| 多账号托盘子菜单 | 优先级低，且会放大桌面壳复杂度 |
| 账号级调度配额与并发控制 | 需在闭环稳定后再补 |

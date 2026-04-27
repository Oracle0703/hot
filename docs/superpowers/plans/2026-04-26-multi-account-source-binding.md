# Multi-Account Source Binding Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为 B站补齐“多账号管理 + 来源绑定账号执行 + 多账号账号态展示”的最小闭环，同时兼容现有单用户默认路径和旧来源。

**Architecture:** 先新增轻量 `site_accounts` 模型和 `sources.account_id` 绑定，再把登录态路径、账号态快照、来源表单/API、B站登录与策略执行链路改成账号感知。默认账号继续复用旧单用户路径，保证旧数据和桌面壳契约不直接失效。

**Tech Stack:** FastAPI, SQLAlchemy ORM, Alembic, SQLite 兼容补丁, Pydantic, pytest

---

## 当前执行状态（2026-04-26）

| 项目 | 状态 | 说明 |
| --- | --- | --- |
| Task 1 | 已完成 | `site_accounts`、`sources.account_id`、Alembic 与 SQLite 兼容补丁已落地 |
| Task 2 | 已完成 | 账号 schema / service、默认账号切换与来源绑定校验已落地 |
| Task 3 | 已完成 | `/api/site-accounts`、来源账号绑定表单/API、来源编辑页账号下拉已落地 |
| Task 4 | 已完成 | `/system/auth-state`、`/auth-state`、账号感知 Cookie / storage state 路径已落地 |
| Task 5 | 已完成 | B站来源执行链路、策略读取、浏览器登录同步、熔断桶都已按账号运行 |
| Task 6 | 已完成 | README / API 文档 / roadmap / release 兼容说明已同步 |
| Scheduler 登录入口收口 | 已完成 | `/scheduler` 的手工 Cookie 保存和浏览器登录同步都支持 `account_key` 账号槽位 |
| 当前剩余阻塞项 | 无 | 多账号首版闭环已打通；后续若继续扩展，下一阶段是非 B站平台账号化 |

---

## 文件结构

| 文件 | 责任 |
| --- | --- |
| `app/models/site_account.py` | 新增站点账号模型 |
| `app/models/source.py` | 为来源增加 `account_id` 外键字段 |
| `app/models/__init__.py` | 导出 `SiteAccount` 供 metadata / Alembic 使用 |
| `app/schemas/site_account.py` | 账号 API schema |
| `app/schemas/source.py` | 来源 schema 新增 `account_id` |
| `app/services/site_account_service.py` | 账号创建、查询、默认账号切换、来源可用性校验 |
| `app/services/auth_state_service.py` | 路径构建升级为账号感知 |
| `app/services/app_env_service.py` | B站 Cookie 从单值升级为按账号管理 |
| `app/services/bilibili_auth_service.py` | 登录同步指定账号槽位 |
| `app/services/auth_state_status_service.py` | `/system/auth-state` 聚合多账号快照 |
| `app/services/source_execution_service.py` | 统一解析来源账号上下文并注入策略 |
| `app/services/strategies/bilibili_profile_videos_recent.py` | 按来源账号读取 Cookie / storage state |
| `app/services/strategies/bilibili_site_search.py` | 按来源账号读取可选 Cookie |
| `app/workers/runner.py` | 熔断桶升级为账号级 |
| `app/api/routes_site_accounts.py` | 新增账号 API |
| `app/api/routes_sources.py` | 来源 API 支持 `account_id` |
| `app/api/routes_pages.py` | 来源页面账号下拉、账号页、`/auth-state` 多账号渲染 |
| `app/api/routes_system.py` | 暴露多账号账号态结构 |
| `app/main.py` | 注册账号 API 路由 |
| `app/db.py` | SQLite 旧库补列逻辑增加 `sources.account_id` 与账号表兼容 |
| `migrations/versions/0007_site_accounts_and_source_account_binding.py` | Alembic 增量迁移 |
| `tests/unit/test_site_account_service.py` | 账号服务单测 |
| `tests/unit/test_auth_state_status_service.py` | 多账号状态聚合单测 |
| `tests/unit/test_strategy_bilibili_profile_videos_recent.py` | B站主页策略账号化单测 |
| `tests/unit/test_strategy_bilibili_site_search.py` | B站站内搜索策略账号化单测 |
| `tests/unit/test_source_service.py` | 来源绑定账号读写单测 |
| `tests/unit/test_alembic_migrations.py` | 迁移回归 |
| `tests/integration/test_site_accounts_api.py` | 新账号 API 集成测试 |
| `tests/integration/test_sources_api.py` | 来源 API 账号绑定集成测试 |
| `tests/integration/test_system_api.py` | `/system/auth-state` 多账号结构回归 |
| `tests/integration/test_pages.py` | `/sources` 表单与 `/auth-state` 页面多账号回归 |
| `README.md` / `docs/specs/api-reference.md` / roadmap 文档 | 功能状态与接口说明 |

### Task 1: 建立账号模型与数据库迁移基础

**Files:**
- Create: `app/models/site_account.py`
- Create: `migrations/versions/0007_site_accounts_and_source_account_binding.py`
- Modify: `app/models/source.py`
- Modify: `app/models/__init__.py`
- Modify: `app/db.py`
- Test: `tests/unit/test_alembic_migrations.py`
- Test: `tests/unit/test_source_service.py`

- [x] **Step 1: 先写迁移失败测试**

```python
def test_upgrade_head_creates_site_accounts_and_source_account_id(tmp_path) -> None:
    url = _sqlite_url(tmp_path, "multi-account.db")
    engine = create_engine(url)

    run_migrations(engine, url, backup_dir=tmp_path / "backups")

    insp = inspect(engine)
    assert "site_accounts" in insp.get_table_names()
    source_columns = {column["name"] for column in insp.get_columns("sources")}
    assert "account_id" in source_columns
```

- [x] **Step 2: 跑测试确认当前失败**

Run: `./.venv/Scripts/python.exe -m pytest tests/unit/test_alembic_migrations.py -k "site_accounts or source_account_id" -v`

Expected: FAIL，提示 `site_accounts` 表或 `sources.account_id` 字段不存在。

- [x] **Step 3: 实现最小模型与迁移**

```python
class SiteAccount(Base):
    __tablename__ = "site_accounts"

    id: Mapped[str] = mapped_column(Uuid, primary_key=True, default=uuid4)
    platform: Mapped[str] = mapped_column(String(50), nullable=False)
    account_key: Mapped[str] = mapped_column(String(100), nullable=False)
    display_name: Mapped[str] = mapped_column(String(100), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
```

迁移要求：
- 创建 `site_accounts`
- 为 `sources` 增加可空 `account_id`
- 给 `site_accounts(platform, account_key)` 加唯一索引
- 保持 downgrade 可执行
- 在 `app/db.py` 的 SQLite 兼容补丁里加入 `sources.account_id`

- [x] **Step 4: 再跑迁移与来源服务测试**

Run: `./.venv/Scripts/python.exe -m pytest tests/unit/test_alembic_migrations.py tests/unit/test_source_service.py -v`

Expected: PASS，且旧 `Source` 读写行为不回退。

- [x] **Step 5: 提交本任务**

```bash
git add app/models/site_account.py app/models/source.py app/models/__init__.py app/db.py migrations/versions/0007_site_accounts_and_source_account_binding.py tests/unit/test_alembic_migrations.py tests/unit/test_source_service.py
git commit -m "feat: add site account schema for source binding"
```

### Task 2: 补齐账号 schema 与服务层

**Files:**
- Create: `app/schemas/site_account.py`
- Create: `app/services/site_account_service.py`
- Modify: `app/services/source_service.py`
- Test: `tests/unit/test_site_account_service.py`
- Test: `tests/unit/test_source_service.py`

- [x] **Step 1: 先写账号服务失败测试**

```python
def test_set_default_account_clears_old_default(session) -> None:
    service = SiteAccountService(session)
    first = service.create_account(...)
    second = service.create_account(...)

    updated = service.set_default_account(str(second.id))

    assert updated.is_default is True
    assert service.get_account(str(first.id)).is_default is False
```

- [x] **Step 2: 跑测试确认服务尚不存在**

Run: `./.venv/Scripts/python.exe -m pytest tests/unit/test_site_account_service.py -v`

Expected: FAIL，提示 `SiteAccountService` 或相关 schema 不存在。

- [x] **Step 3: 实现账号服务与来源校验**

```python
class SiteAccountService:
    def list_accounts(self, platform: str | None = None) -> list[SiteAccount]: ...
    def create_account(self, data: SiteAccountCreate) -> SiteAccount: ...
    def set_default_account(self, account_id: str) -> SiteAccount: ...
    def get_default_account(self, platform: str) -> SiteAccount | None: ...
    def ensure_bindable_account(self, account_id: str) -> SiteAccount: ...
```

要求：
- `account_key` 规范化为小写字母、数字、`-`
- 同平台默认账号唯一
- `SourceService.create_source/update_source` 在收到 `account_id` 时校验账号存在且启用
- 未提供 `account_id` 时不强制绑定

- [x] **Step 4: 运行账号服务与来源服务测试**

Run: `./.venv/Scripts/python.exe -m pytest tests/unit/test_site_account_service.py tests/unit/test_source_service.py -v`

Expected: PASS，账号默认切换与来源绑定校验通过。

- [x] **Step 5: 提交本任务**

```bash
git add app/schemas/site_account.py app/services/site_account_service.py app/services/source_service.py tests/unit/test_site_account_service.py tests/unit/test_source_service.py
git commit -m "feat: add site account service layer"
```

### Task 3: 打通账号 API 与来源 API/表单绑定

**Files:**
- Create: `app/api/routes_site_accounts.py`
- Modify: `app/main.py`
- Modify: `app/schemas/source.py`
- Modify: `app/api/routes_sources.py`
- Modify: `app/api/routes_pages.py`
- Test: `tests/integration/test_site_accounts_api.py`
- Test: `tests/integration/test_sources_api.py`
- Test: `tests/integration/test_pages.py`

- [x] **Step 1: 先写 API 与页面失败测试**

```python
def test_create_site_account_returns_201(tmp_path) -> None:
    client = create_test_client(make_sqlite_url(tmp_path, "site-accounts.db"))
    response = client.post("/api/site-accounts", json={
        "platform": "bilibili",
        "account_key": "creator-a",
        "display_name": "UP主A",
    })
    assert response.status_code == 201
```

```python
def test_edit_source_page_shows_account_selector_for_bilibili_source(tmp_path) -> None:
    response = client.get(f"/sources/{source_id}")
    assert "name='account_id'" in response.text
```

- [x] **Step 2: 跑测试确认接口和表单缺失**

Run: `./.venv/Scripts/python.exe -m pytest tests/integration/test_site_accounts_api.py tests/integration/test_sources_api.py tests/integration/test_pages.py -k "site_account or account_id" -v`

Expected: FAIL，提示 `/api/site-accounts` 404 或页面中不存在 `account_id` 字段。

- [x] **Step 3: 实现账号 API 与来源绑定表单**

```python
class SourceCreate(BaseModel):
    ...
    account_id: UUID | None = None
```

要求：
- 注册 `/api/site-accounts`
- 支持 `GET/POST/PUT/POST set-default`
- `/api/sources` 的 create/update/read 返回 `account_id`
- `/sources/new` 与 `/sources/{id}` 对 B站策略渲染账号下拉
- 非 B站策略不暴露账号选择，避免误绑

- [x] **Step 4: 跑集成测试**

Run: `./.venv/Scripts/python.exe -m pytest tests/integration/test_site_accounts_api.py tests/integration/test_sources_api.py tests/integration/test_pages.py -k "site_account or account_id or auth_state" -v`

Expected: PASS，账号 API 可用，来源表单能保存账号绑定。

- [x] **Step 5: 提交本任务**

```bash
git add app/api/routes_site_accounts.py app/main.py app/schemas/source.py app/api/routes_sources.py app/api/routes_pages.py tests/integration/test_site_accounts_api.py tests/integration/test_sources_api.py tests/integration/test_pages.py
git commit -m "feat: expose site account api and source binding ui"
```

### Task 4: 升级登录态路径、Cookie 存储与多账号状态页

**Files:**
- Modify: `app/services/auth_state_service.py`
- Modify: `app/runtime_paths.py`
- Modify: `app/services/app_env_service.py`
- Modify: `app/services/auth_state_status_service.py`
- Modify: `app/api/routes_system.py`
- Modify: `app/api/routes_pages.py`
- Test: `tests/unit/test_auth_state_status_service.py`
- Test: `tests/integration/test_system_api.py`
- Test: `tests/integration/test_pages.py`

- [x] **Step 1: 先写多账号状态失败测试**

```python
def test_auth_state_status_service_returns_account_list_for_bilibili(tmp_path) -> None:
    snapshot = AuthStateStatusService(...).build_snapshot()
    bilibili = snapshot["platforms"][0]
    assert "accounts" in bilibili
    assert bilibili["accounts"][0]["account_key"] == "default"
```

```python
def test_system_auth_state_returns_multi_account_snapshot(tmp_path) -> None:
    response = client.get("/system/auth-state")
    assert response.json()["platforms"][0]["accounts"]
```

- [x] **Step 2: 跑测试确认当前仍是单用户结构**

Run: `./.venv/Scripts/python.exe -m pytest tests/unit/test_auth_state_status_service.py tests/integration/test_system_api.py tests/integration/test_pages.py -k "accounts or auth_state" -v`

Expected: FAIL，当前快照没有 `accounts` 列表，页面只渲染单卡片。

- [x] **Step 3: 实现账号感知路径与状态聚合**

```python
@dataclass(slots=True)
class AuthStatePaths:
    user_data_dir: Path
    storage_state_file: Path

def build_paths(self, platform: str, account_key: str = "default") -> AuthStatePaths:
    if account_key == "default":
        return old_single_user_paths(...)
    return AuthStatePaths(
        user_data_dir=data_dir / f"{platform}-{account_key}-user-data",
        storage_state_file=data_dir / f"{platform}-{account_key}-storage-state.json",
    )
```

要求：
- `AppEnvService` 新增按账号读取/写入 B站 Cookie 的接口，保留默认账号回退
- `AuthStateStatusService` 读取账号列表并聚合为 `platforms[].accounts[]`
- `/auth-state` 页面展示多个账号卡片和默认账号标记
- `/system/auth-state` 保留顶层 `status` 字段供 Electron 兼容消费

- [x] **Step 4: 跑状态页测试**

Run: `./.venv/Scripts/python.exe -m pytest tests/unit/test_auth_state_status_service.py tests/integration/test_system_api.py tests/integration/test_pages.py -k "auth_state" -v`

Expected: PASS，多账号快照结构稳定，页面与系统接口一致。

- [x] **Step 5: 提交本任务**

```bash
git add app/services/auth_state_service.py app/runtime_paths.py app/services/app_env_service.py app/services/auth_state_status_service.py app/api/routes_system.py app/api/routes_pages.py tests/unit/test_auth_state_status_service.py tests/integration/test_system_api.py tests/integration/test_pages.py
git commit -m "feat: add multi-account auth state snapshots"
```

### Task 5: 让 B站登录与执行链路真正按账号运行

**Files:**
- Modify: `app/services/bilibili_auth_service.py`
- Modify: `app/services/source_execution_service.py`
- Modify: `app/services/strategies/__init__.py`
- Modify: `app/services/strategies/bilibili_profile_videos_recent.py`
- Modify: `app/services/strategies/bilibili_site_search.py`
- Modify: `app/workers/runner.py`
- Test: `tests/unit/test_strategy_bilibili_profile_videos_recent.py`
- Test: `tests/unit/test_strategy_bilibili_site_search.py`
- Test: `tests/e2e/test_full_smoke.py`

- [x] **Step 1: 先写账号执行失败测试**

```python
def test_bilibili_profile_runner_reads_storage_state_for_bound_account(tmp_path, monkeypatch) -> None:
    auth_state_service = AuthStateService(runtime_root=tmp_path)
    storage_state_file = auth_state_service.build_paths("bilibili", "creator-a").storage_state_file
    ...
    source = SimpleNamespace(entry_url="https://space.bilibili.com/20411266", account_key="creator-a")
    items = asyncio.run(runner._fetch_items(source))
    assert browser.new_context_kwargs["storage_state"] == str(storage_state_file)
```

```python
def test_job_runner_builds_account_scoped_breaker_bucket() -> None:
    bucket = runner._build_circuit_breaker_bucket(SimpleNamespace(site_name="Bilibili", account_key="creator-a"))
    assert bucket == "bilibili:creator-a"
```

- [x] **Step 2: 跑测试确认当前仍是 `single-user`**

Run: `./.venv/Scripts/python.exe -m pytest tests/unit/test_strategy_bilibili_profile_videos_recent.py tests/unit/test_strategy_bilibili_site_search.py tests/e2e/test_full_smoke.py -k "account or single-user or storage_state" -v`

Expected: FAIL，策略仍只读全局 `BILIBILI_COOKIE` / 默认 storage state。

- [x] **Step 3: 实现账号上下文解析与策略注入**

```python
class SourceExecutionService:
    def _resolve_account_context(self, source) -> dict[str, str] | None: ...
```

要求：
- `BilibiliBrowserAuthService` 登录接口接收 `account_id` 或 `account_key`
- `SourceExecutionService` 为账号依赖策略补齐 `account_key` / `account_cookie`
- `bilibili_profile_videos_recent` 与 `bilibili_site_search` 优先读来源账号上下文，未绑定则回退默认账号
- `JobRunner` 熔断桶键从 `platform:single-user` 升级为 `platform:<account_key>`

- [x] **Step 4: 跑单元与烟雾测试**

Run: `./.venv/Scripts/python.exe -m pytest tests/unit/test_strategy_bilibili_profile_videos_recent.py tests/unit/test_strategy_bilibili_site_search.py tests/e2e/test_full_smoke.py -k "bilibili or account" -v`

Expected: PASS，绑定账号来源可用，默认账号回退不破坏旧链路。

- [x] **Step 5: 提交本任务**

```bash
git add app/services/bilibili_auth_service.py app/services/source_execution_service.py app/services/strategies/__init__.py app/services/strategies/bilibili_profile_videos_recent.py app/services/strategies/bilibili_site_search.py app/workers/runner.py tests/unit/test_strategy_bilibili_profile_videos_recent.py tests/unit/test_strategy_bilibili_site_search.py tests/e2e/test_full_smoke.py
git commit -m "feat: execute bilibili sources with bound accounts"
```

### Task 6: 文档、发布兼容与最终回归

**Files:**
- Modify: `README.md`
- Modify: `docs/specs/api-reference.md`
- Modify: `architecture/roadmap/2026-04-24-repository-implementation-plan.md`
- Modify: `architecture/roadmap/2026-q2-implementation-roadmap.md`
- Modify: `docs/desktop-shell-integration.md`

- [x] **Step 1: 先补文档断言或 checklist**

```text
- README 标记“多账号来源绑定”已完成
- api-reference 增加 /api/site-accounts 与新的 /system/auth-state 结构
- roadmap 把“多账号体系”从未完成改成已完成
```

- [x] **Step 2: 执行核心回归测试**

Run: `./.venv/Scripts/python.exe -m pytest tests/unit/test_alembic_migrations.py tests/unit/test_site_account_service.py tests/unit/test_auth_state_status_service.py tests/unit/test_strategy_bilibili_profile_videos_recent.py tests/unit/test_strategy_bilibili_site_search.py tests/integration/test_site_accounts_api.py tests/integration/test_sources_api.py tests/integration/test_system_api.py tests/integration/test_pages.py -v`

Expected: PASS；若 `tests/integration/test_pages.py` 出现已知 flaky，用单测结果和子集结果单独记录，不要误报“全绿”。

- [x] **Step 3: 执行发布兼容与格式检查**

Run: `powershell -ExecutionPolicy Bypass -File scripts/prepare_release.ps1`

Run: `git diff --check`

Expected: release 组装成功；`git diff --check` 退出码 `0`，最多只有 CRLF warning。

- [x] **Step 4: 更新文档**

要求：
- README 说明多账号仅首版覆盖 B站
- `docs/specs/api-reference.md` 写清 `/system/auth-state` 的 `accounts` 结构
- roadmap 与桌面壳文档说明 Electron 仍消费聚合顶层状态

- [x] **Step 5: 提交本任务**

```bash
git add README.md docs/specs/api-reference.md architecture/roadmap/2026-04-24-repository-implementation-plan.md architecture/roadmap/2026-q2-implementation-roadmap.md docs/desktop-shell-integration.md
git commit -m "docs: document multi-account source binding"
```

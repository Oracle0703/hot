# Stable Crawling And Data Center Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在当前仓库上分阶段落地单用户稳定采集内核、数据处理中心和订阅推送中心，不重写技术栈。

**Architecture:** 保持 `Python + FastAPI + Playwright` 为核心，先把单用户登录态、失败分类、调度治理和策略边界收敛，再在现有数据模型旁边增加 `RawItem` / `ContentItem` / `Subscription` / `DeliveryRecord`。现有报告链路暂不删除，而是先改造成消费新内容模型的兼容层，避免一次性大拆。

**Tech Stack:** Python 3.11, FastAPI, SQLAlchemy, Alembic, Playwright, Pytest, SQLite

---

## 当前状态（2026-04-26）

| 任务 | 状态 | 当前结论 |
| --- | --- | --- |
| Task 1 | 已完成 | 单用户登录态已收敛到 `AuthStateService`，运行时路径与 B 站登录同步/读取已统一 |
| Task 2 | 已完成 | 失败分类、重试边界、熔断与结构化运行日志已接入执行器 |
| Task 3 | 已完成 | `RawItem -> ContentItem` 内容流水线、归一化与兼容报告输出已落地 |
| Task 4 | 已完成 | `Subscription -> DeliveryRecord` 分发链路、匹配与去重投递已落地 |
| Task 5 | 已完成 | 内容中心、订阅中心、投递状态的 API 与页面入口已落地，并补了筛选/重试 |
| Task 6 | 已完成 | 文档、Alembic 校验、端到端冒烟与桌面壳接入契约已补齐 |

## 当前未完成项（不属于本计划原始 1~6 Task）

| 项目 | 状态 | 说明 |
| --- | --- | --- |
| 桌面壳实体应用 | 未完成 | 当前仅完成 `desktop-manifest`、schema、consumer 示例与本地控制面契约，尚未实现 Electron / Tauri 壳体 |
| 托盘/系统通知 | 未完成 | 当前仍由现有 launcher、页面和脚本承担本地运行交互 |
| 多账号体系 | 未完成 | 当前仍按单用户、固定运行目录设计 |
| 独立账号态状态页 | 未完成 | 已有登录态服务与相关能力，但尚未单独抽出账号态巡检页 |

## 当前仓库关键入口

| 路径 | 当前责任 |
| --- | --- |
| `app/main.py:27-84` | 应用组装，注入调度器、执行器、路由 |
| `app/runtime_paths.py:9-73` | 运行时目录布局，目前就是单用户登录态的主要落点 |
| `app/services/bilibili_auth_service.py:23-146` | B 站浏览器登录态获取与同步 |
| `app/workers/runner.py:25-256` | 任务主执行循环、日志、报告、钉钉通知 |
| `app/services/retry_policy.py:17-77` | 轻量重试策略 |
| `app/services/strategies/registry.py:16-139` | 策略错误码和注册表 |
| `app/models/source.py:11-34` | 来源定义，目前未绑定账号态 |
| `app/models/item.py:12-43` | 当前采集内容表 `CollectedItem` |
| `app/services/report_service.py:26-497` | 落库 `CollectedItem` 并生成报告 |
| `app/services/weekly_dingtalk_push_service.py:20-103` | 当前人工筛选后钉钉推送 |

## Task 1（已完成）: 收敛单用户登录态与浏览器状态管理

**Files:**
- Create: `app/services/auth_state_service.py`
- Create: `tests/unit/test_auth_state_service.py`
- Modify: `app/runtime_paths.py`
- Modify: `app/services/bilibili_auth_service.py`
- Modify: `app/services/strategies/bilibili_profile_videos_recent.py`
- Modify: `tests/unit/test_bilibili_auth_service.py`
- Modify: `tests/unit/test_runtime_paths.py`
- Modify: `tests/unit/test_strategy_bilibili_profile_videos_recent.py`
- Test: `tests/unit/test_auth_state_service.py`

- [ ] **Step 1: 写失败测试，先固定单用户登录态路径和状态读取行为**

```python
def test_auth_state_service_builds_single_user_paths(tmp_path) -> None:
    service = AuthStateService(runtime_root=tmp_path)
    paths = service.build_paths(platform="bilibili")
    assert paths.user_data_dir == tmp_path / "data" / "bilibili-user-data"
    assert paths.storage_state_file == tmp_path / "data" / "bilibili-storage-state.json"
```

- [ ] **Step 2: 运行测试确认当前仓库还没有统一服务层**

Run: `pytest tests/unit/test_runtime_paths.py tests/unit/test_bilibili_auth_service.py tests/unit/test_strategy_bilibili_profile_videos_recent.py tests/unit/test_auth_state_service.py -v`

Expected: `test_auth_state_service.py` 缺失，且现有逻辑分散在 `runtime_paths.py` 与各站点策略中。

- [ ] **Step 3: 增加单用户登录态服务**

```python
@dataclass(slots=True)
class AuthStatePaths:
    user_data_dir: Path
    storage_state_file: Path


class AuthStateService:
    def build_paths(self, platform: str) -> AuthStatePaths: ...
```

- [ ] **Step 4: 收敛 B 站登录同步和策略读取路径**

```python
paths = auth_state_service.build_paths("bilibili")
context = await playwright.chromium.launch_persistent_context(str(paths.user_data_dir), **launch_kwargs)
await context.storage_state(path=str(paths.storage_state_file))
```

- [ ] **Step 5: 让抓取策略统一从服务层读取状态**

```python
storage_state_file = auth_state_service.build_paths("bilibili").storage_state_file
if storage_state_file.exists():
    kwargs["storage_state"] = str(storage_state_file)
```

- [ ] **Step 6: 运行测试确认通过**

Run: `pytest tests/unit/test_auth_state_service.py tests/unit/test_runtime_paths.py tests/unit/test_bilibili_auth_service.py tests/unit/test_strategy_bilibili_profile_videos_recent.py -v`

Expected: PASS，且单用户登录态路径通过统一服务读取，不再散落在多个模块。

- [ ] **Step 7: 提交**

```bash
git add app/services/auth_state_service.py app/runtime_paths.py app/services/bilibili_auth_service.py app/services/strategies/bilibili_profile_videos_recent.py tests/unit/test_auth_state_service.py tests/unit/test_bilibili_auth_service.py tests/unit/test_runtime_paths.py tests/unit/test_strategy_bilibili_profile_videos_recent.py
git commit -m "refactor: centralize single-user auth state paths"
```

## Task 2（已完成）: 收敛失败分类、重试决策和运行器治理

**Files:**
- Create: `app/services/failure_classifier.py`
- Create: `app/services/circuit_breaker_service.py`
- Create: `tests/unit/test_failure_classifier.py`
- Create: `tests/unit/test_circuit_breaker_service.py`
- Modify: `app/services/strategies/registry.py`
- Modify: `app/services/retry_policy.py`
- Modify: `app/workers/runner.py`
- Modify: `tests/unit/test_retry_policy.py`
- Modify: `tests/unit/test_runner.py`
- Modify: `tests/unit/test_strategy_registry.py`
- Test: `tests/unit/test_failure_classifier.py`

- [ ] **Step 1: 写失败测试，先固定标准错误和不可重试行为**

```python
def test_auth_error_is_not_retried() -> None:
    policy = RetryPolicy(max_attempts=3, retry_on=("NETWORK", "TIMEOUT"))
    assert policy.should_retry("AUTH_EXPIRED", 1) is False


def test_circuit_breaker_opens_after_repeated_risk_control() -> None:
    breaker = CircuitBreakerService(threshold=3)
    for _ in range(3):
        breaker.record_failure("bilibili:market-01", "RISK_CONTROL")
    assert breaker.is_open("bilibili:market-01") is True
```

- [ ] **Step 2: 运行测试确认现有错误码和运行器不满足**

Run: `pytest tests/unit/test_retry_policy.py tests/unit/test_runner.py tests/unit/test_strategy_registry.py tests/unit/test_failure_classifier.py tests/unit/test_circuit_breaker_service.py -v`

Expected: FAIL，当前 `ReasonCode` 仅有粗粒度分类，`JobRunner` 也没有账号级熔断状态。

- [ ] **Step 3: 扩展错误分类并增加失败映射器**

```python
class FailureCode:
    NETWORK = "NETWORK"
    TIMEOUT = "TIMEOUT"
    PARSE = "PARSE"
    AUTH_EXPIRED = "AUTH_EXPIRED"
    AUTH_MISSING = "AUTH_MISSING"
    RISK_CONTROL = "RISK_CONTROL"
    PERMISSION_DENIED = "PERMISSION_DENIED"
```

- [ ] **Step 4: 增加熔断服务并在 `JobRunner` 中接入**

```python
bucket_key = f"{platform}:{account_key}"
if circuit_breaker.is_open(bucket_key):
    raise RuntimeError("source blocked by circuit breaker")
```

- [ ] **Step 5: 让 `JobRunner` 记录结构化失败信息，而不是只写裸字符串**

```python
session.add(JobLog(job_id=job.id, source_id=source.id, level="error", message=f"[{failure.code}] {failure.message}"))
```

- [ ] **Step 6: 运行测试确认重试、熔断和日志行为正确**

Run: `pytest tests/unit/test_failure_classifier.py tests/unit/test_circuit_breaker_service.py tests/unit/test_retry_policy.py tests/unit/test_runner.py tests/unit/test_strategy_registry.py -v`

Expected: PASS，且 `AUTH_EXPIRED`、`PARSE` 不再被重试，`RISK_CONTROL` 可触发熔断。

- [ ] **Step 7: 提交**

```bash
git add app/services/failure_classifier.py app/services/circuit_breaker_service.py app/services/strategies/registry.py app/services/retry_policy.py app/workers/runner.py tests/unit/test_failure_classifier.py tests/unit/test_circuit_breaker_service.py tests/unit/test_retry_policy.py tests/unit/test_runner.py tests/unit/test_strategy_registry.py
git commit -m "feat: add failure taxonomy and runner circuit breaking"
```

## Task 3（已完成）: 建立原始内容层与共享内容层

**Files:**
- Create: `app/models/raw_item.py`
- Create: `app/models/content_item.py`
- Create: `app/services/content_normalizer_service.py`
- Create: `app/services/content_pipeline_service.py`
- Create: `migrations/versions/0004_content_center_models.py`
- Create: `tests/unit/test_content_normalizer_service.py`
- Create: `tests/unit/test_content_pipeline_service.py`
- Modify: `app/models/__init__.py`
- Modify: `app/services/report_service.py`
- Modify: `tests/unit/test_models.py`
- Modify: `tests/unit/test_report_service.py`
- Test: `tests/unit/test_content_pipeline_service.py`

- [ ] **Step 1: 写失败测试，先定义 `RawItem -> ContentItem` 两层模型**

```python
def test_pipeline_promotes_raw_items_into_content_items(session) -> None:
    pipeline = ContentPipelineService(session)
    created = pipeline.ingest_run(job_id, source_id, [{"title": "校招信息", "url": "https://example.com/a"}])
    assert created.raw_count == 1
    assert created.content_count == 1
```

- [ ] **Step 2: 运行测试确认现有仓库只有 `CollectedItem`**

Run: `pytest tests/unit/test_models.py tests/unit/test_report_service.py tests/unit/test_content_normalizer_service.py tests/unit/test_content_pipeline_service.py -v`

Expected: FAIL，`RawItem` / `ContentItem` 尚不存在。

- [ ] **Step 3: 增加内容中心模型与迁移**

```python
class RawItem(Base):
    __tablename__ = "raw_items"
    source_id = mapped_column(Uuid, ForeignKey("sources.id"), nullable=False)
    job_id = mapped_column(Uuid, ForeignKey("collection_jobs.id"), nullable=False)
    payload = mapped_column(JSON, nullable=False)


class ContentItem(Base):
    __tablename__ = "content_items"
    dedupe_key = mapped_column(String(128), nullable=False, unique=True)
    title = mapped_column(String(300), nullable=False)
    canonical_url = mapped_column(Text, nullable=False)
    tags = mapped_column(JSON, nullable=False, default=list)
```

- [ ] **Step 4: 实现归一化和去重流水线**

```python
normalized = normalizer.normalize(source=source, raw_payload=item)
content = self._get_or_create_by_dedupe_key(normalized.dedupe_key)
content.title = normalized.title
content.tags = normalized.tags
```

- [ ] **Step 5: 让 `ReportService` 先消费 `ContentItem`，保留 `CollectedItem` 为兼容输出**

```python
pipeline_result = ContentPipelineService(self.session).ingest_run(job.id, source_runs)
items = pipeline_result.content_items
```

- [ ] **Step 6: 运行测试确认新内容流水线可工作**

Run: `pytest tests/unit/test_content_normalizer_service.py tests/unit/test_content_pipeline_service.py tests/unit/test_models.py tests/unit/test_report_service.py -v`

Expected: PASS，且报告服务仍可输出。

- [ ] **Step 7: 提交**

```bash
git add app/models/raw_item.py app/models/content_item.py app/services/content_normalizer_service.py app/services/content_pipeline_service.py app/models/__init__.py app/services/report_service.py migrations/versions/0004_content_center_models.py tests/unit/test_content_normalizer_service.py tests/unit/test_content_pipeline_service.py tests/unit/test_models.py tests/unit/test_report_service.py
git commit -m "feat: add raw and content item pipeline"
```

## Task 4（已完成）: 增加订阅、匹配与投递记录

**Files:**
- Create: `app/models/subscription.py`
- Create: `app/models/delivery_record.py`
- Create: `app/services/subscription_matcher_service.py`
- Create: `app/services/content_dispatch_service.py`
- Create: `migrations/versions/0005_subscriptions_and_delivery_records.py`
- Create: `tests/unit/test_subscription_matcher_service.py`
- Create: `tests/unit/test_content_dispatch_service.py`
- Modify: `app/models/__init__.py`
- Modify: `app/services/weekly_dingtalk_push_service.py`
- Modify: `tests/unit/test_models.py`
- Modify: `tests/unit/test_weekly_dingtalk_push_service.py`
- Test: `tests/unit/test_content_dispatch_service.py`

- [ ] **Step 1: 写失败测试，先定义订阅匹配和去重投递**

```python
def test_matcher_selects_subscription_by_business_line_and_keyword(session) -> None:
    matched = SubscriptionMatcherService(session).match(content_item)
    assert [item.code for item in matched] == ["hr-daily"]


def test_dispatch_service_does_not_send_duplicate_delivery(session, sender) -> None:
    count = ContentDispatchService(session, sender=sender).dispatch_content_item(content_item.id)
    assert count == 1
```

- [ ] **Step 2: 运行测试确认订阅与投递模型尚不存在**

Run: `pytest tests/unit/test_models.py tests/unit/test_weekly_dingtalk_push_service.py tests/unit/test_subscription_matcher_service.py tests/unit/test_content_dispatch_service.py -v`

Expected: FAIL，当前仅有人工筛选推送，没有内容级订阅分发。

- [ ] **Step 3: 增加模型与匹配服务**

```python
class Subscription(Base):
    __tablename__ = "subscriptions"
    code = mapped_column(String(100), nullable=False, unique=True)
    channel = mapped_column(String(30), nullable=False, default="dingtalk")
    business_lines = mapped_column(JSON, nullable=False, default=list)
    keywords = mapped_column(JSON, nullable=False, default=list)


class DeliveryRecord(Base):
    __tablename__ = "delivery_records"
    subscription_id = mapped_column(Uuid, ForeignKey("subscriptions.id"), nullable=False)
    content_item_id = mapped_column(Uuid, ForeignKey("content_items.id"), nullable=False)
    status = mapped_column(String(30), nullable=False, default="pending")
```

- [ ] **Step 4: 把现有钉钉推送收敛为通用分发器的渠道实现**

```python
dispatcher = ContentDispatchService(session, dingtalk_sender=sender)
dispatcher.dispatch_content_item(content_item_id)
```

- [ ] **Step 5: 运行测试确认内容级推送链路可用**

Run: `pytest tests/unit/test_subscription_matcher_service.py tests/unit/test_content_dispatch_service.py tests/unit/test_weekly_dingtalk_push_service.py tests/unit/test_models.py -v`

Expected: PASS，重复投递会被 `DeliveryRecord` 阻止。

- [ ] **Step 6: 提交**

```bash
git add app/models/subscription.py app/models/delivery_record.py app/services/subscription_matcher_service.py app/services/content_dispatch_service.py app/services/weekly_dingtalk_push_service.py app/models/__init__.py migrations/versions/0005_subscriptions_and_delivery_records.py tests/unit/test_subscription_matcher_service.py tests/unit/test_content_dispatch_service.py tests/unit/test_weekly_dingtalk_push_service.py tests/unit/test_models.py
git commit -m "feat: add subscription matching and delivery records"
```

## Task 5（已完成）: 暴露内容中心与订阅中心的 API / 页面入口

**Files:**
- Create: `app/api/routes_content.py`
- Create: `app/api/routes_subscriptions.py`
- Create: `tests/integration/test_content_api.py`
- Create: `tests/integration/test_subscription_api.py`
- Modify: `app/main.py`
- Modify: `app/api/routes_pages.py`
- Modify: `tests/integration/test_pages.py`
- Test: `tests/integration/test_content_api.py`

- [ ] **Step 1: 写失败测试，先固定最小读取与配置入口**

```python
def test_content_api_lists_content_items(client) -> None:
    response = client.get("/api/content")
    assert response.status_code == 200


def test_subscription_api_creates_rule(client) -> None:
    response = client.post("/api/subscriptions", json={"code": "hr-daily", "channel": "dingtalk"})
    assert response.status_code == 201
```

- [ ] **Step 2: 运行测试确认当前路由不存在**

Run: `pytest tests/integration/test_content_api.py tests/integration/test_subscription_api.py tests/integration/test_pages.py -v`

Expected: FAIL，`/api/content` 和 `/api/subscriptions` 尚未注册。

- [ ] **Step 3: 增加只读内容列表与订阅 CRUD**

```python
@router.get("/api/content")
def list_content(session: Session = Depends(get_db_session)) -> list[dict[str, object]]:
    return ContentQueryService(session).list_recent()
```

- [ ] **Step 4: 在现有页面体系中增加最小入口，不重做 UI 框架**

```python
"<a class='mini-card' href='/content-center'><h3>内容中心</h3></a>"
```

- [ ] **Step 5: 运行集成测试确认主入口可访问**

Run: `pytest tests/integration/test_content_api.py tests/integration/test_subscription_api.py tests/integration/test_pages.py -v`

Expected: PASS，且首页或导航能进入内容中心/订阅页。

- [ ] **Step 6: 提交**

```bash
git add app/api/routes_content.py app/api/routes_subscriptions.py app/main.py app/api/routes_pages.py tests/integration/test_content_api.py tests/integration/test_subscription_api.py tests/integration/test_pages.py
git commit -m "feat: expose content center and subscription endpoints"
```

## Task 6（已完成）: 文档、迁移校验与端到端验收

**Files:**
- Modify: `architecture/2026-04-24-stable-crawling-data-center-architecture.md`
- Modify: `architecture/roadmap/2026-q2-implementation-roadmap.md`
- Modify: `README.md`
- Modify: `tests/test_alembic_migrations.py`
- Modify: `tests/e2e/test_full_smoke.py`
- Test: `tests/test_alembic_migrations.py`

- [ ] **Step 1: 写失败测试，先把迁移链和冒烟链路纳入覆盖**

```python
def test_latest_migration_includes_content_center_tables() -> None:
    assert "subscriptions" in upgraded_table_names
```

- [ ] **Step 2: 运行测试确认迁移与全链路尚未覆盖新增表**

Run: `pytest tests/test_alembic_migrations.py tests/e2e/test_full_smoke.py -v`

Expected: FAIL，新增模型尚未体现在迁移测试和全链路测试中。

- [ ] **Step 3: 更新文档与验收说明**

```markdown
## 内容中心
- 新增 `RawItem` / `ContentItem` / `Subscription` / `DeliveryRecord`
- 新增内容 API 和订阅 API
```

- [ ] **Step 4: 补齐迁移测试与最小端到端场景**

```python
def test_full_smoke_runs_content_pipeline_and_dispatch(...) -> None:
    assert delivery_count >= 1
```

- [ ] **Step 5: 运行最终验收**

Run: `pytest tests/unit/test_auth_state_service.py tests/unit/test_failure_classifier.py tests/unit/test_content_pipeline_service.py tests/unit/test_subscription_matcher_service.py tests/integration/test_content_api.py tests/integration/test_subscription_api.py tests/test_alembic_migrations.py tests/e2e/test_full_smoke.py -v`

Expected: PASS，核心新链路全部通过。

- [ ] **Step 6: 提交**

```bash
git add architecture/2026-04-24-stable-crawling-data-center-architecture.md architecture/roadmap/2026-q2-implementation-roadmap.md README.md tests/test_alembic_migrations.py tests/e2e/test_full_smoke.py
git commit -m "docs: finalize implementation guidance for content center rollout"
```

## 执行顺序约束

| 顺序 | 原因 |
| --- | --- |
| Task 1 -> Task 2 | 先把单用户登录态和失败分类立住，后续调度才有稳定边界 |
| Task 2 -> Task 3 | 内容中心不能建立在不稳定的执行器之上 |
| Task 3 -> Task 4 | 订阅推送必须消费 `ContentItem`，不能直接推原始抓取结果 |
| Task 4 -> Task 5 | 先让后端链路通，再暴露 API / 页面 |
| Task 5 -> Task 6 | 最后再补文档和全链路验收 |

## 实施备注

| 事项 | 说明 |
| --- | --- |
| 兼容策略 | `CollectedItem` 暂不立刻删除，先作为报告兼容层保留一轮迭代 |
| 数据库策略 | 先写 Alembic 迁移，不做跳表直改 |
| UI 策略 | 继续沿用现有页面风格，不在本轮重做前端框架 |
| 登录策略 | 当前计划按单用户运行，不提前引入多账号模型 |
| 桌面壳策略 | 本计划不引入 Electron / Tauri，仅保留后续接入空间 |

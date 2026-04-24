# 多定时调度分组与 B 站封面图通知增强 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让系统支持“一个来源归属一个调度分组、一个分组可挂多个每日定时点”的调度模型，同时把 B 站 `cover_image_url` 入库并在钉钉通知中展示为标题链接、统计行、封面图地址行。

**Architecture:** 保留 `scheduler_settings` 作为全局开关配置，新建 `schedule_plans` 承载每日执行计划；`sources.schedule_group` 定义来源的调度归属，`collection_jobs.schedule_group_scope` 定义本次任务的调度范围。B 站详情增强继续沿用“先抓列表、再按视频详情补字段”的模式，把 `cover_image_url` 与已完成的点赞/评论/播放字段统一入库，并在钉钉消息中优先使用已存储值。

**Tech Stack:** FastAPI, SQLAlchemy ORM, SQLite schema patching, pytest, Bilibili strategy/detail services, DingTalk markdown webhook

---

## 文件结构

| 路径 | 责任 |
|---|---|
| `app/models/schedule_plan.py` | 新的每日调度计划模型 |
| `app/models/source.py` | 新增 `schedule_group` |
| `app/models/job.py` | 新增 `schedule_group_scope` |
| `app/models/item.py` | 新增 `cover_image_url` |
| `app/db.py` | SQLite 补列兼容 `schedule_group`、`schedule_group_scope`、`cover_image_url` |
| `app/schemas/source.py` | 来源表单/API 增加 `schedule_group` |
| `app/services/source_service.py` | 查询调度分组、按调度分组统计启用来源 |
| `app/services/job_service.py` | 新增按调度分组创建任务、按计划创建调度任务 |
| `app/services/scheduler_service.py` | 从单 `daily_time` 改为扫描多条 `schedule_plans` |
| `app/workers/runner.py` | 支持 `schedule_group_scope` 过滤来源 |
| `app/api/routes_pages.py` | `/scheduler` 计划管理、首页按调度分组运行、任务详情范围展示、来源页展示调度分组 |
| `app/api/routes_sources.py` | 简化来源表单接收 `schedule_group` |
| `app/services/bilibili_video_detail_service.py` | 返回 `cover_image_url` |
| `app/services/strategies/bilibili_profile_videos_recent.py` | 把 `cover_image_url` 传给后续入库层 |
| `app/services/report_service.py` | 持久化并更新 `cover_image_url` |
| `app/services/dingtalk_webhook_service.py` | 正文改为 `[标题](url)` + 统计行 + `封面图：...` |
| `tests/unit/test_models.py` | 模型字段覆盖 |
| `tests/unit/test_scheduler_service.py` | 多计划扫描、防重复、空分组跳过 |
| `tests/unit/test_job_service.py` | 按调度分组/计划创建任务 |
| `tests/unit/test_runner.py` | runner 范围过滤优先级 |
| `tests/unit/test_report_service.py` | `cover_image_url` 入库更新 |
| `tests/unit/test_dingtalk_webhook_service.py` | 标题链接、统计行、封面图地址行 |
| `tests/unit/test_strategy_bilibili_profile_videos_recent.py` | B 站策略补充封面图地址 |
| `tests/integration/test_scheduler_page.py` | 调度计划页面增删改查 |
| `tests/integration/test_pages.py` | 首页按调度分组运行入口、来源页展示 |

## 实施约束

| 项目 | 约束 |
|---|---|
| 第一版调度分组 | `Source.schedule_group` 仅支持单值，`None` 表示不参与定时 |
| 计划触发 | 按 `schedule_plans.id` 每天只触发一次，不做全局分组去重 |
| 旧入口 | 全量、国内、国外手动运行全部保留 |
| 数据迁移 | 不自动把 `source_group` 映射成 `schedule_group` |
| 封面图 | 第一版只保存 URL，不下载本地文件 |

### Task 1: 扩展模型与数据库兼容层

**Files:**
- Create: `app/models/schedule_plan.py`
- Modify: `app/models/source.py`
- Modify: `app/models/job.py`
- Modify: `app/models/item.py`
- Modify: `app/db.py`
- Test: `tests/unit/test_models.py`

- [ ] **Step 1: 先写模型失败测试**

```python
from app.models.schedule_plan import SchedulePlan

def test_schedule_plan_model_keeps_required_columns() -> None:
    columns = SchedulePlan.__table__.columns
    assert "run_time" in columns
    assert "schedule_group" in columns
    assert "last_triggered_on" in columns

def test_source_job_item_models_expose_schedule_and_cover_columns() -> None:
    assert "schedule_group" in Source.__table__.columns
    assert "schedule_group_scope" in CollectionJob.__table__.columns
    assert "cover_image_url" in CollectedItem.__table__.columns
```

- [ ] **Step 2: 运行测试确认当前失败**

Run: `pytest tests/unit/test_models.py -v`
Expected: FAIL，报 `SchedulePlan` 不存在或新字段缺失。

- [ ] **Step 3: 实现最小模型与 SQLite 补列**

```python
class SchedulePlan(Base):
    __tablename__ = "schedule_plans"
    id = mapped_column(Integer, primary_key=True)
    enabled = mapped_column(Boolean, nullable=False, default=True)
    run_time = mapped_column(String(5), nullable=False)
    schedule_group = mapped_column(String(100), nullable=False)
    last_triggered_on = mapped_column(Date, nullable=True)
```

```python
schedule_group: Mapped[str | None] = mapped_column(String(100), nullable=True)
schedule_group_scope: Mapped[str | None] = mapped_column(String(100), nullable=True)
cover_image_url: Mapped[str | None] = mapped_column(Text, nullable=True)
```

- [ ] **Step 4: 补齐 schema compatibility 并确认模型测试通过**

Run: `pytest tests/unit/test_models.py -v`
Expected: PASS，且 SQLite 老库在启动时可补齐新增列。

- [ ] **Step 5: 提交本任务改动**

```bash
git add app/models/schedule_plan.py app/models/source.py app/models/job.py app/models/item.py app/db.py tests/unit/test_models.py
git commit -m "feat: add schedule plan and cover image schema"
```

### Task 2: 重构调度服务为多计划扫描

**Files:**
- Create: `app/services/schedule_plan_service.py`
- Modify: `app/services/scheduler_service.py`
- Modify: `app/models/scheduler_setting.py`
- Test: `tests/unit/test_scheduler_service.py`

- [ ] **Step 1: 先补多计划调度测试**

```python
def test_scheduler_service_creates_job_for_due_plan_once_per_day(tmp_path) -> None:
    # 创建 enabled=True 的计划 run_time=08:00、schedule_group="morning"
    # 创建一个 schedule_group="morning" 的启用来源
    created = SchedulerService(session).run_due_jobs(datetime(2026, 4, 23, 8, 0, 0))
    assert len(created) == 1

def test_scheduler_service_skips_plan_without_enabled_sources(tmp_path) -> None:
    # 计划存在但分组下无启用来源
    created = SchedulerService(session).run_due_jobs(datetime(2026, 4, 23, 8, 0, 0))
    assert created == []
```

- [ ] **Step 2: 运行失败用例确认旧逻辑不满足**

Run: `pytest tests/unit/test_scheduler_service.py -v`
Expected: FAIL，旧实现返回单个 job 或仍依赖 `daily_time`。

- [ ] **Step 3: 实现计划扫描与计划级防重**

```python
def run_due_jobs(self, now: datetime) -> list[CollectionJob]:
    settings = self.get_settings()
    if not settings.enabled:
        return []
    due_plans = self.plan_service.list_due_plans(now)
    created_jobs = []
    for plan in due_plans:
        job = JobService(self.session).create_scheduled_job_for_plan(plan)
        if job is None:
            continue
        plan.last_triggered_on = now.date()
        created_jobs.append(job)
    self.session.commit()
    return created_jobs
```

- [ ] **Step 4: 保留旧 `daily_time` 兼容语义但不再作为核心执行入口**

Run: `pytest tests/unit/test_scheduler_service.py -v`
Expected: PASS，覆盖“禁用不跑、同计划同日不重复、空分组跳过、同组多时间点允许”。

- [ ] **Step 5: 提交本任务改动**

```bash
git add app/services/schedule_plan_service.py app/services/scheduler_service.py app/models/scheduler_setting.py tests/unit/test_scheduler_service.py
git commit -m "feat: support multiple grouped schedule plans"
```

### Task 3: 让任务创建与执行支持 `schedule_group_scope`

**Files:**
- Modify: `app/services/job_service.py`
- Modify: `app/workers/runner.py`
- Test: `tests/unit/test_job_service.py`
- Test: `tests/unit/test_runner.py`

- [ ] **Step 1: 先写 JobService 和 Runner 的失败测试**

```python
def test_job_service_creates_manual_job_for_schedule_group(tmp_path) -> None:
    job = JobService(session).create_manual_job_for_schedule_group("morning")
    assert job.schedule_group_scope == "morning"
    assert job.source_group_scope is None

def test_runner_executes_only_sources_in_schedule_group_scope(tmp_path) -> None:
    # 创建 morning / evening 两个来源
    # 创建 schedule_group_scope="morning" 的任务
    assert executed_names == ["早报来源"]
```

- [ ] **Step 2: 运行对应测试确认失败**

Run: `pytest tests/unit/test_job_service.py tests/unit/test_runner.py -v`
Expected: FAIL，`create_manual_job_for_schedule_group` 不存在，runner 也不会按 `schedule_group_scope` 过滤。

- [ ] **Step 3: 实现按调度分组建任务与执行过滤**

```python
def create_manual_job_for_schedule_group(self, schedule_group: str) -> CollectionJob | None:
    total = self._count_enabled_sources(schedule_group=schedule_group)
    if not total:
        return None
    job = CollectionJob(
        trigger_type="manual",
        status="pending",
        schedule_group_scope=schedule_group,
        total_sources=total,
    )
```

```python
if job.schedule_group_scope:
    statement = statement.where(Source.schedule_group == job.schedule_group_scope)
elif job.source_group_scope:
    statement = statement.where(Source.source_group == job.source_group_scope)
```

- [ ] **Step 4: 确认任务创建和执行路径都通过**

Run: `pytest tests/unit/test_job_service.py tests/unit/test_runner.py -v`
Expected: PASS，且旧的 `source_group_scope` 逻辑不回归。

- [ ] **Step 5: 提交本任务改动**

```bash
git add app/services/job_service.py app/workers/runner.py tests/unit/test_job_service.py tests/unit/test_runner.py
git commit -m "feat: add schedule group scoped jobs"
```

### Task 4: 扩展来源 schema、服务和表单输入

**Files:**
- Modify: `app/schemas/source.py`
- Modify: `app/services/source_service.py`
- Modify: `app/api/routes_sources.py`
- Modify: `app/api/routes_pages.py`
- Test: `tests/integration/test_pages.py`

- [ ] **Step 1: 先写来源页与来源表单失败测试**

```python
def test_new_source_form_accepts_optional_schedule_group(tmp_path) -> None:
    response = client.post("/api/sources/form", data={
        "entry_url": "https://space.bilibili.com/4186021",
        "source_group": "domestic",
        "schedule_group": "morning",
        "max_items": "30",
    })
    assert response.status_code == 303

def test_sources_page_shows_schedule_group_hint(tmp_path) -> None:
    assert "调度分组" in response.text
    assert "未参与定时任务" in response.text
```

- [ ] **Step 2: 运行页面测试确认失败**

Run: `pytest tests/integration/test_pages.py -v`
Expected: FAIL，页面与 schema 还没有 `schedule_group` 字段。

- [ ] **Step 3: 实现 schema、服务查询与页面表单字段**

```python
class SourceCreate(BaseModel):
    schedule_group: str | None = Field(default=None, max_length=100)

class SourceUpdate(BaseModel):
    schedule_group: str | None = Field(default=None, max_length=100)
```

```python
def list_distinct_schedule_groups(self) -> list[str]:
    statement = (
        select(Source.schedule_group)
        .where(Source.schedule_group.is_not(None))
        .distinct()
        .order_by(Source.schedule_group.asc())
    )
    return [value for value in self.session.scalars(statement).all() if value]
```

- [ ] **Step 4: 确认来源创建、编辑和列表展示通过**

Run: `pytest tests/integration/test_pages.py -v`
Expected: PASS，来源表单允许留空；留空时显示“不参与定时任务”。

- [ ] **Step 5: 提交本任务改动**

```bash
git add app/schemas/source.py app/services/source_service.py app/api/routes_sources.py app/api/routes_pages.py tests/integration/test_pages.py
git commit -m "feat: add schedule group to source forms"
```

### Task 5: 把 `/scheduler` 改造成计划管理页

**Files:**
- Modify: `app/api/routes_pages.py`
- Modify: `app/services/schedule_plan_service.py`
- Test: `tests/integration/test_scheduler_page.py`

- [ ] **Step 1: 先写调度页失败测试**

```python
def test_scheduler_page_lists_schedule_plans(tmp_path) -> None:
    response = client.get("/scheduler")
    assert "调度计划" in response.text
    assert "schedule_group" in response.text or "调度分组" in response.text

def test_scheduler_page_can_create_schedule_plan(tmp_path) -> None:
    response = client.post("/scheduler/plans", data={
        "enabled": "true",
        "run_time": "08:00",
        "schedule_group": "morning",
    }, follow_redirects=True)
    assert "08:00" in response.text
    assert "morning" in response.text
```

- [ ] **Step 2: 运行调度页测试确认失败**

Run: `pytest tests/integration/test_scheduler_page.py -v`
Expected: FAIL，旧页面仍展示 `daily_time` 单表单。

- [ ] **Step 3: 实现计划列表、新增、编辑、删除与说明文案**

```python
@router.post("/scheduler/plans")
async def create_schedule_plan(...): ...

@router.post("/scheduler/plans/{plan_id}")
async def update_schedule_plan(...): ...

@router.post("/scheduler/plans/{plan_id}/delete")
def delete_schedule_plan(...): ...
```

```python
render_panel("调度计划", plan_table + create_form)
```

- [ ] **Step 4: 回归页面行为**

Run: `pytest tests/integration/test_scheduler_page.py -v`
Expected: PASS，页面明确提示“未分组来源不会参与任何定时任务”。

- [ ] **Step 5: 提交本任务改动**

```bash
git add app/api/routes_pages.py app/services/schedule_plan_service.py tests/integration/test_scheduler_page.py
git commit -m "feat: add grouped schedule plan management page"
```

### Task 6: 首页新增按调度分组运行入口，任务详情展示新范围

**Files:**
- Modify: `app/api/routes_pages.py`
- Modify: `app/services/job_service.py`
- Test: `tests/integration/test_pages.py`

- [ ] **Step 1: 先写首页和任务详情失败测试**

```python
def test_home_page_can_run_job_for_schedule_group(tmp_path) -> None:
    response = client.post("/jobs/run/schedule-group/morning")
    assert response.status_code == 303

def test_job_detail_page_shows_schedule_group_scope_badge(tmp_path) -> None:
    assert "执行范围：调度分组 morning" in response.text
```

- [ ] **Step 2: 运行页面测试确认失败**

Run: `pytest tests/integration/test_pages.py -v`
Expected: FAIL，旧路由与任务详情只认识 `source_group_scope`。

- [ ] **Step 3: 新增首页入口与详情页范围标签**

```python
@router.post("/jobs/run/schedule-group/{schedule_group}")
def run_schedule_group_job(...):
    job = JobService(session).create_manual_job_for_schedule_group(schedule_group)
```

```python
def _job_scope_label(job) -> str:
    if job.schedule_group_scope:
        return f"执行范围：调度分组 {job.schedule_group_scope}"
```

- [ ] **Step 4: 确认首页和详情页通过**

Run: `pytest tests/integration/test_pages.py -v`
Expected: PASS，分组为空时返回首页提示，旧国内/国外入口仍可用。

- [ ] **Step 5: 提交本任务改动**

```bash
git add app/api/routes_pages.py app/services/job_service.py tests/integration/test_pages.py
git commit -m "feat: add manual run entry for schedule groups"
```

### Task 7: 把 B 站 `cover_image_url` 接入策略与报告入库

**Files:**
- Modify: `app/services/bilibili_video_detail_service.py`
- Modify: `app/services/strategies/bilibili_profile_videos_recent.py`
- Modify: `app/services/report_service.py`
- Test: `tests/unit/test_strategy_bilibili_profile_videos_recent.py`
- Test: `tests/unit/test_report_service.py`

- [ ] **Step 1: 先写失败测试覆盖封面图地址**

```python
def test_bilibili_profile_strategy_enriches_items_with_cover_image_url() -> None:
    strategy = BilibiliProfileVideosRecentStrategy(
        runner=runner,
        detail_fetcher=lambda url: {"cover_image_url": "https://i0.hdslb.com/demo.jpg"},
    )
    assert items[0]["cover_image_url"] == "https://i0.hdslb.com/demo.jpg"

def test_report_service_persists_cover_image_url_and_updates_existing_item(tmp_path) -> None:
    assert items[0].cover_image_url == "https://i0.hdslb.com/demo-new.jpg"
```

- [ ] **Step 2: 运行这两组测试确认失败**

Run: `pytest tests/unit/test_strategy_bilibili_profile_videos_recent.py tests/unit/test_report_service.py -v`
Expected: FAIL，详情字段与入库逻辑还未包含 `cover_image_url`。

- [ ] **Step 3: 最小实现详情透传与 upsert**

```python
for key in ("author", "published_at_text", "like_count", "reply_count", "view_count", "cover_image_url"):
    value = detail.get(key)
    if value is not None:
        enriched[key] = value
```

```python
item.cover_image_url = payload.get("cover_image_url") or item.cover_image_url
```

- [ ] **Step 4: 确认策略和报告层通过**

Run: `pytest tests/unit/test_strategy_bilibili_profile_videos_recent.py tests/unit/test_report_service.py -v`
Expected: PASS，重复采集时用最新封面图地址覆盖旧值。

- [ ] **Step 5: 提交本任务改动**

```bash
git add app/services/bilibili_video_detail_service.py app/services/strategies/bilibili_profile_videos_recent.py app/services/report_service.py tests/unit/test_strategy_bilibili_profile_videos_recent.py tests/unit/test_report_service.py
git commit -m "feat: persist bilibili cover image url"
```

### Task 8: 调整钉钉通知正文为标题链接、统计行、封面图地址行

**Files:**
- Modify: `app/services/dingtalk_webhook_service.py`
- Test: `tests/unit/test_dingtalk_webhook_service.py`

- [ ] **Step 1: 先写失败测试锁定样式**

```python
def test_dingtalk_formats_item_as_clickable_title_stats_and_cover_line(...) -> None:
    text = service._build_source_markdown_text(job, "初夏ChuXXia", [item])
    assert "1. [PRAGMATA/识质存在](https://www.bilibili.com/video/BV1...)" in text
    assert "发布时间：2026-04-22 11:57 | 点赞：3689 | 评论：206 | 播放：61317" in text
    assert "封面图：https://i0.hdslb.com/demo.jpg" in text
```

- [ ] **Step 2: 运行钉钉测试确认失败**

Run: `pytest tests/unit/test_dingtalk_webhook_service.py -v`
Expected: FAIL，当前正文仍是标题行 + URL 行，不展示封面图地址。

- [ ] **Step 3: 最小实现正文与回退策略**

```python
def _build_item_title_line(self, item: CollectedItem) -> str:
    title = self._compact_text(item.title)
    url = self._optional_compact_text(item.url)
    return f"[{title}]({url})" if url else title

def _format_item_lines(self, items: list[CollectedItem]) -> list[str]:
    lines.append(f"{index}. {self._build_item_title_line(item)}")
    lines.append("")
    lines.append(self._build_item_stats_line(item))
    cover_line = self._build_item_cover_line(item, override)
    if cover_line:
        lines.append("")
        lines.append(cover_line)
```

- [ ] **Step 4: 确认通知测试通过**

Run: `pytest tests/unit/test_dingtalk_webhook_service.py -v`
Expected: PASS，且“若标题不含热点报告则补 `热点报告 {label}`”规则继续成立。

- [ ] **Step 5: 提交本任务改动**

```bash
git add app/services/dingtalk_webhook_service.py tests/unit/test_dingtalk_webhook_service.py
git commit -m "feat: show cover url in dingtalk bilibili notifications"
```

### Task 9: 做一次聚合验证并记录回归范围

**Files:**
- Modify: `docs/superpowers/plans/2026-04-23-multi-schedule-grouped-runs.md`
- Verify: `tests/unit/test_models.py`
- Verify: `tests/unit/test_scheduler_service.py`
- Verify: `tests/unit/test_job_service.py`
- Verify: `tests/unit/test_runner.py`
- Verify: `tests/unit/test_report_service.py`
- Verify: `tests/unit/test_dingtalk_webhook_service.py`
- Verify: `tests/unit/test_strategy_bilibili_profile_videos_recent.py`
- Verify: `tests/integration/test_scheduler_page.py`
- Verify: `tests/integration/test_pages.py`

- [ ] **Step 1: 跑调度与任务主链路测试**

Run: `pytest tests/unit/test_models.py tests/unit/test_scheduler_service.py tests/unit/test_job_service.py tests/unit/test_runner.py -v`
Expected: PASS

- [ ] **Step 2: 跑 B 站与通知链路测试**

Run: `pytest tests/unit/test_report_service.py tests/unit/test_dingtalk_webhook_service.py tests/unit/test_strategy_bilibili_profile_videos_recent.py -v`
Expected: PASS

- [ ] **Step 3: 跑页面测试**

Run: `pytest tests/integration/test_scheduler_page.py tests/integration/test_pages.py -v`
Expected: PASS

- [ ] **Step 4: 跑最终回归集合**

Run: `pytest tests/unit/test_models.py tests/unit/test_scheduler_service.py tests/unit/test_job_service.py tests/unit/test_runner.py tests/unit/test_report_service.py tests/unit/test_dingtalk_webhook_service.py tests/unit/test_strategy_bilibili_profile_videos_recent.py tests/integration/test_scheduler_page.py tests/integration/test_pages.py -v`
Expected: PASS；若失败，先修失败模块再重新执行该集合。

- [ ] **Step 5: 仅在工作区干净或可精确选择路径时提交**

```bash
git add app/models/schedule_plan.py app/models/source.py app/models/job.py app/models/item.py app/db.py app/schemas/source.py app/services/source_service.py app/services/job_service.py app/services/schedule_plan_service.py app/services/scheduler_service.py app/workers/runner.py app/api/routes_pages.py app/api/routes_sources.py app/services/bilibili_video_detail_service.py app/services/strategies/bilibili_profile_videos_recent.py app/services/report_service.py app/services/dingtalk_webhook_service.py tests/unit/test_models.py tests/unit/test_scheduler_service.py tests/unit/test_job_service.py tests/unit/test_runner.py tests/unit/test_report_service.py tests/unit/test_dingtalk_webhook_service.py tests/unit/test_strategy_bilibili_profile_videos_recent.py tests/integration/test_scheduler_page.py tests/integration/test_pages.py
git commit -m "feat: add grouped schedules and bilibili cover image notifications"
```

## 实施备注

| 项目 | 说明 |
|---|---|
| `daily_time` | 保留字段，只用于兼容旧配置，不再驱动核心调度 |
| `schedule_group` 值域 | 第一版使用普通字符串，不做固定枚举，方便运营直接录入 |
| 未分组来源 | 手动“采集全部”仍会执行；定时计划和“按调度分组运行”不会命中 |
| 封面图通知 | 如果 `cover_image_url` 缺失，则省略该行，不为了通知再额外阻塞任务 |
| 提交策略 | 当前仓库是脏工作区，执行时只能按本计划涉及路径精确 `git add`，不能做全量提交 |

## 执行完成定义

| 检查项 | 完成标准 |
|---|---|
| 多定时计划 | `/scheduler` 可维护多条 `run_time + schedule_group` 规则 |
| 分组执行 | 定时任务与手动入口都能只跑对应 `schedule_group` 来源 |
| 兼容旧逻辑 | 全量、国内、国外入口不回归 |
| B 站封面图 | `CollectedItem.cover_image_url` 能写入并更新 |
| 钉钉样式 | 单条正文为标题链接、统计行、封面图地址行 |
| 回归测试 | 本计划列出的 pytest 集合全部通过 |

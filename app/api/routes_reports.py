from __future__ import annotations

from datetime import datetime
from html import escape
from urllib.parse import parse_qs
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.api.routes_sources import get_db_session
from app.config import get_settings
from app.models.item import CollectedItem
from app.schemas.report import ReportRead
from app.services.weekly_dingtalk_push_service import WeeklyDingTalkPushService
from app.services.weekly_rating_service import GRADE_OPTIONS, WeeklyRatingService
from app.services.published_at_display import format_published_at
from app.services.report_service import ReportService
from app.services.weekly_cover_cache_service import WeeklyCoverCacheService
from app.services.weekly_hot_service import WeeklyHotService
from app.ui.page_theme import render_page, render_page_header, render_panel

router = APIRouter(tags=["reports"])

REPORTS_TITLE = "历史报告"
REPORT_DETAIL_TITLE = "报告预览"
GLOBAL_REPORT_TITLE = "全局热点总报告"
WEEKLY_TITLE = "最近一周热点"


def _button_link(label: str, href: str, variant: str = "button-secondary") -> str:
    return f"<a class='button {variant}' href='{escape(href, quote=True)}'>{escape(label)}</a>"


def _format_metric(value: int | None) -> str:
    return "--" if value is None else str(value)


def _render_weekly_cover_cell(item) -> str:
    cover_image_url = str(getattr(item, "cover_image_url", "") or "").strip()
    if not cover_image_url:
        return "<span class='muted-text'>暂无封面</span>"
    title = str(getattr(item, "title", "") or "封面预览")
    return (
        f"<img class='weekly-cover' src='/weekly/covers/{escape(str(getattr(item, 'id')), quote=True)}' "
        f"alt='{escape(title, quote=True)}' loading='lazy' />"
    )


def _render_weekly_title_cell(item) -> str:
    title = str(getattr(item, "title", "") or "未命名内容")
    url = str(getattr(item, "url", "") or "").strip()
    if not url:
        return f"<span class='weekly-title-text'>{escape(title)}</span>"
    return (
        f"<a class='weekly-title-link' href='{escape(url, quote=True)}' target='_blank' rel='noreferrer'>"
        f"{escape(title)}</a>"
    )


def _render_grade_select(item) -> str:
    current_grade = str(getattr(item, "manual_grade", "") or "")
    options = ["<option value=''>未选择</option>"]
    for grade in GRADE_OPTIONS:
        selected = " selected" if current_grade == grade else ""
        options.append(f"<option value='{escape(grade, quote=True)}'{selected}>{escape(grade)}</option>")
    return (
        f"<select class='weekly-grade-select' name='grade_{escape(str(getattr(item, 'id')), quote=True)}'>"
        f"{''.join(options)}</select>"
    )


def _render_push_status(item) -> str:
    pushed_at = getattr(item, "pushed_to_dingtalk_at", None)
    if pushed_at is None:
        return "<span class='weekly-status weekly-status-pending'>未推送</span>"
    return f"<span class='weekly-status weekly-status-sent'>已推送 {escape(pushed_at.strftime('%Y-%m-%d %H:%M'))}</span>"


def _render_weekly_action_bar(threshold_grade: str) -> str:
    return f"""
    <div class='weekly-actions'>
      <div class='weekly-threshold-banner'>
        <strong>当前推送阈值：{escape(threshold_grade)}</strong>
        <span>推荐评分仅供参考；人工评分达到该等级及以上时，点击“批量推送达标项”才会发到钉钉群。</span>
      </div>
      <div class='weekly-bulk-tools'>
        <label class='weekly-bulk-label' for='weekly-bulk-grade'>批量设为</label>
        <select id='weekly-bulk-grade' class='weekly-grade-select'>
          <option value=''>选择等级</option>
          {''.join(f"<option value='{escape(grade, quote=True)}'>{escape(grade)}</option>" for grade in GRADE_OPTIONS)}
        </select>
        <button class='button-secondary' type='button' onclick='weeklySetAllGrades()'>应用到本页</button>
        <button class='button-secondary' type='button' onclick='weeklyClearAllGrades()'>清空本页评分</button>
      </div>
      <div class='page-actions'>
        <button class='button-primary' type='submit'>保存评分</button>
      </div>
    </div>
    """


def _render_weekly_feedback(
    *,
    ratings_saved: bool,
    pushed_count: int | None,
    push_empty: bool,
) -> str:
    messages: list[str] = []
    if ratings_saved:
        messages.append("<p class='helper-note'>评分已保存。</p>")
    if pushed_count is not None:
        messages.append(f"<p class='helper-note'>已推送 {pushed_count} 条达标内容到钉钉。</p>")
    elif push_empty:
        messages.append("<p class='helper-note'>当前没有达到阈值且未推送的内容。</p>")
    return "".join(messages)


def _render_weekly_table(items: list[object], *, threshold_grade: str) -> str:
    if not items:
        return "<div class='empty-state'>最近一周暂无采集数据，先执行一次抓取即可在这里查看。</div>"

    rows = []
    for index, item in enumerate(items, start=1):
        rows.append(
            "<tr>"
            f"<td class='weekly-order-cell'>{index}</td>"
            f"<td>{_render_weekly_title_cell(item)}</td>"
            f"<td>{_render_weekly_cover_cell(item)}</td>"
            f"<td>{escape(_format_metric(getattr(item, 'like_count', None)))}</td>"
            f"<td>{escape(_format_metric(getattr(item, 'view_count', None)))}</td>"
            f"<td>{escape(_format_metric(getattr(item, 'reply_count', None)))}</td>"
            f"<td>{escape(format_published_at(getattr(item, 'published_at', None), getattr(item, 'published_at_text', None)))}</td>"
            f"<td>{escape(str(getattr(item, 'recommended_grade', None) or '--'))}</td>"
            f"<td>{_render_grade_select(item)}</td>"
            f"<td>{_render_push_status(item)}</td>"
            "</tr>"
        )
    return (
        "<form method='post' action='/weekly/ratings'>"
        f"{_render_weekly_action_bar(threshold_grade)}"
        "<div class='data-table-wrapper'>"
        "<table class='data-table weekly-hot-table'>"
        "<thead><tr><th>序号</th><th>标题</th><th>封面预览图</th><th>点赞数</th><th>播放量</th><th>评论数</th><th>发布时间</th><th>推荐评分</th><th>人工评分</th><th>推送状态</th></tr></thead>"
        f"<tbody>{''.join(rows)}</tbody>"
        "</table>"
        "</div>"
        "<div class='page-actions'><button class='button-primary' type='submit'>保存评分</button></div>"
        "</form>"
    )


def _render_weekly_page_script() -> str:
    return """
    <script>
    function weeklySetAllGrades() {
      const bulkSelect = document.getElementById('weekly-bulk-grade');
      if (!bulkSelect || !bulkSelect.value) {
        return;
      }
      document.querySelectorAll('.weekly-grade-select[name^="grade_"]').forEach((select) => {
        select.value = bulkSelect.value;
      });
    }

    function weeklyClearAllGrades() {
      document.querySelectorAll('.weekly-grade-select[name^="grade_"]').forEach((select) => {
        select.value = '';
      });
    }
    </script>
    """


@router.get("/api/reports", response_model=list[ReportRead])
def list_reports_api(session: Session = Depends(get_db_session)) -> list[ReportRead]:
    service = ReportService(session)
    return [ReportRead.model_validate(report) for report in service.list_reports()]


@router.get("/api/reports/{report_id}/download")
def download_report(report_id: str, format: str = Query("md", pattern="^(md|docx)$"), session: Session = Depends(get_db_session)) -> FileResponse:
    service = ReportService(session)
    report = service.get_report(report_id)
    if report is None:
        raise HTTPException(status_code=404, detail="report not found")

    if format == "docx":
        return FileResponse(report.docx_path, media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document")
    return FileResponse(report.markdown_path, media_type="text/markdown; charset=utf-8")


@router.get("/reports", response_class=HTMLResponse)
def reports_page(session: Session = Depends(get_db_session)) -> str:
    service = ReportService(session)
    report = next(iter(service.list_reports(limit=1)), None)

    if report is None:
        report_content = "<div class='empty-state'>暂无报告，先返回首页执行一次采集即可生成首份总报告。</div>"
    else:
        report_content = f"""
        <div class='helper-note'>每次任务完成后，系统都会刷新同一份总报告，并保留历史条目的状态标记。</div>
        <div class='report-links'>
          {_button_link('查看报告', f'/reports/{report.id}', 'button-primary')}
          {_button_link('下载 Markdown', f'/api/reports/{report.id}/download?format=md')}
          {_button_link('下载 DOCX', f'/api/reports/{report.id}/download?format=docx')}
        </div>
        """

    content = (
        render_page_header(
            eyebrow='Reports',
            title=REPORTS_TITLE,
            subtitle='集中查看最近生成的全局热点报告，并继续从这里进入下载与预览。',
            actions=_button_link('返回首页', '/'),
        )
        + render_panel(GLOBAL_REPORT_TITLE, report_content, extra_class='reports-overview-panel')
    )
    return render_page(title=REPORTS_TITLE, content=content, body_class='theme-dark')


@router.get("/weekly", response_class=HTMLResponse)
def weekly_page(request: Request, session: Session = Depends(get_db_session)) -> str:
    items = WeeklyHotService(session).list_recent_items(now=datetime.utcnow())
    rating_service = WeeklyRatingService(session)
    rating_service.assign_recommended_grades(items)
    settings = get_settings()
    pushed_count_param = request.query_params.get("pushed_count")
    pushed_count = int(pushed_count_param) if pushed_count_param and pushed_count_param.isdigit() else None
    ratings_saved = request.query_params.get("ratings_saved") == "1"
    push_empty = request.query_params.get("push_empty") == "1"
    threshold_grade = rating_service.normalize_grade(settings.weekly_grade_push_threshold) or "B+"
    content = (
        render_page_header(
            eyebrow='Weekly',
            title=WEEKLY_TITLE,
            subtitle='固定展示最近 7 天采集到的热点内容，标题可直接点击跳转，按发布时间倒序排列。',
            actions=_button_link('返回首页', '/') + _button_link(REPORTS_TITLE, '/reports'),
        )
        + render_panel(
            WEEKLY_TITLE,
            _render_weekly_feedback(ratings_saved=ratings_saved, pushed_count=pushed_count, push_empty=push_empty)
            + "<div class='helper-note'>仅展示最近 7 天首次抓到的内容；无封面时会显示占位文案。</div>"
            + "<form method='post' action='/weekly/push' class='weekly-push-form'><div class='page-actions'><button class='button-secondary' type='submit'>批量推送达标项</button></div></form>"
            + _render_weekly_table(items, threshold_grade=threshold_grade)
            + _render_weekly_page_script(),
            extra_class='weekly-hot-panel',
        )
    )
    return render_page(title=WEEKLY_TITLE, content=content, body_class='theme-dark')


@router.post("/weekly/ratings")
async def save_weekly_ratings(request: Request, session: Session = Depends(get_db_session)) -> RedirectResponse:
    form_data = parse_qs((await request.body()).decode("utf-8"))
    grades_by_item_id = {
        key.removeprefix("grade_"): values[0] if values else ""
        for key, values in form_data.items()
        if key.startswith("grade_")
    }
    WeeklyRatingService(session).save_manual_grades(grades_by_item_id)
    return RedirectResponse(url="/weekly?ratings_saved=1", status_code=303)


@router.post("/weekly/push")
async def push_weekly_items(session: Session = Depends(get_db_session)) -> RedirectResponse:
    items = WeeklyHotService(session).list_recent_items(now=datetime.utcnow())
    WeeklyRatingService(session).refresh_recommended_grades(items)
    pushed_count = WeeklyDingTalkPushService(session).push_items([item.id for item in items])
    if pushed_count == 0:
        return RedirectResponse(url="/weekly?push_empty=1", status_code=303)
    return RedirectResponse(url=f"/weekly?pushed_count={pushed_count}", status_code=303)


@router.get("/weekly/covers/{item_id}")
def weekly_cover_image(item_id: str, session: Session = Depends(get_db_session)) -> FileResponse:
    try:
        item_uuid = UUID(item_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="cover not found") from exc

    item = session.get(CollectedItem, item_uuid)
    if item is None:
        raise HTTPException(status_code=404, detail="cover not found")

    cached_path = WeeklyCoverCacheService(session).get_cached_path(item)
    if cached_path is None or not cached_path.exists():
        raise HTTPException(status_code=404, detail="cover not found")

    return FileResponse(cached_path)


@router.get("/reports/{report_id}", response_class=HTMLResponse)
def report_detail_page(report_id: str, session: Session = Depends(get_db_session)) -> str:
    service = ReportService(session)
    report = service.get_report(report_id)
    if report is None:
        raise HTTPException(status_code=404, detail="report not found")

    markdown_content = escape(service.read_markdown(report))
    preview = f"<pre class='report-preview'>{markdown_content}</pre>"
    content = (
        render_page_header(
            eyebrow='Report Detail',
            title=REPORT_DETAIL_TITLE,
            subtitle='保持原有 Markdown 预览方式，并统一到首页同一套深色页面结构。',
            actions=(
                _button_link('返回首页', '/')
                + _button_link('下载 Markdown', f'/api/reports/{report.id}/download?format=md')
                + _button_link('下载 DOCX', f'/api/reports/{report.id}/download?format=docx', 'button-primary')
            ),
        )
        + render_panel(GLOBAL_REPORT_TITLE, preview, extra_class='report-preview-panel')
    )
    return render_page(title=REPORT_DETAIL_TITLE, content=content, body_class='theme-dark')

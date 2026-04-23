from __future__ import annotations

from datetime import datetime
from html import escape
from urllib.parse import parse_qs

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.api.routes_sources import get_db_session
from app.schemas.source import SourceUpdate
from app.services.app_env_service import AppEnvService
from app.services.bilibili_auth_service import BilibiliBrowserAuthService
from app.services.job_service import JobService
from app.services.scheduler_service import SchedulerService
from app.services.source_service import SourceService
from app.ui.page_theme import render_badge, render_page, render_page_header, render_panel, render_stat_card

router = APIRouter(tags=["pages"])

APP_TITLE = "\u70ed\u70b9\u4fe1\u606f\u91c7\u96c6\u7cfb\u7edf"
DASHBOARD_TITLE = "\u70ed\u70b9\u4fe1\u53f7\u603b\u89c8"
RUN_NOW = "\u7acb\u5373\u91c7\u96c6"
SOURCES_TITLE = "\u91c7\u96c6\u6e90\u7ba1\u7406"
REPORTS_TITLE = "\u5386\u53f2\u62a5\u544a"
SCHEDULER_TITLE = "\u5b9a\u65f6\u8c03\u5ea6"
NEW_SOURCE_TITLE = "\u65b0\u589e\u91c7\u96c6\u6e90"
JOB_DETAIL_TITLE = "\u4efb\u52a1\u8be6\u60c5"
RECENT_JOBS_TITLE = "\u6700\u8fd1\u4efb\u52a1"
QUICK_ACTIONS_TITLE = "\u5feb\u6377\u5165\u53e3"
TASK_PROGRESS_TITLE = "\u4efb\u52a1\u8fdb\u5ea6"
TASK_LOGS_TITLE = "\u4efb\u52a1\u65e5\u5fd7"
SETTINGS_TITLE = "\u8c03\u5ea6\u8bbe\u7f6e"
JOB_REPORTS_TITLE = "\u62a5\u544a\u4e0e\u72b6\u6001"
BASE_CONFIG_TITLE = "\u57fa\u7840\u914d\u7f6e"
SOURCE_CONFIG_ERROR = "\u6765\u6e90\u914d\u7f6e\u9519\u8bef"
LATEST_ERROR = "\u6700\u8fd1\u9519\u8bef"
DIAGNOSTIC_SUMMARY_TITLE = "\u8bca\u65ad\u6458\u8981"
ACTIVE_SOURCES_LABEL = "\u6d3b\u8dc3\u6765\u6e90"
ACTIVE_SOURCES_META = "\u8986\u76d6\u5f53\u524d\u542f\u7528\u7684\u91c7\u96c6\u5165\u53e3"
LATEST_JOB_META = "\u6700\u65b0\u4e00\u6b21\u8fd0\u884c\u72b6\u6001"
REPORT_ENTRY_LABEL = "\u62a5\u544a\u5165\u53e3"
REPORT_ENTRY_VALUE = "2\u79cd"
REPORT_ENTRY_META = "Markdown \u4e0e DOCX \u5747\u53ef\u5bfc\u51fa"
SCHEDULER_STATUS_LABEL = "\u8c03\u5ea6\u72b6\u6001"
SCHEDULER_STATUS_VALUE = "\u5728\u7ebf"
SCHEDULER_STATUS_META = "\u53ef\u8fdb\u5165\u8c03\u5ea6\u9875\u8c03\u6574\u6bcf\u65e5\u6267\u884c\u65f6\u95f4"
CURRENT_STATUS_LABEL = "\u5f53\u524d\u72b6\u6001"
CURRENT_STATUS_META = "\u5b9a\u65f6\u6267\u884c\u5f00\u5173"
EXECUTION_TIME_LABEL = "\u6267\u884c\u65f6\u95f4"
EXECUTION_TIME_META = "\u6bcf\u65e5\u81ea\u52a8\u8fd0\u884c\u65f6\u95f4"
SAVE_SETTINGS_LABEL = "\u4fdd\u5b58\u8bbe\u7f6e"
SAVE_SOURCE_LABEL = "\u4fdd\u5b58\u91c7\u96c6\u6e90"
RECENT_RESULT_TITLE = "\u6700\u8fd1\u4efb\u52a1\u7ed3\u679c"
VIEW_JOB_DETAIL_LABEL = "\u67e5\u770b\u4efb\u52a1\u8be6\u60c5"
OPEN_REPORT_LABEL = "\u6253\u5f00\u62a5\u544a"
REPORT_PENDING_HINT = "\u62a5\u544a\u6b63\u5728\u751f\u6210\uff0c\u7a0d\u5019\u5373\u53ef\u5728\u8fd9\u91cc\u6253\u5f00\u3002"
LATEST_TASK_ID_LABEL = "\u6700\u65b0\u4efb\u52a1 ID"


def _source_group_label(group: str | None) -> str:
    if group == "domestic":
        return "国内"
    if group == "overseas":
        return "国外"
    return "未分组"


def _job_scope_label(scope: str | None) -> str:
    if scope == "domestic":
        return "执行范围：国内"
    if scope == "overseas":
        return "执行范围：国外"
    return "执行范围：全部"


class JobDispatcherHolder:
    dispatcher = None


def configure_job_dispatcher(dispatcher) -> None:
    JobDispatcherHolder.dispatcher = dispatcher


def get_job_dispatcher():
    if JobDispatcherHolder.dispatcher is None:
        raise RuntimeError("job dispatcher is not configured")
    return JobDispatcherHolder.dispatcher


def _button_link(label: str, href: str, variant: str = "button-secondary") -> str:
    return f"<a class='button {variant}' href='{escape(href, quote=True)}'>{escape(label)}</a>"


def _button_submit(label: str, variant: str = "button-primary") -> str:
    return f"<button class='{escape(variant)}' type='submit'>{escape(label)}</button>"


def _job_status_tone(status: str) -> str:
    return {
        "success": "success",
        "running": "info",
        "pending": "warning",
        "partial_success": "warning",
        "failed": "danger",
    }.get(status, "neutral")


def _format_job_collection_time(job) -> str:
    value = getattr(job, "finished_at", None) or getattr(job, "started_at", None)
    if value is None:
        return "待开始"
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d %H:%M")
    return str(value)


def _render_error_summary(latest_error: str | None) -> str:
    if not latest_error:
        return ""
    label = SOURCE_CONFIG_ERROR if "\u6765\u6e90 URL \u65e0\u6548" in latest_error else LATEST_ERROR
    return (
        "<p class='job-error'>"
        f"<strong>{label}:</strong> "
        f"<span data-field='latest_error'>{escape(latest_error)}</span>"
        "</p>"
    )



def _humanize_diagnostic_detail(title: str, detail: str) -> str:
    normalized = detail.strip()
    lowered = normalized.lower()

    if title == "B\u7ad9\u767b\u5f55\u5931\u6548":
        return "B\u7ad9\u767b\u5f55\u6001\u53ef\u80fd\u5df2\u8fc7\u671f\uff0c\u8bf7\u5728\u8c03\u5ea6\u9875\u91cd\u65b0\u586b\u5199 Cookie \u540e\u518d\u8bd5\u3002"

    if title == "B\u7ad9\u98ce\u63a7":
        return "B\u7ad9\u5f53\u524d\u62e6\u622a\u4e86\u672c\u6b21\u67e5\u8be2\uff0c\u53ef\u7a0d\u540e\u91cd\u8bd5\uff0c\u6216\u66f4\u6362\u6700\u65b0 Cookie \u540e\u518d\u91c7\u96c6\u3002"

    if title == "B\u7ad9Cookie\u914d\u7f6e":
        if "required" in lowered or "is empty" in lowered:
            return "B\u7ad9 Cookie \u8fd8\u6ca1\u6709\u914d\u7f6e\uff0c\u8bf7\u5148\u5728\u8c03\u5ea6\u9875\u8865\u5145\u540e\u518d\u91c7\u96c6\u3002"
        if "invalid" in lowered:
            return "B\u7ad9 Cookie \u683c\u5f0f\u4e0d\u5b8c\u6574\u6216\u5df2\u5931\u6548\uff0c\u8bf7\u91cd\u65b0\u590d\u5236\u5b8c\u6574 Cookie\u3002"
        if "permission denied" in lowered or "refresh bilibili_cookie" in lowered:
            return "B\u7ad9 Cookie \u53ef\u80fd\u5df2\u5931\u6548\uff0c\u8bf7\u5237\u65b0\u540e\u91cd\u65b0\u586b\u5199\u3002"
        return "B\u7ad9 Cookie \u53ef\u80fd\u5b58\u5728\u95ee\u9898\uff0c\u8bf7\u68c0\u67e5\u662f\u5426\u4e3a\u6700\u65b0\u767b\u5f55\u6001\u3002"

    if title == "\u9489\u9489\u901a\u77e5\u672a\u53d1\u9001":
        if "no new collected items in current job" in lowered:
            return "\u672c\u8f6e\u65e0\u65b0\u589e\u5185\u5bb9\uff0c\u5df2\u8df3\u8fc7\u9489\u9489\u901a\u77e5\u3002"
        if "dingtalk_webhook is empty" in lowered:
            return "\u672a\u914d\u7f6e\u9489\u9489\u673a\u5668\u4eba Webhook\uff0c\u8bf7\u5230\u8c03\u5ea6\u9875\u586b\u5199\u540e\u518d\u8bd5\u3002"
        if "enable_dingtalk_notifier is false" in lowered:
            return "\u9489\u9489\u901a\u77e5\u5f00\u5173\u672a\u5f00\u542f\uff0c\u8bf7\u5230\u8c03\u5ea6\u9875\u542f\u7528\u540e\u518d\u6267\u884c\u4efb\u52a1\u3002"
        return "\u672c\u6b21\u4efb\u52a1\u672a\u53d1\u9001\u9489\u9489\u901a\u77e5\uff0c\u8bf7\u68c0\u67e5\u8c03\u5ea6\u9875\u7684\u673a\u5668\u4eba\u914d\u7f6e\u3002"

    if title == "\u9489\u9489\u901a\u77e5\u5931\u8d25":
        if "keywords not in content" in lowered:
            return "\u9489\u9489\u673a\u5668\u4eba\u5df2\u62d2\u6536\u6d88\u606f\uff0c\u8bf7\u68c0\u67e5\u673a\u5668\u4eba\u5173\u952e\u8bcd\u914d\u7f6e\u662f\u5426\u4e0e\u7cfb\u7edf\u586b\u5199\u4e00\u81f4\u3002"
        if "sign" in lowered or "timestamp" in lowered:
            return "\u9489\u9489\u52a0\u7b7e\u6821\u9a8c\u5931\u8d25\uff0c\u8bf7\u68c0\u67e5 Webhook \u914d\u5957\u7684 Secret \u662f\u5426\u586b\u5199\u6b63\u786e\u3002"
        if "errcode=" in lowered:
            return "\u9489\u9489\u673a\u5668\u4eba\u8fd4\u56de\u4e86\u53d1\u9001\u5931\u8d25\uff0c\u8bf7\u68c0\u67e5 Webhook\u3001Secret \u6216\u5173\u952e\u8bcd\u914d\u7f6e\u3002"
        return "\u9489\u9489\u6d88\u606f\u53d1\u9001\u5931\u8d25\uff0c\u8bf7\u68c0\u67e5 Webhook \u8fde\u63a5\u548c\u673a\u5668\u4eba\u914d\u7f6e\u3002"

    return normalized


def _extract_diagnostic_entries(logs) -> list[tuple[str, str, str]]:
    latest_by_title: dict[str, tuple[str, str, str]] = {}
    for log in logs or []:
        message = str(getattr(log, "message", "") or "").strip()
        level = str(getattr(log, "level", "warning") or "warning")
        title = ""
        detail = message
        if "dingtalk notification failed:" in message:
            title = "\u9489\u9489\u901a\u77e5\u5931\u8d25"
            detail = message.split("dingtalk notification failed:", 1)[1].strip() or message
        elif "dingtalk notification skipped:" in message:
            title = "\u9489\u9489\u901a\u77e5\u672a\u53d1\u9001"
            detail = message.split("dingtalk notification skipped:", 1)[1].strip() or message
        elif "\u767b\u5f55\u5931\u6548" in message or ("requires login" in message and "bilibili" in message.lower()):
            title = "B\u7ad9\u767b\u5f55\u5931\u6548"
        elif "\u98ce\u63a7" in message or ("risk control" in message and "bilibili" in message.lower()):
            title = "B\u7ad9\u98ce\u63a7"
        elif "BILIBILI_COOKIE" in message and "bilibili" in message.lower():
            title = "B\u7ad9Cookie\u914d\u7f6e"
        if not title:
            continue
        latest_by_title[title] = (title, _humanize_diagnostic_detail(title, detail), level)
    ordered_titles = ["B\u7ad9\u767b\u5f55\u5931\u6548", "B\u7ad9\u98ce\u63a7", "B\u7ad9Cookie\u914d\u7f6e", "\u9489\u9489\u901a\u77e5\u672a\u53d1\u9001", "\u9489\u9489\u901a\u77e5\u5931\u8d25"]
    return [latest_by_title[title] for title in ordered_titles if title in latest_by_title]


def _render_diagnostic_summary(logs) -> str:
    entries = _extract_diagnostic_entries(logs)
    if not entries:
        return ""
    items = "".join(
        f"<li class='diagnostic-item diagnostic-{escape(level, quote=True)}'><span class='diagnostic-label'>{escape(title)}</span><span class='diagnostic-detail'>{escape(detail)}</span></li>"
        for title, detail, level in entries
    )
    return (
        "<div class='diagnostic-summary'>"
        f"<h3 class='diagnostic-title'>{DIAGNOSTIC_SUMMARY_TITLE}</h3>"
        f"<ul class='diagnostic-list'>{items}</ul>"
        "</div>"
    )


def render_progress_panel(job, report_id, latest_error: str | None = None, logs=None) -> str:
    report_links = "<div class='helper-note'>\u62a5\u544a\u751f\u6210\u4e2d\uff0c\u8bf7\u7a0d\u5019\u5237\u65b0\u3002</div>"
    if report_id is not None:
        report_links = f"""
        <div class='report-links'>
          <a class='button button-primary' href='/reports/{report_id}'>\u67e5\u770b\u62a5\u544a {report_id}</a>
          <a class='button button-secondary' href='/api/reports/{report_id}/download?format=md'>\u4e0b\u8f7d Markdown</a>
          <a class='button button-secondary' href='/api/reports/{report_id}/download?format=docx'>\u4e0b\u8f7d DOCX</a>
        </div>
        """

    metrics = f"""
    <div class='metrics-compact'>
      <div class='metric-tile'><span class='kicker'>\u603b\u6765\u6e90</span><strong data-field='total_sources'>{job.total_sources}</strong></div>
      <div class='metric-tile'><span class='kicker'>\u5df2\u5b8c\u6210</span><strong data-field='completed_sources'>{job.completed_sources}</strong></div>
      <div class='metric-tile'><span class='kicker'>\u6210\u529f</span><strong data-field='success_sources'>{job.success_sources}</strong></div>
      <div class='metric-tile'><span class='kicker'>\u5931\u8d25</span><strong data-field='failed_sources'>{job.failed_sources}</strong></div>
    </div>
    """
    return f"""
    <section id='progress-panel' class='panel progress-panel'>
      <div class='panel-header'>
        <h2 class='panel-title'>{TASK_PROGRESS_TITLE}</h2>
        {render_badge(job.status, _job_status_tone(job.status))}
      </div>
      <div class='panel-body'>
        {report_links}
        {_render_error_summary(latest_error)}
        {_render_diagnostic_summary(logs)}
        <p class='helper-note'>\u72b6\u6001: <strong data-field='status'>{escape(job.status)}</strong></p>
        {metrics}
      </div>
    </section>
    """


def render_log_list(logs) -> str:
    items = "".join(f"<li>[{escape(log.level)}] {escape(log.message)}</li>" for log in logs)
    if not items:
        items = "<li>\u6682\u65e0\u65e5\u5fd7</li>"
    return f"""
    <section class='panel log-panel'>
      <div class='panel-header'>
        <h2 class='panel-title'>{TASK_LOGS_TITLE}</h2>
      </div>
      <div class='panel-body'>
        <ul id='job-log-list'>{items}</ul>
      </div>
    </section>
    """


def _render_recent_jobs(recent_jobs) -> str:
    if not recent_jobs:
        return "<div class='empty-state'>暂无任务，点击“立即采集”即可生成第一条运行记录。</div>"
    items = []
    for index, job in enumerate(recent_jobs):
        collection_time = _format_job_collection_time(job)
        summary = (
            f"<div class='timeline-summary'>"
            f"<span>总来源<strong>{job.total_sources}</strong></span>"
            f"<span>成功<strong>{job.success_sources}</strong></span>"
            f"<span>失败<strong>{job.failed_sources}</strong></span>"
            f"<span>已完成<strong>{job.completed_sources}</strong></span>"
            f"</div>"
        )
        latest_class = " is-latest" if index == 0 else ""
        items.append(
            f"""
            <a class='recent-job-item' href='/jobs/{job.id}'>
              <span class='recent-job-node status-{escape(job.status, quote=True)}'></span>
              <div class='recent-job-card{latest_class}'>
                <div class='timeline-meta'>
                  <div class='kicker'>任务 {job.id}</div>
                  {render_badge(job.status, _job_status_tone(job.status))}
                </div>
                <h3>运行结果概览</h3>
                <div class='resource-meta'>采集时间：{escape(collection_time)}</div>
                {summary}
                <div class='resource-meta'>打开详情查看进度、日志与报告下载。</div>
              </div>
            </a>
            """
        )
    return f"<div id='recent-jobs' class='recent-job-list recent-jobs-timeline'>{''.join(items)}</div>"


def _render_source_card(source) -> str:
    site_name = source.site_name or "\u672a\u547d\u540d\u7ad9\u70b9"
    tone = "success" if source.enabled else "neutral"
    enabled_text = "\u5df2\u542f\u7528" if source.enabled else "\u5df2\u505c\u7528"
    group_text = _source_group_label(getattr(source, "source_group", None))
    edit_link = _button_link('编辑', f'/sources/{source.id}')
    delete_form = f"""
    <form class='inline-form' method='post' action='/api/sources/{source.id}/delete' onsubmit=\"return confirm('确认删除这个采集员吗？');\">
      <button class='button-secondary' type='submit'>删除</button>
    </form>
    """
    return f"""
    <article class='resource-card'>
      <div class='kicker'>{escape(site_name)}</div>
      <h3><a href='/sources/{source.id}'>{escape(source.name)}</a></h3>
      <div>{render_badge(source.fetch_mode, 'info')} {render_badge(enabled_text, tone)} {render_badge(group_text, 'info')}</div>
      <div class='resource-meta'>{escape(source.entry_url)}</div>
      <div class='page-actions'>{edit_link}{delete_form}</div>
    </article>
    """


def _render_source_edit_page(source, *, error: str | None = None) -> str:
    checked = "checked" if getattr(source, "enabled", False) else ""
    group_value = str(getattr(source, "source_group", "") or "domestic")
    search_keyword = str(getattr(source, "search_keyword", "") or "")
    error_html = f"<p class='helper-note'>{escape(error)}</p>" if error else ""
    form = f"""
    <form method='post' action='/sources/{source.id}' class='scheduler-form scheduler-settings-panel'>
      {error_html}
      <div class='field-grid'>
        <label class='field'>
          <span class='label'>名称</span>
          <input name='name' value='{escape(str(source.name), quote=True)}' />
        </label>
        <label class='field'>
          <span class='label'>入口 URL</span>
          <input name='entry_url' value='{escape(str(source.entry_url), quote=True)}' />
        </label>
        <label class='field'>
          <span class='label'>关键词</span>
          <input name='search_keyword' value='{escape(search_keyword, quote=True)}' placeholder='如当前来源不需要可留空' />
        </label>
        <label class='field'>
          <span class='label'>来源分组</span>
          <select name='source_group'>
            <option value='domestic'{" selected" if group_value == "domestic" else ""}>国内</option>
            <option value='overseas'{" selected" if group_value == "overseas" else ""}>国外</option>
          </select>
        </label>
        <label class='field'>
          <span class='label'>最大条数</span>
          <input name='max_items' value='{escape(str(source.max_items), quote=True)}' />
        </label>
      </div>
      <label class='checkbox-row'>
        <input type='checkbox' name='enabled' value='true' {checked} />
        <span>启用该采集源</span>
      </label>
      <p class='helper-note'>当前站点：{escape(str(getattr(source, "site_name", "") or "未命名站点"))}；当前抓取方式：{escape(str(getattr(source, "fetch_mode", "") or "未设置"))}。这个页面只开放常用字段编辑，不修改高级抓取配置。</p>
      <div class='page-actions'>{_button_submit('保存采集源', 'button-primary')}{_button_link('返回采集源列表', '/sources')}</div>
    </form>
    """
    content = (
        render_page_header(
            eyebrow='Source Edit',
            title='编辑采集源',
            subtitle='修改常用字段后保存，系统会回到采集源列表页。',
            actions=_button_link('返回采集源列表', '/sources'),
        )
        + render_panel(BASE_CONFIG_TITLE, form, extra_class='form-panel')
    )
    return render_page(title='编辑采集源', content=content, body_class='theme-dark')


def _get_source_or_404(session: Session, source_id: str):
    source = SourceService(session).get_source(source_id)
    if source is None:
        raise HTTPException(status_code=404, detail='source not found')
    return source


def _render_featured_latest_job(service: JobService, recent_jobs) -> str:
    if not recent_jobs:
        return f"""
        <section class='featured-latest-job'>
          <div class='featured-kicker'>{RECENT_RESULT_TITLE}</div>
          <h2 class='featured-title'>\u6682\u65e0\u6700\u8fd1\u4efb\u52a1</h2>
          <p class='featured-summary'>\u8fd8\u6ca1\u6709\u53ef\u5c55\u793a\u7684\u91c7\u96c6\u7ed3\u679c\uff0c\u53ef\u4ee5\u7acb\u5373\u89e6\u53d1\u4e00\u6b21\u91c7\u96c6\uff0c\u8ba9\u9996\u9875\u53d8\u6210\u4eca\u65e5\u60c5\u62a5\u53f0\u3002</p>
          <div class='hero-actions'>
            <form class='inline-form' method='post' action='/jobs/run/domestic'>
              {_button_submit('立即采集国内')}
            </form>
            <form class='inline-form' method='post' action='/jobs/run/overseas'>
              {_button_submit('立即采集国外')}
            </form>
          </div>
        </section>
        """

    latest_job = recent_jobs[0]
    report_id = service.get_report_id(str(latest_job.id))
    report_action = (
        _button_link(OPEN_REPORT_LABEL, f"/reports/{report_id}", "button-secondary")
        if report_id is not None
        else f"<div class='helper-note'>{REPORT_PENDING_HINT}</div>"
    )
    return f"""
    <section class='featured-latest-job'>
      <div class='featured-kicker'>{RECENT_RESULT_TITLE}</div>
      <div class='featured-header'>
        <div>
          <div class='kicker'>{LATEST_TASK_ID_LABEL}</div>
          <h2 class='featured-title'>{escape(str(latest_job.id))}</h2>
        </div>
        {render_badge(latest_job.status, _job_status_tone(latest_job.status))}
      </div>
      <p class='featured-summary'>\u9996\u9875\u5148\u770b\u8fd9\u4e00\u8f6e\u91c7\u96c6\u7684\u6700\u7ec8\u7ed3\u679c\uff0c\u5982\u679c\u9700\u8981\u8ffd\u8e2a\u66f4\u7ec6\u65e5\u5fd7\uff0c\u53ef\u76f4\u63a5\u6253\u5f00\u4efb\u52a1\u8be6\u60c5\u6216\u62a5\u544a\u3002</p>
      <div class='featured-metrics'>
        <div class='featured-metric'><span class='kicker'>\u603b\u6765\u6e90</span><strong>{latest_job.total_sources}</strong></div>
        <div class='featured-metric'><span class='kicker'>\u6210\u529f</span><strong>{latest_job.success_sources}</strong></div>
        <div class='featured-metric'><span class='kicker'>\u5931\u8d25</span><strong>{latest_job.failed_sources}</strong></div>
        <div class='featured-metric'><span class='kicker'>\u5df2\u5b8c\u6210</span><strong>{latest_job.completed_sources}</strong></div>
      </div>
      <div class='hero-actions'>
        {_button_link(VIEW_JOB_DETAIL_LABEL, f"/jobs/{latest_job.id}", "button-primary")}
        {report_action}
      </div>
    </section>
    """


@router.get("/", response_class=HTMLResponse)
def index_page(request: Request, session: Session = Depends(get_db_session)) -> str:
    service = JobService(session)
    recent_jobs = service.list_recent_jobs(limit=3)
    source_service = SourceService(session)
    source_count = len(source_service.list_sources())
    domestic_count = source_service.count_enabled_sources("domestic")
    overseas_count = source_service.count_enabled_sources("overseas")
    ungrouped_count = source_service.count_enabled_sources(None)
    latest_status = recent_jobs[0].status if recent_jobs else "idle"
    run_group_empty = request.query_params.get("run_group_empty")
    run_group_feedback = ""
    if run_group_empty == "domestic":
        run_group_feedback = "<p class='helper-note'>国内分组没有可采集来源。</p>"
    elif run_group_empty == "overseas":
        run_group_feedback = "<p class='helper-note'>国外分组没有可采集来源。</p>"

    hero = f"""
    <section class='page-hero dashboard-hero result-hero'>
      <div class='hero-grid hero-grid-featured'>
        {_render_featured_latest_job(service, recent_jobs)}
        <div class='hero-side-stack'>
          <div>
            <div class='eyebrow'>Signal Center</div>
            <h1 class='page-title'>{DASHBOARD_TITLE}</h1>
            <p class='page-subtitle'>\u628a\u6700\u65b0\u4e00\u8f6e\u91c7\u96c6\u7684\u7ed3\u679c\u653e\u5728\u9996\u5c4f\u4e2d\u5fc3\uff0c\u8ba9\u5de5\u4f5c\u53f0\u5148\u56de\u7b54"\u521a\u521a\u6293\u5230\u4e86\u4ec0\u4e48"\u3002</p>
            {run_group_feedback}
          </div>
          <div class='stats-grid compact-stats-grid'>
            {render_stat_card(ACTIVE_SOURCES_LABEL, str(source_count), ACTIVE_SOURCES_META)}
            {render_stat_card('国内来源', str(domestic_count), '将纳入“立即采集国内”按钮')}
            {render_stat_card('国外来源', str(overseas_count), '将纳入“立即采集国外”按钮')}
            {render_stat_card('未分组来源', str(ungrouped_count), '不会被国内/国外按钮带上')}
          </div>
          <div class='hero-actions'>
            <form class='inline-form' method='post' action='/jobs/run/domestic'>
              {_button_submit('立即采集国内')}
            </form>
            <form class='inline-form' method='post' action='/jobs/run/overseas'>
              {_button_submit('立即采集国外')}
            </form>
            {_button_link(SOURCES_TITLE, '/sources')}
            {_button_link(REPORTS_TITLE, '/reports')}
          </div>
        </div>
      </div>
    </section>
    """

    quick_actions_html = (
        "<div id='quick-actions' class='quick-link-list'>"
        "<a class='mini-card' href='/sources'><h3>\u91c7\u96c6\u6e90\u7ba1\u7406</h3><div class='resource-meta'>\u67e5\u770b\u6765\u6e90\u914d\u7f6e\u3001\u542f\u7528\u72b6\u6001\u4e0e\u5165\u53e3 URL\u3002</div></a>"
        "<a class='mini-card' href='/reports'><h3>\u5386\u53f2\u62a5\u544a</h3><div class='resource-meta'>\u4e0b\u8f7d\u6700\u8fd1\u751f\u6210\u7684\u70ed\u70b9\u62a5\u544a\u3002</div></a>"
        "<a class='mini-card' href='/scheduler'><h3>\u5b9a\u65f6\u8c03\u5ea6</h3><div class='resource-meta'>\u8bbe\u7f6e\u6bcf\u65e5\u81ea\u52a8\u8fd0\u884c\u65f6\u95f4\u3002</div></a>"
        "</div>"
    )
    content = hero + f"""
    <section class='content-grid'>
      {render_panel(RECENT_JOBS_TITLE, _render_recent_jobs(recent_jobs), extra_class='recent-jobs-panel')}
      {render_panel(QUICK_ACTIONS_TITLE, quick_actions_html, extra_class='quick-actions-panel')}
    </section>
    """
    return render_page(title=APP_TITLE, content=content, body_class='theme-dark', page_class='dashboard-page')



def _render_scheduler_page(
    session: Session,
    *,
    bilibili_form_value: str | None = None,
    bilibili_error: str | None = None,
    bilibili_success: str | None = None,
) -> str:
    settings = SchedulerService(session).get_settings()
    app_env_service = AppEnvService()
    dingtalk_settings = app_env_service.get_dingtalk_settings()
    bilibili_settings = app_env_service.get_bilibili_settings()
    network_settings = app_env_service.get_network_settings()
    fetch_interval_settings = app_env_service.get_fetch_interval_settings()
    enabled_text = "\u5df2\u542f\u7528" if settings.enabled else "\u5df2\u505c\u7528"
    checked = "checked" if settings.enabled else ""
    dingtalk_enabled_text = "\u5df2\u542f\u7528" if dingtalk_settings.enabled else "\u5df2\u505c\u7528"
    dingtalk_checked = "checked" if dingtalk_settings.enabled else ""
    bilibili_cookie_status = "已配置" if bilibili_settings.cookie.strip() else "未配置"
    network_enabled_text = "已启用" if network_settings.enabled else "已停用"
    network_checked = "checked" if network_settings.enabled else ""
    bilibili_value = bilibili_settings.cookie if bilibili_form_value is None else bilibili_form_value
    bilibili_feedback = ""
    if bilibili_success:
        bilibili_feedback += f"<p class='helper-note'>{escape(bilibili_success)}</p>"
    if bilibili_error:
        bilibili_feedback += f"<p class='helper-note'>{escape(bilibili_error)}</p>"
    summary = f"""
    <div class='stats-grid'>
      {render_stat_card(CURRENT_STATUS_LABEL, enabled_text, CURRENT_STATUS_META)}
      {render_stat_card(EXECUTION_TIME_LABEL, settings.daily_time, EXECUTION_TIME_META)}
      {render_stat_card('钉钉通知', dingtalk_enabled_text, '保存后会同步写入 data/app.env，并用于后续任务通知')}
      {render_stat_card('B站登录态', bilibili_cookie_status, '保存完整浏览器 Cookie 后，B站主页与站内搜索都会优先复用该登录态')}
      {render_stat_card('站点网络访问', network_enabled_text, '启用后可让 B站直连，其它站点按应用内代理规则访问')}
    </div>
    """
    form = f"""
    <form method='post' action='/scheduler' class='scheduler-form scheduler-settings-panel'>
      <label class='checkbox-row'>
        <input type='checkbox' name='enabled' value='true' {checked} />
        <span>\u542f\u7528\u5b9a\u65f6\u8c03\u5ea6</span>
      </label>
      <div class='field'>
        <span class='label'>\u6267\u884c\u65f6\u95f4</span>
        <input type='time' name='daily_time' value='{escape(settings.daily_time, quote=True)}' />
      </div>
      <div class='page-actions'>{_button_submit(SAVE_SETTINGS_LABEL)}</div>
    </form>
    """
    dingtalk_form = f"""
    <form method='post' action='/scheduler/dingtalk' class='scheduler-form scheduler-settings-panel'>
      <label class='checkbox-row'>
        <input type='checkbox' name='enabled' value='true' {dingtalk_checked} />
        <span>启用钉钉群通知</span>
      </label>
      <div class='field'>
        <span class='label'>Webhook</span>
        <input name='webhook' value='{escape(dingtalk_settings.webhook, quote=True)}' placeholder='https://oapi.dingtalk.com/robot/send?access_token=...' />
      </div>
      <div class='field'>
        <span class='label'>Secret</span>
        <input name='secret' value='{escape(dingtalk_settings.secret, quote=True)}' placeholder='未启用加签可留空' />
      </div>
      <div class='field'>
        <span class='label'>关键词</span>
        <input name='keyword' value='{escape(dingtalk_settings.keyword, quote=True)}' placeholder='如配置了机器人关键词，请保持一致' />
      </div>
      <p class='helper-note'>保存后立即更新当前运行配置，并持久化到 {escape(str(dingtalk_settings.env_file))}。</p>
      <div class='page-actions'>{_button_submit('保存钉钉通知', 'button-primary')}</div>
    </form>
    """
    bilibili_form = f"""
    <form method='post' action='/scheduler/bilibili' class='scheduler-form scheduler-settings-panel'>
      {bilibili_feedback}
      <div class='field'>
        <span class='label'>完整 Cookie</span>
        <textarea name='bilibili_cookie' rows='6' placeholder='SESSDATA=...; bili_jct=...; DedeUserID=...'>{escape(bilibili_value)}</textarea>
      </div>
      <p class='helper-note'>这里直接粘贴浏览器里复制出来的整串 Cookie 即可；如果误贴了 BILIBILI_COOKIE= 前缀，系统会自动识别。缺少 SESSDATA 将拒绝保存。保存后会立即写入 {escape(str(bilibili_settings.env_file))}。</p>
      <div class='page-actions'>{_button_submit('保存B站登录态', 'button-primary')}</div>
    </form>
    <form method='post' action='/scheduler/bilibili/browser-login' class='scheduler-form scheduler-settings-panel'>
      <p class='helper-note'>如果手工复制 Cookie 很容易触发风控，可直接点下面按钮，系统会打开本机浏览器让你完成登录，并自动把最新登录态同步到 {escape(str(bilibili_settings.env_file))}。</p>
      <div class='page-actions'>{_button_submit('打开浏览器登录并同步', 'button-primary')}</div>
    </form>
    """
    network_form = f"""
    <form method='post' action='/scheduler/network' class='scheduler-form scheduler-settings-panel'>
      <label class='checkbox-row'>
        <input type='checkbox' name='proxy_enabled' value='true' {network_checked} />
        <span>启用站点代理规则</span>
      </label>
      <div class='field'>
        <span class='label'>代理地址</span>
        <input name='outbound_proxy_url' value='{escape(network_settings.outbound_proxy_url, quote=True)}' placeholder='http://127.0.0.1:7890' />
      </div>
      <div class='field'>
        <span class='label'>直连域名</span>
        <input name='bypass_domains' value='{escape(network_settings.bypass_domains, quote=True)}' placeholder='bilibili.com,hdslb.com,bilivideo.com' />
      </div>
      <p class='helper-note'>代理地址可以留空。留空时系统默认全部直连；如果填写了代理地址，未命中直连域名的站点才会走应用内代理。建议默认保留 B站相关域名直连。</p>
      <div class='page-actions'>{_button_submit('保存网络访问', 'button-primary')}</div>
    </form>
    """
    fetch_interval_form = f"""
    <form method='post' action='/scheduler/fetch-interval' class='scheduler-form scheduler-settings-panel'>
      <div class='field-grid'>
        <div class='field'>
          <span class='label'>全局间隔（秒）</span>
          <input name='source_fetch_interval_seconds' type='number' min='0' value='{escape(str(fetch_interval_settings.source_fetch_interval_seconds), quote=True)}' />
        </div>
        <div class='field'>
          <span class='label'>B站额外间隔（秒）</span>
          <input name='bilibili_source_interval_seconds' type='number' min='0' value='{escape(str(fetch_interval_settings.bilibili_source_interval_seconds), quote=True)}' />
        </div>
        <div class='field'>
          <span class='label'>B站重试退避（秒）</span>
          <input name='bilibili_retry_delay_seconds' type='number' min='0' value='{escape(str(fetch_interval_settings.bilibili_retry_delay_seconds), quote=True)}' />
        </div>
      </div>
      <p class='helper-note'>来源仍按顺序串行执行。普通来源使用全局间隔；B站来源会在此基础上再追加一次 B站额外间隔。若 B站主页偶发风控或异常跳转，系统会按这里设置的退避秒数自动重试 1 次。建议 B站先从 15~20 秒间隔、5~10 秒退避尝试。</p>
      <div class='page-actions'>{_button_submit('保存采集节流', 'button-primary')}</div>
    </form>
    """
    content = (
        render_page_header(
            eyebrow='Scheduler',
            title=SCHEDULER_TITLE,
            subtitle='\u96c6\u4e2d\u7ba1\u7406\u6bcf\u65e5\u81ea\u52a8\u91c7\u96c6\u65f6\u95f4\uff0c\u8ba9\u7cfb\u7edf\u6309\u56fa\u5b9a\u8282\u594f\u8f93\u51fa\u70ed\u70b9\u62a5\u544a\u3002',
            actions=_button_link('返回首页', '/'),
        )
        + summary
        + render_panel(SETTINGS_TITLE, form, extra_class='scheduler-settings-panel')
        + render_panel('钉钉通知', dingtalk_form, extra_class='scheduler-settings-panel')
        + render_panel('B站登录态', bilibili_form, extra_class='scheduler-settings-panel')
        + render_panel('站点网络访问', network_form, extra_class='scheduler-settings-panel')
        + render_panel('采集节流', fetch_interval_form, extra_class='scheduler-settings-panel')
    )
    return render_page(title=SCHEDULER_TITLE, content=content, body_class='theme-dark')


@router.get("/scheduler", response_class=HTMLResponse)
def scheduler_page(request: Request, session: Session = Depends(get_db_session)) -> str:
    bilibili_success = None
    if request.query_params.get('bilibili_saved') == '1':
        bilibili_success = 'B站登录态已更新'
    if request.query_params.get('bilibili_browser_saved') == '1':
        bilibili_success = '已从浏览器同步最新B站登录态'
    return _render_scheduler_page(session, bilibili_success=bilibili_success)


@router.post('/scheduler')
async def save_scheduler_settings(request: Request, session: Session = Depends(get_db_session)) -> RedirectResponse:
    form_data = parse_qs((await request.body()).decode('utf-8'))
    enabled = form_data.get('enabled', [None])[0] == 'true'
    daily_time = form_data.get('daily_time', ['08:00'])[0]
    SchedulerService(session).update_settings(enabled=enabled, daily_time=daily_time)
    return RedirectResponse(url='/scheduler', status_code=303)


@router.post('/scheduler/dingtalk')
async def save_dingtalk_settings(request: Request) -> RedirectResponse:
    form_data = parse_qs((await request.body()).decode('utf-8'))
    enabled = form_data.get('enabled', [None])[0] == 'true'
    webhook = form_data.get('webhook', [''])[0]
    secret = form_data.get('secret', [''])[0]
    keyword = form_data.get('keyword', [''])[0]
    AppEnvService().update_dingtalk_settings(enabled=enabled, webhook=webhook, secret=secret, keyword=keyword)
    return RedirectResponse(url='/scheduler', status_code=303)


@router.post('/scheduler/bilibili')
async def save_bilibili_settings(request: Request, session: Session = Depends(get_db_session)) -> Response:
    form_data = parse_qs((await request.body()).decode('utf-8'))
    bilibili_cookie = form_data.get('bilibili_cookie', [''])[0]
    try:
        AppEnvService().update_bilibili_settings(cookie=bilibili_cookie)
    except ValueError as exc:
        html = _render_scheduler_page(
            session,
            bilibili_form_value=bilibili_cookie,
            bilibili_error=str(exc),
        )
        return HTMLResponse(content=html, status_code=422)
    return RedirectResponse(url='/scheduler?bilibili_saved=1', status_code=303)


@router.post('/scheduler/bilibili/browser-login')
async def sync_bilibili_settings_from_browser(session: Session = Depends(get_db_session)) -> Response:
    try:
        result = BilibiliBrowserAuthService().login_and_sync()
        if getattr(result, 'cookie', '').strip():
            AppEnvService().update_bilibili_settings(cookie=result.cookie)
    except RuntimeError as exc:
        html = _render_scheduler_page(
            session,
            bilibili_error=str(exc),
        )
        return HTMLResponse(content=html, status_code=422)
    return RedirectResponse(url='/scheduler?bilibili_browser_saved=1', status_code=303)


@router.post('/scheduler/network')
async def save_network_settings(request: Request) -> RedirectResponse:
    form_data = parse_qs((await request.body()).decode('utf-8'))
    enabled = form_data.get('proxy_enabled', [None])[0] == 'true'
    outbound_proxy_url = form_data.get('outbound_proxy_url', [''])[0]
    bypass_domains = form_data.get('bypass_domains', [''])[0]
    AppEnvService().update_network_settings(enabled=enabled, outbound_proxy_url=outbound_proxy_url, bypass_domains=bypass_domains)
    return RedirectResponse(url='/scheduler', status_code=303)


@router.post('/scheduler/fetch-interval')
async def save_fetch_interval_settings(request: Request) -> RedirectResponse:
    form_data = parse_qs((await request.body()).decode('utf-8'))
    source_fetch_interval_seconds = int(form_data.get('source_fetch_interval_seconds', ['0'])[0] or '0')
    bilibili_source_interval_seconds = int(form_data.get('bilibili_source_interval_seconds', ['0'])[0] or '0')
    bilibili_retry_delay_seconds = int(form_data.get('bilibili_retry_delay_seconds', ['5'])[0] or '5')
    AppEnvService().update_fetch_interval_settings(
        source_fetch_interval_seconds=source_fetch_interval_seconds,
        bilibili_source_interval_seconds=bilibili_source_interval_seconds,
        bilibili_retry_delay_seconds=bilibili_retry_delay_seconds,
    )
    return RedirectResponse(url='/scheduler', status_code=303)

@router.get('/sources', response_class=HTMLResponse)
def sources_page(request: Request, session: Session = Depends(get_db_session)) -> str:
    source_service = SourceService(session)
    grouped_sources = (
        ('国内采集源', source_service.list_sources_by_group('domestic')),
        ('国外采集源', source_service.list_sources_by_group('overseas')),
        ('未分组采集源', source_service.list_sources_by_group(None)),
    )
    items_html = "<div class='empty-state'>暂无采集源，先创建一个入口即可开始收集热点。</div>"
    if any(sources for _, sources in grouped_sources):
        items_html = ''.join(
            render_panel(
                title,
                (
                    f"<section class='source-grid'>{''.join(_render_source_card(source) for source in sources)}</section>"
                    if sources
                    else "<div class='empty-state'>当前分组暂无采集源。</div>"
                ),
                extra_class='sources-group-panel',
            )
            for title, sources in grouped_sources
        )

    saved_feedback = "<p class='helper-note'>采集源已更新</p>" if request.query_params.get('source_saved') == '1' else ""
    content = (
        render_page_header(
            eyebrow='Sources',
            title=SOURCES_TITLE,
            subtitle='\u7edf\u4e00\u67e5\u770b\u6bcf\u4e2a\u70ed\u70b9\u6765\u6e90\u7684\u7ad9\u70b9\u3001\u6293\u53d6\u65b9\u5f0f\u4e0e\u5165\u53e3\u5730\u5740\uff0c\u4fdd\u8bc1\u6765\u6e90\u914d\u7f6e\u4e00\u76ee\u4e86\u7136\u3002',
            actions=_button_link('\u8fd4\u56de\u9996\u9875', '/') + _button_link(NEW_SOURCE_TITLE, '/sources/new', 'button-primary'),
        )
        + saved_feedback
        + items_html
    )
    return render_page(title=SOURCES_TITLE, content=content, body_class='theme-dark')


@router.get('/sources/new', response_class=HTMLResponse)
def new_source_page() -> str:
    form = f"""
    <form method='post' action='/api/sources/form'>
      <div class='field-grid'>
        <label class='field'>
          <span class='label'>\u5165\u53e3 URL</span>
          <input name='entry_url' placeholder='https://www.youtube.com/@ElectronicArts ? https://space.bilibili.com/20411266' />
        </label>
        <label class='field'>
          <span class='label'>\u5173\u952e\u8bcd</span>
          <input name='search_keyword' placeholder='\u4f8b\u5982\uff1a\u6e38\u620f' />
        </label>
        <label class='field'>
          <span class='label'>\u6765\u6e90\u5206\u7ec4</span>
          <select name='source_group'>
            <option value='domestic'>国内</option>
            <option value='overseas'>国外</option>
          </select>
        </label>
        <label class='field'>
          <span class='label'>\u6700\u5927\u6761\u6570</span>
          <input name='max_items' value='30' />
        </label>
      </div>
      <p class='helper-note'>只需要填写 URL、分组、关键词和条数，系统会自动推断最合适的采集策略。</p>
      <div class='page-actions'>{_button_submit(SAVE_SOURCE_LABEL)}</div>
    </form>
    """
    content = (
        render_page_header(
            eyebrow='Source Setup',
            title=NEW_SOURCE_TITLE,
            subtitle='\u7528\u7b80\u5316\u8868\u5355\u5feb\u901f\u5f55\u5165\u4e00\u4e2a\u65b0\u7684\u70ed\u70b9\u5165\u53e3\uff0c\u9002\u5408\u8fd0\u8425\u540c\u5b66\u65e5\u5e38\u7ef4\u62a4\u3002',
            actions=_button_link('\u8fd4\u56de\u6765\u6e90\u5217\u8868', '/sources'),
        )
        + render_panel(BASE_CONFIG_TITLE, form, extra_class='form-panel')
    )
    return render_page(title=NEW_SOURCE_TITLE, content=content, body_class='theme-dark')


@router.get('/sources/{source_id}', response_class=HTMLResponse)
def edit_source_page(source_id: str, session: Session = Depends(get_db_session)) -> str:
    source = _get_source_or_404(session, source_id)
    return _render_source_edit_page(source)


@router.post('/sources/{source_id}')
async def save_source_page(source_id: str, request: Request, session: Session = Depends(get_db_session)) -> Response:
    form_data = parse_qs((await request.body()).decode('utf-8'))
    source = _get_source_or_404(session, source_id)

    try:
        payload = SourceUpdate(
            name=form_data.get('name', [str(source.name)])[0].strip(),
            entry_url=form_data.get('entry_url', [str(source.entry_url)])[0].strip(),
            search_keyword=(form_data.get('search_keyword', [''])[0].strip() or None),
            source_group=form_data.get('source_group', [str(getattr(source, 'source_group', '') or '')])[0].strip() or None,
            max_items=form_data.get('max_items', [str(source.max_items)])[0].strip(),
            enabled=form_data.get('enabled', [None])[0] == 'true',
        )
    except ValidationError as exc:
        message = '; '.join(error['msg'] for error in exc.errors())
        source.name = form_data.get('name', [str(source.name)])[0]
        source.entry_url = form_data.get('entry_url', [str(source.entry_url)])[0]
        source.search_keyword = form_data.get('search_keyword', [''])[0] or None
        source.source_group = form_data.get('source_group', [str(getattr(source, 'source_group', '') or '')])[0] or None
        source.max_items = form_data.get('max_items', [str(source.max_items)])[0]
        source.enabled = form_data.get('enabled', [None])[0] == 'true'
        return HTMLResponse(content=_render_source_edit_page(source, error=message), status_code=422)

    updated = SourceService(session).update_source(source_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail='source not found')
    return RedirectResponse(url='/sources?source_saved=1', status_code=303)


@router.post('/jobs/run')
def run_job(session: Session = Depends(get_db_session), dispatcher=Depends(get_job_dispatcher)) -> RedirectResponse:
    service = JobService(session)
    job = service.create_manual_job()
    dispatcher.dispatch_pending_jobs()
    return RedirectResponse(url=f'/jobs/{job.id}', status_code=303)


@router.post('/jobs/run/domestic')
def run_domestic_job(session: Session = Depends(get_db_session), dispatcher=Depends(get_job_dispatcher)) -> RedirectResponse:
    service = JobService(session)
    job = service.create_manual_job_for_group('domestic')
    if job is None:
        return RedirectResponse(url='/?run_group_empty=domestic', status_code=303)
    dispatcher.dispatch_pending_jobs()
    return RedirectResponse(url=f'/jobs/{job.id}', status_code=303)


@router.post('/jobs/run/overseas')
def run_overseas_job(session: Session = Depends(get_db_session), dispatcher=Depends(get_job_dispatcher)) -> RedirectResponse:
    service = JobService(session)
    job = service.create_manual_job_for_group('overseas')
    if job is None:
        return RedirectResponse(url='/?run_group_empty=overseas', status_code=303)
    dispatcher.dispatch_pending_jobs()
    return RedirectResponse(url=f'/jobs/{job.id}', status_code=303)


@router.get('/jobs/{job_id}', response_class=HTMLResponse)
def job_detail_page(job_id: str, session: Session = Depends(get_db_session)) -> str:
    service = JobService(session)
    job = service.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail='job not found')

    header = render_page_header(
        eyebrow='Job Monitor',
        title=JOB_DETAIL_TITLE,
        subtitle='\u6301\u7eed\u8ddf\u8e2a\u5f53\u524d\u4efb\u52a1\u72b6\u6001\u3001\u6765\u6e90\u5b8c\u6210\u60c5\u51b5\u548c\u62a5\u544a\u751f\u6210\u8fdb\u5ea6\u3002',
        actions=_button_link('\u8fd4\u56de\u9996\u9875', '/') + render_badge(_job_scope_label(job.source_group_scope), 'info') + render_badge(job.status, _job_status_tone(job.status)),
    )
    logs = service.list_job_logs(job_id)
    progress_host = f"<div id='progress-host' data-url='/jobs/{job.id}/progress'>{render_progress_panel(job, service.get_report_id(job_id), service.get_latest_error_message(job_id), logs)}</div>"
    report_summary = render_panel(
        JOB_REPORTS_TITLE,
        f"<div class='helper-note'>\u4efb\u52a1 ID: {escape(str(job.id))}</div><div class='helper-note'>\u7cfb\u7edf\u4f1a\u81ea\u52a8\u5237\u65b0\u8fdb\u5ea6\u548c\u65e5\u5fd7\uff0c\u65e0\u9700\u624b\u52a8\u91cd\u8f7d\u9875\u9762\u3002</div>",
        extra_class='report-summary-panel',
    )
    log_host = f"<div id='job-log-host' data-url='/jobs/{job.id}/logs/view'>{render_log_list(logs)}</div>"
    content = header + f"""
    <section class='job-detail-layout'>
      <div class='job-detail-main'>
        <div>{progress_host}</div>
        <div>{report_summary}</div>
      </div>
      <div class='log-panel'>{log_host}</div>
    </section>
    <script>
      async function refreshJobDetail() {{
        const progressHost = document.getElementById('progress-host');
        const logHost = document.getElementById('job-log-host');
        const [progressResponse, logResponse] = await Promise.all([
          fetch(progressHost.dataset.url),
          fetch(logHost.dataset.url)
        ]);
        if (!progressResponse.ok || !logResponse.ok) {{
          return;
        }}
        progressHost.innerHTML = await progressResponse.text();
        logHost.innerHTML = await logResponse.text();
      }}

      refreshJobDetail();
      setInterval(refreshJobDetail, 2000);
    </script>
    """
    return render_page(title=JOB_DETAIL_TITLE, content=content, body_class='theme-dark')


@router.get('/jobs/{job_id}/progress', response_class=HTMLResponse)
def job_progress_partial(job_id: str, session: Session = Depends(get_db_session)) -> str:
    service = JobService(session)
    job = service.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail='job not found')
    return render_progress_panel(job, service.get_report_id(job_id), service.get_latest_error_message(job_id), service.list_job_logs(job_id))


@router.get('/jobs/{job_id}/logs/view', response_class=HTMLResponse)
def job_logs_partial(job_id: str, session: Session = Depends(get_db_session)) -> str:
    service = JobService(session)
    if service.get_job(job_id) is None:
        raise HTTPException(status_code=404, detail='job not found')
    return render_log_list(service.list_job_logs(job_id))







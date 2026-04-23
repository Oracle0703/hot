from __future__ import annotations

from html import escape

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse, HTMLResponse
from sqlalchemy.orm import Session

from app.api.routes_sources import get_db_session
from app.schemas.report import ReportRead
from app.services.report_service import ReportService
from app.ui.page_theme import render_page, render_page_header, render_panel

router = APIRouter(tags=["reports"])

REPORTS_TITLE = "历史报告"
REPORT_DETAIL_TITLE = "报告预览"
GLOBAL_REPORT_TITLE = "全局热点总报告"


def _button_link(label: str, href: str, variant: str = "button-secondary") -> str:
    return f"<a class='button {variant}' href='{escape(href, quote=True)}'>{escape(label)}</a>"


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

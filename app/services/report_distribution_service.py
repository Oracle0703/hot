from __future__ import annotations

from pathlib import Path
import shutil

from app.config import Settings, get_settings
from app.models.report import Report


class ReportDistributionService:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    def copy_report_to_share_dir(self, report: Report) -> Path | None:
        share_dir = self.settings.report_share_dir.strip()
        if not share_dir:
            return None

        destination_dir = Path(share_dir)
        if not destination_dir.is_absolute():
            destination_dir = Path.cwd() / destination_dir
        destination_dir.mkdir(parents=True, exist_ok=True)

        markdown_path = Path(report.markdown_path)
        docx_path = Path(report.docx_path) if report.docx_path else None
        shutil.copy2(markdown_path, destination_dir / markdown_path.name)
        if docx_path is not None and docx_path.exists():
            shutil.copy2(docx_path, destination_dir / docx_path.name)
        return destination_dir

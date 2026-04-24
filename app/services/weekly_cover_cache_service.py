from __future__ import annotations

import hashlib
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import urlsplit

import httpx
from sqlalchemy.orm import Session

from app.models.item import CollectedItem
from app.runtime_paths import get_runtime_paths
from app.services.network_access_policy import build_httpx_request_kwargs


class WeeklyCoverCacheService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_cached_path(self, item: CollectedItem) -> Path | None:
        image_url = str(getattr(item, "cover_image_url", "") or "").strip()
        if not image_url:
            return None

        cache_dir = self._get_cache_dir()
        cache_dir.mkdir(parents=True, exist_ok=True)
        destination_path = cache_dir / self._build_cache_name(str(item.id), image_url)
        if destination_path.exists():
            return destination_path

        self._prune_item_versions(cache_dir, str(item.id), keep_path=destination_path)
        return self._download_image(image_url, destination_path)

    def prune(self, *, now: datetime | None = None, max_age_days: int = 60) -> None:
        cache_dir = self._get_cache_dir()
        if not cache_dir.exists():
            return

        current_time = now or datetime.utcnow()
        cutoff = current_time - timedelta(days=max_age_days)
        for candidate in cache_dir.iterdir():
            if not candidate.is_file():
                continue
            modified_at = datetime.utcfromtimestamp(candidate.stat().st_mtime)
            if modified_at < cutoff:
                candidate.unlink(missing_ok=True)

    def _get_cache_dir(self) -> Path:
        runtime_paths = get_runtime_paths()
        runtime_paths.ensure_directories()
        return runtime_paths.outputs_dir / "weekly-covers"

    def _build_cache_name(self, item_id: str, image_url: str) -> str:
        suffix = Path(urlsplit(image_url).path).suffix.lower() or ".jpg"
        if len(suffix) > 8:
            suffix = ".jpg"
        digest = hashlib.sha256(image_url.encode("utf-8")).hexdigest()[:12]
        return f"{item_id}-{digest}{suffix}"

    def _prune_item_versions(self, cache_dir: Path, item_id: str, *, keep_path: Path) -> None:
        for candidate in cache_dir.glob(f"{item_id}-*"):
            if candidate.resolve() != keep_path.resolve():
                candidate.unlink(missing_ok=True)

    def _download_image(self, image_url: str, destination_path: Path) -> Path | None:
        request_kwargs = build_httpx_request_kwargs(image_url)
        headers = self._build_headers(image_url)
        with httpx.Client(timeout=20.0, follow_redirects=True, headers=headers, **request_kwargs) as client:
            response = client.get(image_url)
            try:
                response.raise_for_status()
            except httpx.HTTPError:
                return None

        destination_path.parent.mkdir(parents=True, exist_ok=True)
        destination_path.write_bytes(response.content)
        return destination_path

    def _build_headers(self, image_url: str) -> dict[str, str]:
        host = (urlsplit(image_url).hostname or "").lower()
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36"
            )
        }
        if host.endswith("hdslb.com") or host.endswith("bilibili.com") or host.endswith("bilivideo.com"):
            headers["Referer"] = "https://www.bilibili.com/"
        return headers

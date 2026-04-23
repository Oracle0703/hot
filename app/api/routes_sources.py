from __future__ import annotations

from collections.abc import Generator
import re
from urllib.parse import parse_qs, urlsplit

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import ValidationError
from sqlalchemy.orm import Session, sessionmaker

from app.db import get_session
from app.schemas.source import CollectionStrategy, SourceCreate, SourceRead, SourceUpdate
from app.services.source_service import SourceService

router = APIRouter(prefix="/api/sources", tags=["sources"])


_BILIBILI_SPACE_PATH_RE = re.compile(r"^/(?P<mid>\d+)(?:/)?$")


def _extract_bilibili_space_mid(entry_url: str) -> str | None:
    parsed = urlsplit(entry_url)
    if parsed.scheme != "https" or parsed.netloc.lower() != "space.bilibili.com":
        return None
    match = _BILIBILI_SPACE_PATH_RE.match(parsed.path.rstrip("/") or parsed.path)
    if match is None:
        return None
    return match.group("mid")


class SessionFactoryHolder:
    factory: sessionmaker | None = None


def configure_session_factory(factory: sessionmaker) -> None:
    SessionFactoryHolder.factory = factory


def get_db_session() -> Generator[Session, None, None]:
    if SessionFactoryHolder.factory is None:
        raise RuntimeError("session factory is not configured")
    yield from get_session(SessionFactoryHolder.factory)


def _parse_form_list(value: str | None) -> list[str]:
    if not value:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


def _get_form_value(form_data: dict[str, list[str]], key: str, default: str = "") -> str:
    return form_data.get(key, [default])[0].strip()


def _normalize_optional_text(value: str) -> str | None:
    return value or None


def _infer_collection_strategy(entry_url: str, explicit_strategy: str | None) -> CollectionStrategy:
    if explicit_strategy:
        return explicit_strategy  # type: ignore[return-value]

    host = urlsplit(entry_url).netloc.lower()
    if "youtube.com" in host or "youtu.be" in host:
        return "youtube_channel_recent"
    if host == "space.bilibili.com" and _extract_bilibili_space_mid(entry_url):
        return "bilibili_profile_videos_recent"
    if "bilibili.com" in host:
        return "bilibili_site_search"
    if host in {"x.com", "www.x.com", "twitter.com", "www.twitter.com"}:
        return "x_profile_recent"
    raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="unsupported entry_url for simplified source form")


def _infer_source_name(entry_url: str, strategy: CollectionStrategy, search_keyword: str | None) -> str:
    parsed = urlsplit(entry_url)
    path_parts = [part for part in parsed.path.split("/") if part]
    if strategy == "youtube_channel_recent":
        channel_name = path_parts[0].lstrip("@") if path_parts else parsed.netloc
        return f"YouTube-{channel_name}"
    if strategy == "bilibili_site_search":
        return f"B站-{search_keyword}-站内搜索"
    if strategy == "bilibili_profile_videos_recent":
        mid = _extract_bilibili_space_mid(entry_url) or parsed.netloc
        return f"B站UP-{mid}-视频投稿"
    if strategy == "x_profile_recent":
        profile_name = path_parts[0].lstrip("@") if path_parts else parsed.netloc
        return f"X-{profile_name}"
    return parsed.netloc or entry_url

def _build_form_payload(form_data: dict[str, list[str]]) -> SourceCreate:
    entry_url = _get_form_value(form_data, "entry_url")
    max_items_raw = _get_form_value(form_data, "max_items", "30")
    explicit_strategy = _normalize_optional_text(_get_form_value(form_data, "collection_strategy"))
    search_keyword = _normalize_optional_text(_get_form_value(form_data, "search_keyword"))
    strategy = _infer_collection_strategy(entry_url, explicit_strategy)

    if strategy == "bilibili_site_search" and not search_keyword:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="search_keyword is required for bilibili_site_search")

    name = _normalize_optional_text(_get_form_value(form_data, "name")) or _infer_source_name(entry_url, strategy, search_keyword)
    site_name = _normalize_optional_text(_get_form_value(form_data, "site_name"))
    fetch_mode = _normalize_optional_text(_get_form_value(form_data, "fetch_mode"))
    parser_type = _normalize_optional_text(_get_form_value(form_data, "parser_type"))
    source_group = _normalize_optional_text(_get_form_value(form_data, "source_group"))

    if not source_group:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="source_group is required")

    if strategy == "youtube_channel_recent":
        site_name = site_name or "YouTube"
        fetch_mode = fetch_mode or "playwright"
        parser_type = None
    elif strategy == "bilibili_site_search":
        site_name = site_name or "Bilibili"
        fetch_mode = fetch_mode or "playwright"
        parser_type = None
    elif strategy == "bilibili_profile_videos_recent":
        site_name = site_name or "Bilibili"
        fetch_mode = fetch_mode or "playwright"
        parser_type = None
    elif strategy == "x_profile_recent":
        site_name = site_name or "X"
        fetch_mode = fetch_mode or "playwright"
        parser_type = None
    else:
        fetch_mode = fetch_mode or "http"
        parser_type = parser_type or "generic_css"

    try:
        return SourceCreate(
            name=name,
            site_name=site_name,
            entry_url=entry_url,
            fetch_mode=fetch_mode,
            parser_type=parser_type,
            list_selector=_normalize_optional_text(_get_form_value(form_data, "list_selector")),
            title_selector=_normalize_optional_text(_get_form_value(form_data, "title_selector")),
            link_selector=_normalize_optional_text(_get_form_value(form_data, "link_selector")),
            meta_selector=_normalize_optional_text(_get_form_value(form_data, "meta_selector")),
            include_keywords=_parse_form_list(_get_form_value(form_data, "include_keywords")),
            exclude_keywords=_parse_form_list(_get_form_value(form_data, "exclude_keywords")),
            max_items=(30 if max_items_raw == "" else max_items_raw),
            enabled=True,
            source_group=source_group,
            collection_strategy=strategy,
            search_keyword=search_keyword,
        )
    except ValidationError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=exc.errors()) from exc


@router.get("", response_model=list[SourceRead])
def list_sources(session: Session = Depends(get_db_session)) -> list[SourceRead]:
    service = SourceService(session)
    return service.list_sources()


@router.post("", response_model=SourceRead, status_code=status.HTTP_201_CREATED)
def create_source(payload: SourceCreate, session: Session = Depends(get_db_session)) -> SourceRead:
    service = SourceService(session)
    return service.create_source(payload)


@router.put("/{source_id}", response_model=SourceRead)
def update_source(source_id: str, payload: SourceUpdate, session: Session = Depends(get_db_session)) -> SourceRead:
    service = SourceService(session)
    source = service.update_source(source_id, payload)
    if source is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="source not found")
    return source


@router.delete("/{source_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_source(source_id: str, session: Session = Depends(get_db_session)) -> Response:
    service = SourceService(session)
    deleted = service.delete_source(source_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="source not found")
    return Response(status_code=status.HTTP_204_NO_CONTENT)



@router.post("/{source_id}/delete", status_code=status.HTTP_303_SEE_OTHER)
def delete_source_from_form(source_id: str, session: Session = Depends(get_db_session)) -> Response:
    service = SourceService(session)
    deleted = service.delete_source(source_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="source not found")
    response = Response(status_code=status.HTTP_303_SEE_OTHER)
    response.headers["Location"] = "/sources"
    return response
@router.post("/form", status_code=status.HTTP_303_SEE_OTHER)
async def create_source_from_form(request: Request, session: Session = Depends(get_db_session)) -> Response:
    content_type = request.headers.get("content-type", "")
    if not content_type.startswith("application/x-www-form-urlencoded"):
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="unsupported content type, use application/x-www-form-urlencoded",
        )

    form_data = parse_qs((await request.body()).decode("utf-8"))
    payload = _build_form_payload(form_data)

    service = SourceService(session)
    service.create_source(payload)
    response = Response(status_code=status.HTTP_303_SEE_OTHER)
    response.headers["Location"] = "/sources"
    return response



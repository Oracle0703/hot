from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.routes_sources import get_db_session
from app.schemas.site_account import SiteAccountCreate, SiteAccountRead, SiteAccountUpdate
from app.services.site_account_service import SiteAccountService


router = APIRouter(prefix="/api/site-accounts", tags=["site-accounts"])


@router.get("", response_model=list[SiteAccountRead])
def list_site_accounts(
    platform: str | None = None,
    session: Session = Depends(get_db_session),
) -> list[SiteAccountRead]:
    return SiteAccountService(session).list_accounts(platform=platform)


@router.post("", response_model=SiteAccountRead, status_code=status.HTTP_201_CREATED)
def create_site_account(payload: SiteAccountCreate, session: Session = Depends(get_db_session)) -> SiteAccountRead:
    return SiteAccountService(session).create_account(payload)


@router.put("/{account_id}", response_model=SiteAccountRead)
def update_site_account(
    account_id: str,
    payload: SiteAccountUpdate,
    session: Session = Depends(get_db_session),
) -> SiteAccountRead:
    updated = SiteAccountService(session).update_account(account_id, payload)
    if updated is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="site account not found")
    return updated


@router.post("/{account_id}/set-default", response_model=SiteAccountRead)
def set_default_site_account(account_id: str, session: Session = Depends(get_db_session)) -> SiteAccountRead:
    try:
        return SiteAccountService(session).set_default_account(account_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

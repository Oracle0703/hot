from __future__ import annotations

from pathlib import Path

import pytest

from app.db import create_session_factory, get_engine
from app.models.base import Base
from app.schemas.site_account import SiteAccountCreate
from app.services.site_account_service import SiteAccountService


def make_database_url(tmp_path: Path, name: str) -> str:
    return f"sqlite:///{(tmp_path / name).as_posix()}"


def setup_database(tmp_path: Path, name: str):
    import os

    os.environ["DATABASE_URL"] = make_database_url(tmp_path, name)
    engine = get_engine()
    Base.metadata.create_all(bind=engine)
    return create_session_factory(engine=engine)


def test_site_account_service_set_default_account_clears_old_default(tmp_path) -> None:
    session_factory = setup_database(tmp_path, "site-account-default.db")
    with session_factory() as session:
        service = SiteAccountService(session)
        first = service.create_account(
            SiteAccountCreate(
                platform="bilibili",
                account_key="default",
                display_name="默认账号",
                is_default=True,
            )
        )
        second = service.create_account(
            SiteAccountCreate(
                platform="bilibili",
                account_key="creator-a",
                display_name="账号A",
            )
        )

        updated = service.set_default_account(str(second.id))

        session.refresh(first)
        assert updated.is_default is True
        assert first.is_default is False


def test_site_account_service_create_account_normalizes_account_key(tmp_path) -> None:
    session_factory = setup_database(tmp_path, "site-account-normalize.db")
    with session_factory() as session:
        service = SiteAccountService(session)

        created = service.create_account(
            SiteAccountCreate(
                platform="bilibili",
                account_key="Creator A",
                display_name="账号A",
            )
        )

        assert created.account_key == "creator-a"


def test_site_account_service_ensure_bindable_account_rejects_disabled_account(tmp_path) -> None:
    session_factory = setup_database(tmp_path, "site-account-disabled.db")
    with session_factory() as session:
        service = SiteAccountService(session)
        created = service.create_account(
            SiteAccountCreate(
                platform="bilibili",
                account_key="creator-a",
                display_name="账号A",
                enabled=False,
            )
        )

        with pytest.raises(ValueError, match="disabled|禁用"):
            service.ensure_bindable_account(str(created.id))

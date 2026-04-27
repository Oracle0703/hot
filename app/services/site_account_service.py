from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.site_account import SiteAccount
from app.schemas.site_account import SiteAccountCreate, SiteAccountUpdate, normalize_account_key


class SiteAccountService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_account(self, account_id: str) -> SiteAccount | None:
        return self.session.get(SiteAccount, UUID(account_id))

    def list_accounts(self, platform: str | None = None) -> list[SiteAccount]:
        statement = select(SiteAccount)
        if platform:
            statement = statement.where(SiteAccount.platform == str(platform).strip().lower())
        statement = statement.order_by(SiteAccount.platform.asc(), SiteAccount.account_key.asc())
        return list(self.session.scalars(statement).all())

    def create_account(self, data: SiteAccountCreate) -> SiteAccount:
        payload = data.model_dump()
        payload["platform"] = str(payload["platform"]).strip().lower()
        payload["account_key"] = normalize_account_key(str(payload["account_key"]))
        account = SiteAccount(**payload)
        self.session.add(account)
        self.session.flush()
        if account.is_default:
            self._clear_other_defaults(account.platform, account.id)
        self.session.commit()
        self.session.refresh(account)
        return account

    def update_account(self, account_id: str, data: SiteAccountUpdate) -> SiteAccount | None:
        account = self.get_account(account_id)
        if account is None:
            return None

        for field_name, value in data.model_dump(exclude_unset=True).items():
            setattr(account, field_name, value)
        if account.is_default:
            self._clear_other_defaults(account.platform, account.id)
        self.session.commit()
        self.session.refresh(account)
        return account

    def set_default_account(self, account_id: str) -> SiteAccount:
        account = self.ensure_account(account_id)
        account.is_default = True
        self._clear_other_defaults(account.platform, account.id)
        self.session.commit()
        self.session.refresh(account)
        return account

    def get_default_account(self, platform: str) -> SiteAccount | None:
        statement = (
            select(SiteAccount)
            .where(SiteAccount.platform == str(platform).strip().lower())
            .where(SiteAccount.is_default.is_(True))
            .limit(1)
        )
        return self.session.scalar(statement)

    def ensure_account(self, account_id: str) -> SiteAccount:
        account = self.get_account(account_id)
        if account is None:
            raise ValueError("site account not found")
        return account

    def ensure_bindable_account(self, account_id: str) -> SiteAccount:
        account = self.ensure_account(account_id)
        if not account.enabled:
            raise ValueError("site account is disabled")
        return account

    def _clear_other_defaults(self, platform: str, keep_id) -> None:
        accounts = self.session.scalars(select(SiteAccount).where(SiteAccount.platform == platform)).all()
        for account in accounts:
            if account.id == keep_id:
                continue
            if account.is_default:
                account.is_default = False

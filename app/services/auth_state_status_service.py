from __future__ import annotations

import json
from datetime import datetime, timezone
from types import SimpleNamespace
from typing import Any, Callable

from sqlalchemy.exc import SQLAlchemyError

from app.db import create_session_factory, get_engine
from app.services.app_env_service import AppEnvService
from app.services.auth_state_service import AuthStateService
from app.services.site_account_service import SiteAccountService


class AuthStateStatusService:
    def __init__(
        self,
        *,
        app_env_service: AppEnvService | None = None,
        auth_state_service: AuthStateService | None = None,
        site_accounts_provider: Callable[[], list[object]] | None = None,
    ) -> None:
        self.auth_state_service = auth_state_service or AuthStateService()
        self.app_env_service = app_env_service or AppEnvService(
            env_file=self.auth_state_service.runtime_root / "data" / "app.env"
        )
        self.site_accounts_provider = site_accounts_provider or self._default_site_accounts_provider

    def build_snapshot(self) -> dict[str, Any]:
        platforms = [self._build_bilibili_snapshot()]
        return {
            "status": self._overall_status(platforms),
            "runtime_root": str(self.auth_state_service.runtime_root),
            "checked_at": datetime.now(timezone.utc).isoformat(),
            "platforms": platforms,
        }

    def _build_bilibili_snapshot(self) -> dict[str, Any]:
        accounts = [self._build_bilibili_account_snapshot(account) for account in self._iter_bilibili_accounts()]
        issues = [issue for account in accounts for issue in account.get("issues", [])]
        return {
            "platform": "bilibili",
            "display_name": "B站",
            "status": self._overall_status(accounts),
            "action_hint": self._platform_action_hint(accounts),
            "issues": issues,
            "accounts": accounts,
        }

    def _build_bilibili_account_snapshot(self, account) -> dict[str, Any]:
        account_key = str(getattr(account, "account_key", "default") or "default")
        display_name = str(getattr(account, "display_name", "") or account_key or "默认账号")
        auth_paths = self.auth_state_service.build_paths("bilibili", account_key)
        action_hint = "前往 /scheduler 重新同步 B站登录态"
        storage_state_exists = auth_paths.storage_state_file.exists()
        user_data_dir_exists = auth_paths.user_data_dir.exists()

        try:
            bilibili_settings = self.app_env_service.get_bilibili_settings(account_key=account_key)
            cookie_configured = bool(bilibili_settings.cookie.strip())
        except Exception as exc:
            return self._build_account_snapshot(
                account=account,
                display_name=display_name,
                status="error",
                cookie_configured=False,
                storage_state_exists=storage_state_exists,
                user_data_dir_exists=user_data_dir_exists,
                storage_state_file=str(auth_paths.storage_state_file),
                user_data_dir=str(auth_paths.user_data_dir),
                action_hint=action_hint,
                issues=[f"读取 B站登录态配置失败: {type(exc).__name__}: {exc}"],
            )

        if storage_state_exists:
            try:
                payload = json.loads(auth_paths.storage_state_file.read_text(encoding="utf-8"))
                if not isinstance(payload, dict):
                    raise ValueError("storage state 根对象必须是 JSON object")
            except Exception as exc:
                return self._build_account_snapshot(
                    account=account,
                    display_name=display_name,
                    status="error",
                    cookie_configured=cookie_configured,
                    storage_state_exists=storage_state_exists,
                    user_data_dir_exists=user_data_dir_exists,
                    storage_state_file=str(auth_paths.storage_state_file),
                    user_data_dir=str(auth_paths.user_data_dir),
                    action_hint=action_hint,
                    issues=[f"storage state 文件无效: {type(exc).__name__}: {exc}"],
                )

        issues: list[str] = []
        if cookie_configured and storage_state_exists and user_data_dir_exists:
            status = "ok"
            action_hint = "状态正常，无需操作"
        elif cookie_configured and storage_state_exists and not user_data_dir_exists:
            status = "warning"
            issues.append("浏览器 user-data 目录缺失")
        elif cookie_configured and not storage_state_exists:
            status = "warning"
            issues.append("storage state 文件缺失")
        elif not cookie_configured and storage_state_exists:
            status = "warning"
            issues.append("storage state 文件存在，但 B站 Cookie 未配置")
        else:
            status = "missing"
            issues.append("尚未配置 B站登录态")

        return self._build_account_snapshot(
            account=account,
            display_name=display_name,
            status=status,
            cookie_configured=cookie_configured,
            storage_state_exists=storage_state_exists,
            user_data_dir_exists=user_data_dir_exists,
            storage_state_file=str(auth_paths.storage_state_file),
            user_data_dir=str(auth_paths.user_data_dir),
            action_hint=action_hint,
            issues=issues,
        )

    def _iter_bilibili_accounts(self) -> list[object]:
        accounts = [account for account in self.site_accounts_provider() if getattr(account, "platform", "") == "bilibili"]
        has_default_key = any(str(getattr(account, "account_key", "") or "") == "default" for account in accounts)
        has_default_flag = any(bool(getattr(account, "is_default", False)) for account in accounts)
        if not has_default_key:
            accounts.append(
                SimpleNamespace(
                    id=None,
                    platform="bilibili",
                    account_key="default",
                    display_name="默认账号",
                    enabled=True,
                    is_default=not has_default_flag,
                )
            )
        return sorted(accounts, key=lambda item: (0 if str(getattr(item, "account_key", "")) == "default" else 1, str(getattr(item, "account_key", ""))))

    @staticmethod
    def _build_account_snapshot(
        *,
        account,
        display_name: str,
        status: str,
        cookie_configured: bool,
        storage_state_exists: bool,
        user_data_dir_exists: bool,
        storage_state_file: str,
        user_data_dir: str,
        action_hint: str,
        issues: list[str],
    ) -> dict[str, Any]:
        account_id = getattr(account, "id", None)
        return {
            "account_id": str(account_id) if account_id is not None else None,
            "account_key": str(getattr(account, "account_key", "default") or "default"),
            "display_name": display_name,
            "enabled": bool(getattr(account, "enabled", True)),
            "is_default": bool(getattr(account, "is_default", False)),
            "status": status,
            "cookie_configured": cookie_configured,
            "storage_state_exists": storage_state_exists,
            "user_data_dir_exists": user_data_dir_exists,
            "storage_state_file": storage_state_file,
            "user_data_dir": user_data_dir,
            "action_hint": action_hint,
            "issues": issues,
        }

    @staticmethod
    def _platform_action_hint(accounts: list[dict[str, Any]]) -> str:
        for account in accounts:
            if str(account.get("status") or "") != "ok":
                return str(account.get("action_hint") or "前往 /scheduler 重新同步 B站登录态")
        return "状态正常，无需操作"

    @staticmethod
    def _overall_status(items: list[dict[str, Any]]) -> str:
        statuses = [str(item.get("status") or "") for item in items]
        if any(status == "error" for status in statuses):
            return "error"
        if any(status == "warning" for status in statuses):
            return "warning"
        if statuses and all(status == "missing" for status in statuses):
            return "missing"
        return "ok"

    @staticmethod
    def _default_site_accounts_provider() -> list[object]:
        from app.api.routes_sources import SessionFactoryHolder

        session_factory = SessionFactoryHolder.factory or create_session_factory(engine=get_engine())
        try:
            with session_factory() as session:
                return SiteAccountService(session).list_accounts(platform="bilibili")
        except SQLAlchemyError:
            return []

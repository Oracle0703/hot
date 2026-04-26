from __future__ import annotations

from app.services.auth_state_service import AuthStateService


def test_auth_state_service_builds_single_user_paths(tmp_path) -> None:
    service = AuthStateService(runtime_root=tmp_path)

    paths = service.build_paths(platform="bilibili")

    assert paths.user_data_dir == tmp_path / "data" / "bilibili-user-data"
    assert paths.storage_state_file == tmp_path / "data" / "bilibili-storage-state.json"

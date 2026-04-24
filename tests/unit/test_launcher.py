from __future__ import annotations

from pathlib import Path

from launcher import build_browser_url, build_runtime_environment, load_env_file
from app.runtime_paths import RuntimePaths


def make_runtime_paths(root: Path) -> RuntimePaths:
    return RuntimePaths(
        runtime_root=root,
        data_dir=root / 'data',
        logs_dir=root / 'logs',
        outputs_dir=root / 'outputs',
        reports_dir=root / 'outputs' / 'reports',
        playwright_browsers_dir=root / 'playwright-browsers',
        bilibili_user_data_dir=root / 'data' / 'bilibili-user-data',
        bilibili_storage_state_file=root / 'data' / 'bilibili-storage-state.json',
        env_file=root / 'data' / 'app.env',
        pid_file=root / 'data' / 'launcher.pid',
        launcher_log_file=root / 'logs' / 'launcher.log',
        app_log_file=root / 'logs' / 'app.log',
    )


def test_load_env_file_reads_simple_key_values(tmp_path) -> None:
    env_file = tmp_path / 'app.env'
    env_file.write_text(
        '# comment\nAPP_NAME=运营版热点工具\nENABLE_SCHEDULER=false\nREPORTS_ROOT=outputs/custom-reports\n',
        encoding='utf-8',
    )

    values = load_env_file(env_file)

    assert values == {
        'APP_NAME': '运营版热点工具',
        'ENABLE_SCHEDULER': 'false',
        'REPORTS_ROOT': 'outputs/custom-reports',
    }


def test_build_runtime_environment_sets_packaged_defaults(tmp_path) -> None:
    paths = make_runtime_paths(tmp_path)

    values = build_runtime_environment(paths, file_values={}, process_env={})

    assert values['DATABASE_URL'] == f"sqlite:///{(tmp_path / 'data' / 'hot_topics.db').as_posix()}"
    assert values['REPORTS_ROOT'] == str(tmp_path / 'outputs' / 'reports')
    assert values['PLAYWRIGHT_BROWSERS_PATH'] == str(tmp_path / 'playwright-browsers')
    assert values['HOT_RUNTIME_ROOT'] == str(tmp_path)


def test_build_runtime_environment_prefers_process_env_over_file_values(tmp_path) -> None:
    paths = make_runtime_paths(tmp_path)

    values = build_runtime_environment(
        paths,
        file_values={
            'APP_NAME': '包内默认名',
            'REPORTS_ROOT': 'outputs/custom-reports',
        },
        process_env={
            'APP_NAME': '外部覆盖名',
        },
    )

    assert values['APP_NAME'] == '外部覆盖名'
    assert values['REPORTS_ROOT'] == str(tmp_path / 'outputs' / 'custom-reports')


def test_build_runtime_environment_loads_dingtalk_values_from_env_file(tmp_path) -> None:
    paths = make_runtime_paths(tmp_path)

    values = build_runtime_environment(
        paths,
        file_values={
            'ENABLE_DINGTALK_NOTIFIER': 'true',
            'DINGTALK_WEBHOOK': 'https://oapi.dingtalk.com/robot/send?access_token=test-token',
            'DINGTALK_SECRET': 'SECdemo',
            'DINGTALK_KEYWORD': '热点报告',
        },
        process_env={},
    )

    assert values['ENABLE_DINGTALK_NOTIFIER'] == 'true'
    assert values['DINGTALK_WEBHOOK'].endswith('access_token=test-token')
    assert values['DINGTALK_SECRET'] == 'SECdemo'
    assert values['DINGTALK_KEYWORD'] == '热点报告'


def test_build_runtime_environment_reads_weekly_settings_from_process_env(tmp_path) -> None:
    paths = make_runtime_paths(tmp_path)

    values = build_runtime_environment(
        paths,
        file_values={},
        process_env={
            'WEEKLY_COVER_CACHE_RETENTION_DAYS': '45',
            'WEEKLY_GRADE_PUSH_THRESHOLD': 'A',
        },
    )

    assert values['WEEKLY_COVER_CACHE_RETENTION_DAYS'] == '45'
    assert values['WEEKLY_GRADE_PUSH_THRESHOLD'] == 'A'


def test_build_browser_url_uses_loopback_for_wildcard_host() -> None:
    assert build_browser_url('0.0.0.0', 38080) == 'http://127.0.0.1:38080/'

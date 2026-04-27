from __future__ import annotations

import subprocess
import json
import sys
from pathlib import Path

from tests.conftest import create_test_client, make_sqlite_url


ROOT = Path(__file__).resolve().parents[2]
BOOTSTRAP = ROOT / "scripts" / "bootstrap.ps1"
RUN = ROOT / "scripts" / "run.ps1"
BUILD = ROOT / "scripts" / "build_package.ps1"
BUILD_DESKTOP_SHELL = ROOT / "scripts" / "build_desktop_shell.ps1"
PREPARE = ROOT / "scripts" / "prepare_release.ps1"
PREPARE_UPGRADE = ROOT / "scripts" / "prepare_upgrade_release.ps1"
BUILD_OFFLINE = ROOT / "scripts" / "build_offline_release.ps1"
BUILD_UPGRADE = ROOT / "scripts" / "build_upgrade_release.ps1"
LAUNCHER = ROOT / "launcher.py"
DESKTOP_MANIFEST_CONSUMER = ROOT / "scripts" / "desktop_manifest_consumer.py"


def run_ps1(script: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            "powershell",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(script),
            *args,
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


def test_bootstrap_dry_run_prefers_repo_venv_python() -> None:
    result = run_ps1(BOOTSTRAP, "-DryRun")

    assert result.returncode == 0
    assert ".venv\\Scripts\\python.exe" in result.stdout
    assert "pip install -r requirements.txt" in result.stdout


def test_bootstrap_can_optionally_install_playwright() -> None:
    result = run_ps1(BOOTSTRAP, "-DryRun", "-InstallPlaywright")

    assert result.returncode == 0
    assert "playwright install chromium" in result.stdout


def test_run_script_builds_uvicorn_command_with_repo_venv_python() -> None:
    result = run_ps1(RUN, "-DryRun")

    assert result.returncode == 0
    assert ".venv\\Scripts\\python.exe" in result.stdout
    assert "-m uvicorn app.main:app --reload" in result.stdout


def test_build_package_script_renders_pyinstaller_command() -> None:
    result = run_ps1(BUILD, "-DryRun")

    assert result.returncode == 0
    assert "pyinstaller" in result.stdout.lower()
    assert "hot_collector.spec" in result.stdout


def test_prepare_release_script_renders_release_assembly_steps() -> None:
    result = run_ps1(PREPARE, "-DryRun")

    assert result.returncode == 0
    assert "release\\HotCollector" in result.stdout
    assert "HotCollectorLauncher.exe" in result.stdout
    assert "desktop-shell" in result.stdout
    assert "打开桌面版.bat" in result.stdout


def test_prepare_upgrade_release_script_renders_upgrade_assembly_steps() -> None:
    result = run_ps1(PREPARE_UPGRADE, "-DryRun")

    assert result.returncode == 0
    assert "release\\HotCollector-Upgrade" in result.stdout
    assert "HotCollectorLauncher.exe" in result.stdout
    assert "desktop-shell" in result.stdout
    assert "打开桌面版.bat" in result.stdout


def test_build_upgrade_release_script_prefers_tar_archive() -> None:
    result = run_ps1(BUILD_UPGRADE, "-DryRun", "-SkipBuild")

    assert result.returncode == 0
    assert "tar.exe -a -cf" in result.stdout
    assert "prepare_upgrade_release.ps1" in result.stdout
    assert "build_desktop_shell.ps1" in result.stdout


def test_build_desktop_shell_script_renders_electron_assembly_steps() -> None:
    result = run_ps1(BUILD_DESKTOP_SHELL, "-DryRun")

    assert result.returncode == 0
    assert "npm install" in result.stdout
    assert "desktop-shell" in result.stdout
    assert "electron.exe" in result.stdout
    assert "tray.png" in result.stdout


def test_build_desktop_shell_repairs_incomplete_electron_runtime() -> None:
    source_root = ROOT / "tmp_test_build_desktop_shell_source"
    output_root = ROOT / "tmp_test_build_desktop_shell_out"
    try:
        for path in (source_root, output_root):
            if path.exists():
                subprocess.run(["powershell", "-Command", f"Remove-Item -Recurse -Force '{path}'"], check=False)

        (source_root / "assets").mkdir(parents=True, exist_ok=True)
        (source_root / "node_modules" / "electron" / "dist").mkdir(parents=True, exist_ok=True)

        (source_root / "package.json").write_text(
            json.dumps(
                {
                    "name": "desktop-shell-test-fixture",
                    "version": "0.0.1",
                    "private": True,
                }
            ),
            encoding="utf-8",
        )
        (source_root / "main.js").write_text("console.log('desktop shell');\n", encoding="utf-8")
        (source_root / "shell-state.js").write_text("module.exports = {};\n", encoding="utf-8")
        (source_root / "assets" / "tray.png").write_bytes(b"stub")
        (source_root / "node_modules" / "electron" / "dist" / "version").write_text("33.4.11", encoding="utf-8")
        (source_root / "node_modules" / "electron" / "install.js").write_text(
            """
const fs = require("fs");
const path = require("path");

const root = __dirname;
const dist = path.join(root, "dist");
fs.mkdirSync(dist, { recursive: true });
fs.writeFileSync(path.join(dist, "electron.exe"), "stub");
fs.writeFileSync(path.join(root, "path.txt"), "electron.exe");
fs.writeFileSync(path.join(root, "install-ran.txt"), "yes");
""".strip()
            + "\n",
            encoding="utf-8",
        )

        result = run_ps1(
            BUILD_DESKTOP_SHELL,
            "-SourceRoot",
            str(source_root.relative_to(ROOT)),
            "-OutputRoot",
            str(output_root.relative_to(ROOT)),
        )

        assert result.returncode == 0, result.stderr or result.stdout
        assert (source_root / "node_modules" / "electron" / "install-ran.txt").exists()
        assert (source_root / "node_modules" / "electron" / "path.txt").read_text(encoding="utf-8") == "electron.exe"
        assert (output_root / "runtime" / "electron.exe").exists()
    finally:
        for path in (source_root, output_root):
            if path.exists():
                subprocess.run(["powershell", "-Command", f"Remove-Item -Recurse -Force '{path}'"], check=False)


def test_desktop_shell_state_helpers_pass_node_tests() -> None:
    result = subprocess.run(
        ["node", "--test", str(ROOT / "desktop-shell" / "electron" / "shell-state.test.js")],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr or result.stdout




def test_prepare_release_generates_stop_script_that_removes_pid_file() -> None:
    dist_root = ROOT / "tmp_test_prepare_release_dist"
    release_root = ROOT / "tmp_test_prepare_release_out"
    desktop_shell_root = ROOT / "tmp_test_prepare_release_shell"
    try:
        if dist_root.exists():
            subprocess.run(["powershell", "-Command", f"Remove-Item -Recurse -Force '{dist_root}'"], check=False)
        if release_root.exists():
            subprocess.run(["powershell", "-Command", f"Remove-Item -Recurse -Force '{release_root}'"], check=False)
        if desktop_shell_root.exists():
            subprocess.run(["powershell", "-Command", f"Remove-Item -Recurse -Force '{desktop_shell_root}'"], check=False)

        dist_root.mkdir(parents=True, exist_ok=True)
        (desktop_shell_root / "runtime").mkdir(parents=True, exist_ok=True)
        (dist_root / "HotCollectorLauncher.exe").write_text("stub", encoding="utf-8")
        (desktop_shell_root / "launch-desktop-shell.bat").write_text("@echo off\r\necho desktop shell\r\n", encoding="utf-8")
        (desktop_shell_root / "runtime" / "electron.exe").write_text("stub", encoding="utf-8")

        result = run_ps1(
            PREPARE,
            "-ReleaseRoot",
            str(release_root.relative_to(ROOT)),
            "-DistRoot",
            str(dist_root.relative_to(ROOT)),
            "-DesktopShellDistRoot",
            str(desktop_shell_root.relative_to(ROOT)),
        )

        assert result.returncode == 0
        stop_script = (release_root / "停止系统.bat").read_text(encoding="utf-8")
        status_script = (release_root / "查看状态.bat").read_text(encoding="utf-8")
        desktop_script = (release_root / "打开桌面版.bat").read_text(encoding="utf-8")
        assert "Remove-Item -Path $pidFile -Force" in stop_script
        assert "HotCollectorLauncher.exe --probe --print-json" in status_script
        assert (release_root / "desktop-shell" / "launch-desktop-shell.bat").exists()
        assert (release_root / "desktop-shell" / "runtime" / "electron.exe").exists()
        assert (release_root / "outputs" / "weekly-covers").exists()
        app_env = (release_root / "data" / "app.env").read_text(encoding="utf-8")
        assert "WEEKLY_GRADE_PUSH_THRESHOLD=B+" in app_env
        assert "WEEKLY_COVER_CACHE_RETENTION_DAYS=60" in app_env
        assert "desktop-shell\\launch-desktop-shell.bat" in desktop_script
    finally:
        if dist_root.exists():
            subprocess.run(["powershell", "-Command", f"Remove-Item -Recurse -Force '{dist_root}'"], check=False)
        if release_root.exists():
            subprocess.run(["powershell", "-Command", f"Remove-Item -Recurse -Force '{release_root}'"], check=False)
        if desktop_shell_root.exists():
            subprocess.run(["powershell", "-Command", f"Remove-Item -Recurse -Force '{desktop_shell_root}'"], check=False)


def test_prepare_upgrade_release_generates_program_only_package() -> None:
    dist_root = ROOT / "tmp_test_prepare_upgrade_dist"
    release_root = ROOT / "tmp_test_prepare_upgrade_out"
    desktop_shell_root = ROOT / "tmp_test_prepare_upgrade_shell"
    try:
        if dist_root.exists():
            subprocess.run(["powershell", "-Command", f"Remove-Item -Recurse -Force '{dist_root}'"], check=False)
        if release_root.exists():
            subprocess.run(["powershell", "-Command", f"Remove-Item -Recurse -Force '{release_root}'"], check=False)
        if desktop_shell_root.exists():
            subprocess.run(["powershell", "-Command", f"Remove-Item -Recurse -Force '{desktop_shell_root}'"], check=False)

        (dist_root / "_internal").mkdir(parents=True, exist_ok=True)
        (desktop_shell_root / "runtime").mkdir(parents=True, exist_ok=True)
        (dist_root / "HotCollectorLauncher.exe").write_text("stub", encoding="utf-8")
        (dist_root / "_internal" / "runtime.txt").write_text("stub", encoding="utf-8")
        (desktop_shell_root / "launch-desktop-shell.bat").write_text("@echo off\r\necho desktop shell\r\n", encoding="utf-8")
        (desktop_shell_root / "runtime" / "electron.exe").write_text("stub", encoding="utf-8")

        result = run_ps1(
            PREPARE_UPGRADE,
            "-ReleaseRoot",
            str(release_root.relative_to(ROOT)),
            "-DistRoot",
            str(dist_root.relative_to(ROOT)),
            "-DesktopShellDistRoot",
            str(desktop_shell_root.relative_to(ROOT)),
        )

        assert result.returncode == 0
        assert (release_root / "HotCollectorLauncher.exe").exists()
        assert (release_root / "_internal" / "runtime.txt").exists()
        assert (release_root / "启动系统.bat").exists()
        assert (release_root / "停止系统.bat").exists()
        assert (release_root / "查看状态.bat").exists()
        assert (release_root / "打开桌面版.bat").exists()
        assert (release_root / "README-运营版.txt").exists()
        assert (release_root / "desktop-shell" / "launch-desktop-shell.bat").exists()
        assert (release_root / "data").exists() is False
        assert (release_root / "logs").exists() is False
        assert (release_root / "outputs").exists() is False
        assert (release_root / "playwright-browsers").exists() is False
    finally:
        if dist_root.exists():
            subprocess.run(["powershell", "-Command", f"Remove-Item -Recurse -Force '{dist_root}'"], check=False)
        if release_root.exists():
            subprocess.run(["powershell", "-Command", f"Remove-Item -Recurse -Force '{release_root}'"], check=False)
        if desktop_shell_root.exists():
            subprocess.run(["powershell", "-Command", f"Remove-Item -Recurse -Force '{desktop_shell_root}'"], check=False)


def test_prepare_release_generates_stop_script_without_using_reserved_pid_variable() -> None:
    dist_root = ROOT / "tmp_test_prepare_release_dist_reserved"
    release_root = ROOT / "tmp_test_prepare_release_out_reserved"
    desktop_shell_root = ROOT / "tmp_test_prepare_release_shell_reserved"
    try:
        if dist_root.exists():
            subprocess.run(["powershell", "-Command", f"Remove-Item -Recurse -Force '{dist_root}'"], check=False)
        if release_root.exists():
            subprocess.run(["powershell", "-Command", f"Remove-Item -Recurse -Force '{release_root}'"], check=False)
        if desktop_shell_root.exists():
            subprocess.run(["powershell", "-Command", f"Remove-Item -Recurse -Force '{desktop_shell_root}'"], check=False)

        dist_root.mkdir(parents=True, exist_ok=True)
        (desktop_shell_root / "runtime").mkdir(parents=True, exist_ok=True)
        (dist_root / "HotCollectorLauncher.exe").write_text("stub", encoding="utf-8")
        (desktop_shell_root / "launch-desktop-shell.bat").write_text("@echo off\r\necho desktop shell\r\n", encoding="utf-8")
        (desktop_shell_root / "runtime" / "electron.exe").write_text("stub", encoding="utf-8")

        result = run_ps1(
            PREPARE,
            "-ReleaseRoot",
            str(release_root.relative_to(ROOT)),
            "-DistRoot",
            str(dist_root.relative_to(ROOT)),
            "-DesktopShellDistRoot",
            str(desktop_shell_root.relative_to(ROOT)),
        )

        assert result.returncode == 0
        stop_script = (release_root / "停止系统.bat").read_text(encoding="utf-8")
        assert '$targetPid = Get-Content $pidFile' in stop_script
        assert '$pid = Get-Content $pidFile' not in stop_script
    finally:
        if dist_root.exists():
            subprocess.run(["powershell", "-Command", f"Remove-Item -Recurse -Force '{dist_root}'"], check=False)
        if release_root.exists():
            subprocess.run(["powershell", "-Command", f"Remove-Item -Recurse -Force '{release_root}'"], check=False)
        if desktop_shell_root.exists():
            subprocess.run(["powershell", "-Command", f"Remove-Item -Recurse -Force '{desktop_shell_root}'"], check=False)


def test_prepare_upgrade_release_generates_status_script_with_probe_command() -> None:
    dist_root = ROOT / "tmp_test_prepare_upgrade_dist_status"
    release_root = ROOT / "tmp_test_prepare_upgrade_out_status"
    desktop_shell_root = ROOT / "tmp_test_prepare_upgrade_shell_status"
    try:
        if dist_root.exists():
            subprocess.run(["powershell", "-Command", f"Remove-Item -Recurse -Force '{dist_root}'"], check=False)
        if release_root.exists():
            subprocess.run(["powershell", "-Command", f"Remove-Item -Recurse -Force '{release_root}'"], check=False)
        if desktop_shell_root.exists():
            subprocess.run(["powershell", "-Command", f"Remove-Item -Recurse -Force '{desktop_shell_root}'"], check=False)

        (dist_root / "_internal").mkdir(parents=True, exist_ok=True)
        (desktop_shell_root / "runtime").mkdir(parents=True, exist_ok=True)
        (dist_root / "HotCollectorLauncher.exe").write_text("stub", encoding="utf-8")
        (dist_root / "_internal" / "runtime.txt").write_text("stub", encoding="utf-8")
        (desktop_shell_root / "launch-desktop-shell.bat").write_text("@echo off\r\necho desktop shell\r\n", encoding="utf-8")
        (desktop_shell_root / "runtime" / "electron.exe").write_text("stub", encoding="utf-8")

        result = run_ps1(
            PREPARE_UPGRADE,
            "-ReleaseRoot",
            str(release_root.relative_to(ROOT)),
            "-DistRoot",
            str(dist_root.relative_to(ROOT)),
            "-DesktopShellDistRoot",
            str(desktop_shell_root.relative_to(ROOT)),
        )

        assert result.returncode == 0
        status_script = (release_root / "查看状态.bat").read_text(encoding="utf-8")
        assert "HotCollectorLauncher.exe --probe --print-json" in status_script
    finally:
        if dist_root.exists():
            subprocess.run(["powershell", "-Command", f"Remove-Item -Recurse -Force '{dist_root}'"], check=False)
        if release_root.exists():
            subprocess.run(["powershell", "-Command", f"Remove-Item -Recurse -Force '{release_root}'"], check=False)
        if desktop_shell_root.exists():
            subprocess.run(["powershell", "-Command", f"Remove-Item -Recurse -Force '{desktop_shell_root}'"], check=False)


def test_build_offline_release_script_prefers_tar_archive() -> None:
    result = run_ps1(BUILD_OFFLINE, "-DryRun", "-SkipBuild")

    assert result.returncode == 0
    assert "tar.exe -a -cf" in result.stdout
    assert "Compress-Archive" not in result.stdout
    assert "build_desktop_shell.ps1" in result.stdout


def test_build_offline_release_generates_sha256_file(tmp_path) -> None:
    """TC-SEC-201"""
    dist_root = ROOT / "tmp_test_build_offline_dist" / "HotCollectorLauncher"
    release_root = ROOT / "tmp_test_build_offline_release" / "HotCollector-Offline-Test"
    playwright_root = ROOT / "tmp_test_build_offline_playwright"
    desktop_shell_root = ROOT / "tmp_test_build_offline_shell"
    vc_redist = ROOT / "tmp_test_build_offline_vcredist.exe"
    zip_path = Path(str(release_root) + ".zip")
    sha_path = Path(str(zip_path) + ".sha256")
    try:
        for path in (dist_root.parent, release_root.parent, playwright_root, desktop_shell_root):
            if path.exists():
                subprocess.run(["powershell", "-Command", f"Remove-Item -Recurse -Force '{path}'"], check=False)
        for path in (vc_redist, zip_path, sha_path):
            if path.exists():
                subprocess.run(["powershell", "-Command", f"Remove-Item -Force '{path}'"], check=False)

        dist_root.mkdir(parents=True, exist_ok=True)
        playwright_root.mkdir(parents=True, exist_ok=True)
        (desktop_shell_root / "runtime").mkdir(parents=True, exist_ok=True)
        (dist_root / "HotCollectorLauncher.exe").write_text("stub", encoding="utf-8")
        (playwright_root / "browser.txt").write_text("stub", encoding="utf-8")
        (desktop_shell_root / "launch-desktop-shell.bat").write_text("@echo off\r\necho desktop shell\r\n", encoding="utf-8")
        (desktop_shell_root / "runtime" / "electron.exe").write_text("stub", encoding="utf-8")
        vc_redist.write_text("stub", encoding="utf-8")

        result = run_ps1(
            BUILD_OFFLINE,
            "-SkipBuild",
            "-ReleaseRoot",
            str(release_root.relative_to(ROOT)),
            "-DistRoot",
            str(dist_root.relative_to(ROOT)),
            "-PlaywrightBrowsersPath",
            str(playwright_root),
            "-DesktopShellDistRoot",
            str(desktop_shell_root.relative_to(ROOT)),
            "-VcRedistPath",
            str(vc_redist),
        )

        assert result.returncode == 0, result.stderr
        assert zip_path.exists()
        assert sha_path.exists()
        sha_line = sha_path.read_text(encoding="ascii").strip()
        file_hash = subprocess.run(
            ["powershell", "-Command", f"(Get-FileHash -Algorithm SHA256 '{zip_path}').Hash.ToLower()"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        assert file_hash.returncode == 0, file_hash.stderr
        expected = f"{file_hash.stdout.strip()}  {zip_path.name}"
        assert sha_line == expected
    finally:
        for path in (dist_root.parent, release_root.parent, playwright_root, desktop_shell_root):
            if path.exists():
                subprocess.run(["powershell", "-Command", f"Remove-Item -Recurse -Force '{path}'"], check=False)
        for path in (vc_redist, zip_path, sha_path):
            if path.exists():
                subprocess.run(["powershell", "-Command", f"Remove-Item -Force '{path}'"], check=False)


def test_launcher_dry_run_prints_local_runtime_summary(tmp_path) -> None:
    result = subprocess.run(
        [
            sys.executable,
            str(LAUNCHER),
            "--dry-run",
            "--runtime-root",
            str(tmp_path),
            "--port",
            "38080",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0
    assert "http://127.0.0.1:38080/" in result.stdout
    assert "sqlite:///" in result.stdout
    assert "outputs\\reports" in result.stdout or "outputs/reports" in result.stdout
    assert "http://127.0.0.1:38080/system/desktop-manifest" in result.stdout
    assert "http://127.0.0.1:38080/system/health/extended" in result.stdout


def test_launcher_dry_run_print_json_returns_structured_summary(tmp_path) -> None:
    result = subprocess.run(
        [
            sys.executable,
            str(LAUNCHER),
            "--dry-run",
            "--print-json",
            "--runtime-root",
            str(tmp_path),
            "--port",
            "39090",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert payload["runtime_root"] == str(tmp_path)
    assert payload["entry_url"] == "http://127.0.0.1:39090/"
    assert payload["desktop_manifest_url"] == "http://127.0.0.1:39090/system/desktop-manifest"
    assert payload["health_url"] == "http://127.0.0.1:39090/system/health/extended"
    assert payload["docs_url"] == "http://127.0.0.1:39090/docs"
    assert payload["database"].startswith("sqlite:///")


def test_launcher_probe_print_json_returns_instance_status(tmp_path) -> None:
    data_dir = tmp_path / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    (data_dir / "launcher.pid").write_text("4321", encoding="utf-8")

    result = subprocess.run(
        [
            sys.executable,
            str(LAUNCHER),
            "--probe",
            "--print-json",
            "--runtime-root",
            str(tmp_path),
            "--port",
            "39090",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert payload["kind"] == "launcher-probe"
    assert payload["running"] is False
    assert payload["pid"] == 4321
    assert payload["pid_file_exists"] is True
    assert payload["stale_pid_file"] is True
    assert payload["entry_url"] == "http://127.0.0.1:39090/"


def test_desktop_manifest_consumer_print_json_resolves_probe_command(tmp_path) -> None:
    client = create_test_client(make_sqlite_url(tmp_path))
    manifest_path = tmp_path / "desktop-manifest.json"
    manifest_path.write_text(
        json.dumps(client.get("/system/desktop-manifest").json(), ensure_ascii=False),
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            sys.executable,
            str(DESKTOP_MANIFEST_CONSUMER),
            "--manifest-file",
            str(manifest_path),
            "--control",
            "probe",
            "--print-json",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["control"] == "probe"
    assert payload["launch_mode"] == "powershell-file"
    assert payload["preferred_args"] == ["-PrintJson"]
    assert payload["command"][:5] == [
        "powershell.exe",
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
    ]
    assert payload["command"][5].endswith("status.ps1")


def test_desktop_manifest_consumer_rejects_invalid_manifest_file(tmp_path) -> None:
    manifest_path = tmp_path / "invalid-manifest.json"
    manifest_path.write_text('{"kind":"desktop-shell-manifest"}', encoding="utf-8")

    result = subprocess.run(
        [
            sys.executable,
            str(DESKTOP_MANIFEST_CONSUMER),
            "--manifest-file",
            str(manifest_path),
            "--control",
            "probe",
            "--print-json",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 1
    assert "DesktopManifest" in result.stderr or "validation" in result.stderr.lower()


def test_build_spec_includes_playwright_async_api_hiddenimport() -> None:
    spec_text = (ROOT / "hot_collector.spec").read_text(encoding="utf-8")

    assert '"playwright.async_api"' in spec_text

def test_build_spec_adds_repo_venv_site_packages_to_pythonpath() -> None:
    spec_text = (ROOT / "hot_collector.spec").read_text(encoding="utf-8")

    assert '.venv' in spec_text
    assert 'site-packages' in spec_text

def test_build_spec_collects_playwright_package_data() -> None:
    spec_text = (ROOT / "hot_collector.spec").read_text(encoding="utf-8")

    assert 'collect_submodules("playwright")' in spec_text
    assert 'collect_data_files("playwright")' in spec_text

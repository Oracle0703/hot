from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
BOOTSTRAP = ROOT / "scripts" / "bootstrap.ps1"
RUN = ROOT / "scripts" / "run.ps1"
BUILD = ROOT / "scripts" / "build_package.ps1"
PREPARE = ROOT / "scripts" / "prepare_release.ps1"
PREPARE_UPGRADE = ROOT / "scripts" / "prepare_upgrade_release.ps1"
BUILD_OFFLINE = ROOT / "scripts" / "build_offline_release.ps1"
BUILD_UPGRADE = ROOT / "scripts" / "build_upgrade_release.ps1"
LAUNCHER = ROOT / "launcher.py"


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


def test_prepare_upgrade_release_script_renders_upgrade_assembly_steps() -> None:
    result = run_ps1(PREPARE_UPGRADE, "-DryRun")

    assert result.returncode == 0
    assert "release\\HotCollector-Upgrade" in result.stdout
    assert "HotCollectorLauncher.exe" in result.stdout


def test_build_upgrade_release_script_prefers_tar_archive() -> None:
    result = run_ps1(BUILD_UPGRADE, "-DryRun", "-SkipBuild")

    assert result.returncode == 0
    assert "tar.exe -a -cf" in result.stdout
    assert "prepare_upgrade_release.ps1" in result.stdout




def test_prepare_release_generates_stop_script_that_removes_pid_file() -> None:
    dist_root = ROOT / "tmp_test_prepare_release_dist"
    release_root = ROOT / "tmp_test_prepare_release_out"
    try:
        if dist_root.exists():
            subprocess.run(["powershell", "-Command", f"Remove-Item -Recurse -Force '{dist_root}'"], check=False)
        if release_root.exists():
            subprocess.run(["powershell", "-Command", f"Remove-Item -Recurse -Force '{release_root}'"], check=False)

        dist_root.mkdir(parents=True, exist_ok=True)
        (dist_root / "HotCollectorLauncher.exe").write_text("stub", encoding="utf-8")

        result = run_ps1(
            PREPARE,
            "-ReleaseRoot",
            str(release_root.relative_to(ROOT)),
            "-DistRoot",
            str(dist_root.relative_to(ROOT)),
        )

        assert result.returncode == 0
        stop_script = (release_root / "停止系统.bat").read_text(encoding="utf-8")
        assert "Remove-Item -Path $pidFile -Force" in stop_script
    finally:
        if dist_root.exists():
            subprocess.run(["powershell", "-Command", f"Remove-Item -Recurse -Force '{dist_root}'"], check=False)
        if release_root.exists():
            subprocess.run(["powershell", "-Command", f"Remove-Item -Recurse -Force '{release_root}'"], check=False)


def test_prepare_upgrade_release_generates_program_only_package() -> None:
    dist_root = ROOT / "tmp_test_prepare_upgrade_dist"
    release_root = ROOT / "tmp_test_prepare_upgrade_out"
    try:
        if dist_root.exists():
            subprocess.run(["powershell", "-Command", f"Remove-Item -Recurse -Force '{dist_root}'"], check=False)
        if release_root.exists():
            subprocess.run(["powershell", "-Command", f"Remove-Item -Recurse -Force '{release_root}'"], check=False)

        (dist_root / "_internal").mkdir(parents=True, exist_ok=True)
        (dist_root / "HotCollectorLauncher.exe").write_text("stub", encoding="utf-8")
        (dist_root / "_internal" / "runtime.txt").write_text("stub", encoding="utf-8")

        result = run_ps1(
            PREPARE_UPGRADE,
            "-ReleaseRoot",
            str(release_root.relative_to(ROOT)),
            "-DistRoot",
            str(dist_root.relative_to(ROOT)),
        )

        assert result.returncode == 0
        assert (release_root / "HotCollectorLauncher.exe").exists()
        assert (release_root / "_internal" / "runtime.txt").exists()
        assert (release_root / "启动系统.bat").exists()
        assert (release_root / "停止系统.bat").exists()
        assert (release_root / "README-运营版.txt").exists()
        assert (release_root / "data").exists() is False
        assert (release_root / "logs").exists() is False
        assert (release_root / "outputs").exists() is False
        assert (release_root / "playwright-browsers").exists() is False
    finally:
        if dist_root.exists():
            subprocess.run(["powershell", "-Command", f"Remove-Item -Recurse -Force '{dist_root}'"], check=False)
        if release_root.exists():
            subprocess.run(["powershell", "-Command", f"Remove-Item -Recurse -Force '{release_root}'"], check=False)


def test_prepare_release_generates_stop_script_without_using_reserved_pid_variable() -> None:
    dist_root = ROOT / "tmp_test_prepare_release_dist_reserved"
    release_root = ROOT / "tmp_test_prepare_release_out_reserved"
    try:
        if dist_root.exists():
            subprocess.run(["powershell", "-Command", f"Remove-Item -Recurse -Force '{dist_root}'"], check=False)
        if release_root.exists():
            subprocess.run(["powershell", "-Command", f"Remove-Item -Recurse -Force '{release_root}'"], check=False)

        dist_root.mkdir(parents=True, exist_ok=True)
        (dist_root / "HotCollectorLauncher.exe").write_text("stub", encoding="utf-8")

        result = run_ps1(
            PREPARE,
            "-ReleaseRoot",
            str(release_root.relative_to(ROOT)),
            "-DistRoot",
            str(dist_root.relative_to(ROOT)),
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
def test_build_offline_release_script_prefers_tar_archive() -> None:
    result = run_ps1(BUILD_OFFLINE, "-DryRun", "-SkipBuild")

    assert result.returncode == 0
    assert "tar.exe -a -cf" in result.stdout
    assert "Compress-Archive" not in result.stdout


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



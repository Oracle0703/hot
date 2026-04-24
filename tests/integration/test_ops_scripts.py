"""TC-SYS-201~205 / TC-SYS-301~302 / TC-API-301~302 — 运维脚本回归。

通过子进程启动 PowerShell 执行 backup_database.ps1 / restore_database.ps1 / stop.ps1,
验证 -DryRun 不修改文件、实际运行产生预期文件、参数 -Keep 控制保留份数。
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = REPO_ROOT / "scripts"

pytestmark = pytest.mark.skipif(sys.platform != "win32", reason="ops scripts are PowerShell-only")


def _run_ps(script: Path, *args: str, cwd: Path | None = None) -> subprocess.CompletedProcess:
    cmd = [
        "powershell.exe",
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        str(script),
        *args,
    ]
    return subprocess.run(cmd, capture_output=True, text=True, cwd=str(cwd or REPO_ROOT), timeout=30)


def _make_dummy_db(path: Path, content: bytes = b"hot-topics-fake") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)


# --- TC-SYS-201 / TC-API-302 ----------------------------------------------------

def test_backup_database_dry_run_outputs_target_path(tmp_path):
    """TC-SYS-201"""
    db = tmp_path / "data" / "hot_topics.db"
    _make_dummy_db(db)
    backup_dir = tmp_path / "data" / "backups"
    res = _run_ps(
        SCRIPTS_DIR / "backup_database.ps1",
        "-DatabasePath", str(db),
        "-BackupDir", str(backup_dir),
        "-DryRun",
    )
    assert res.returncode == 0, res.stderr or res.stdout
    assert "DryRun" in res.stdout
    # 目录不应被创建,文件不应被复制
    assert not backup_dir.exists()


# --- TC-SYS-202 -----------------------------------------------------------------

def test_backup_database_creates_file(tmp_path):
    """TC-SYS-202"""
    db = tmp_path / "data" / "hot_topics.db"
    _make_dummy_db(db)
    backup_dir = tmp_path / "data" / "backups"
    res = _run_ps(
        SCRIPTS_DIR / "backup_database.ps1",
        "-DatabasePath", str(db),
        "-BackupDir", str(backup_dir),
    )
    assert res.returncode == 0, res.stderr or res.stdout
    files = list(backup_dir.glob("hot_topics-*.db"))
    assert len(files) == 1


# --- TC-SYS-203 -----------------------------------------------------------------

def test_backup_database_keeps_only_n_latest(tmp_path):
    """TC-SYS-203: 多次备份 + -Keep 2 -> 最多保留 2 份。"""
    db = tmp_path / "data" / "hot_topics.db"
    _make_dummy_db(db)
    backup_dir = tmp_path / "data" / "backups"
    backup_dir.mkdir(parents=True)
    # 预置 3 份"旧"备份
    import time
    for i in range(3):
        f = backup_dir / f"hot_topics-2025010{i}-000000.db"
        f.write_bytes(b"old")
        # 设置不同 mtime
        os.utime(f, (1735689600 + i, 1735689600 + i))
    res = _run_ps(
        SCRIPTS_DIR / "backup_database.ps1",
        "-DatabasePath", str(db),
        "-BackupDir", str(backup_dir),
        "-Keep", "2",
    )
    assert res.returncode == 0, res.stderr or res.stdout
    remaining = list(backup_dir.glob("hot_topics-*.db"))
    assert len(remaining) == 2, [p.name for p in remaining]


# --- TC-SYS-204 -----------------------------------------------------------------

def test_restore_database_validates_file_exists(tmp_path):
    """TC-SYS-204"""
    res = _run_ps(
        SCRIPTS_DIR / "restore_database.ps1",
        "-File", str(tmp_path / "missing.db"),
        "-DatabasePath", str(tmp_path / "data" / "hot_topics.db"),
    )
    assert res.returncode == 1


# --- TC-SYS-205 -----------------------------------------------------------------

def test_restore_database_replaces_main_db(tmp_path):
    """TC-SYS-205"""
    project = tmp_path / "project"
    (project / "scripts").mkdir(parents=True)
    db = project / "data" / "hot_topics.db"
    _make_dummy_db(db, b"current")
    backup = project / "data" / "backups" / "hot_topics-x.db"
    _make_dummy_db(backup, b"restored-content")
    shutil.copy2(SCRIPTS_DIR / "restore_database.ps1", project / "scripts" / "restore_database.ps1")

    res = _run_ps(
        project / "scripts" / "restore_database.ps1",
        "-File", str(backup),
        "-DatabasePath", str(db),
        cwd=project,
    )
    assert res.returncode == 0, res.stderr or res.stdout
    assert db.read_bytes() == b"restored-content"
    rollbacks = list(db.parent.glob("hot_topics.db.before-restore-*"))
    assert len(rollbacks) == 1


# --- TC-SYS-301 / TC-SYS-302 ----------------------------------------------------

def test_stop_ps1_removes_pid_file(tmp_path):
    """TC-SYS-301"""
    project = tmp_path / "project"
    (project / "data").mkdir(parents=True)
    (project / "scripts").mkdir(parents=True)
    pid_file = project / "data" / "launcher.pid"
    pid_file.write_text("999999", encoding="utf-8")  # 不存在的进程号
    shutil.copy2(SCRIPTS_DIR / "stop.ps1", project / "scripts" / "stop.ps1")
    res = _run_ps(project / "scripts" / "stop.ps1", cwd=project)
    assert res.returncode == 0, res.stderr or res.stdout
    assert not pid_file.exists()


def test_stop_system_bat_invokes_ps1(tmp_path):
    """TC-SYS-302"""
    project = tmp_path / "project"
    (project / "data").mkdir(parents=True)
    (project / "scripts").mkdir(parents=True)
    pid_file = project / "data" / "launcher.pid"
    pid_file.write_text("999999", encoding="utf-8")
    shutil.copy2(SCRIPTS_DIR / "stop.ps1", project / "scripts" / "stop.ps1")
    shutil.copy2(SCRIPTS_DIR / "stop_system.bat", project / "scripts" / "stop_system.bat")

    res = subprocess.run(
        ["cmd.exe", "/c", str(project / "scripts" / "stop_system.bat")],
        capture_output=True, text=True, cwd=str(project), timeout=30,
    )
    assert res.returncode == 0, res.stderr or res.stdout
    assert not pid_file.exists()


# --- TC-API-301 -----------------------------------------------------------------

def test_stop_ps1_dry_run(tmp_path):
    """TC-API-301: -DryRun 不删除 PID 文件,只打印 DryRun 行。"""
    project = tmp_path / "project"
    (project / "data").mkdir(parents=True)
    (project / "scripts").mkdir(parents=True)
    pid_file = project / "data" / "launcher.pid"
    # 用当前 python 进程的 PID 模拟一个"在跑的进程"
    pid_file.write_text(str(os.getpid()), encoding="utf-8")
    shutil.copy2(SCRIPTS_DIR / "stop.ps1", project / "scripts" / "stop.ps1")

    res = _run_ps(project / "scripts" / "stop.ps1", "-DryRun", cwd=project)
    assert res.returncode == 0, res.stderr or res.stdout
    assert "DryRun" in res.stdout
    assert pid_file.exists(), "DryRun 不应删除 PID 文件"


# --- TC-API-302 -----------------------------------------------------------------

def test_backup_restore_dry_run(tmp_path):
    """TC-API-302: backup 与 restore 的 -DryRun 都不修改文件。"""
    project = tmp_path / "project"
    (project / "scripts").mkdir(parents=True)
    db = project / "data" / "hot_topics.db"
    _make_dummy_db(db, b"orig")
    backup_dir = project / "data" / "backups"
    src_backup = tmp_path / "src.db"
    src_backup.write_bytes(b"replacement")
    shutil.copy2(SCRIPTS_DIR / "backup_database.ps1", project / "scripts" / "backup_database.ps1")
    shutil.copy2(SCRIPTS_DIR / "restore_database.ps1", project / "scripts" / "restore_database.ps1")

    res1 = _run_ps(
        project / "scripts" / "backup_database.ps1",
        "-DatabasePath", str(db),
        "-BackupDir", str(backup_dir),
        "-DryRun",
        cwd=project,
    )
    assert res1.returncode == 0
    assert not backup_dir.exists()

    res2 = _run_ps(
        project / "scripts" / "restore_database.ps1",
        "-File", str(src_backup),
        "-DatabasePath", str(db),
        "-DryRun",
        cwd=project,
    )
    assert res2.returncode == 0
    assert db.read_bytes() == b"orig"

from __future__ import annotations

import json
import os
import sys
import tempfile
import time
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator


@dataclass(slots=True)
class GuiJobWorkspace:
    job_id: str
    root: Path
    input_dir: Path
    run_dir: Path
    output_dir: Path
    artifacts_dir: Path
    lock_path: Path


def _resolve_global_gui_lock_path() -> Path:
    configured_root = os.environ.get("EDA2KICAD_GUI_LOCK_DIR")
    if configured_root:
        root = Path(configured_root)
    else:
        root = Path(tempfile.gettempdir()) / "eda2kicad-gui-locks"
    root.mkdir(parents=True, exist_ok=True)
    return root / "desktop-session.lock"


def assert_gui_environment_ready(kicad_exe: Path | None = None) -> None:
    if not sys.platform.startswith("win"):
        raise ValueError("GUI automation requires Windows")
    if kicad_exe is not None and not isinstance(kicad_exe, Path):
        kicad_exe = Path(kicad_exe)
    # The real executable check is intentionally deferred to the driver layer so
    # tests and mock-driven runs do not require KiCad to be installed.


def create_job_workspace(output_root: Path, job_id: str) -> GuiJobWorkspace:
    job_root = output_root / "gui-jobs" / job_id
    input_dir = job_root / "input"
    run_dir = job_root / "run"
    output_dir = job_root / "output"
    artifacts_dir = job_root / "artifacts"
    lock_path = job_root / "job.lock"

    for directory in (input_dir, run_dir, output_dir, artifacts_dir):
        directory.mkdir(parents=True, exist_ok=True)

    return GuiJobWorkspace(
        job_id=job_id,
        root=job_root,
        input_dir=input_dir,
        run_dir=run_dir,
        output_dir=output_dir,
        artifacts_dir=artifacts_dir,
        lock_path=lock_path,
    )


@contextmanager
def acquire_gui_job_lock(
    workspace: GuiJobWorkspace,
    *,
    stale_timeout_seconds: float = 600.0,
    wait_timeout_seconds: float = 900.0,
    poll_interval_seconds: float = 0.5,
) -> Iterator[Path]:
    workspace.root.mkdir(parents=True, exist_ok=True)
    global_lock_path = _resolve_global_gui_lock_path()
    payload = {
        "pid": os.getpid(),
        "job_id": workspace.job_id,
        "created_at": time.time(),
    }
    _acquire_lock_file(
        global_lock_path,
        payload,
        stale_timeout_seconds=stale_timeout_seconds,
        wait_timeout_seconds=wait_timeout_seconds,
        poll_interval_seconds=poll_interval_seconds,
        timeout_error_message="global gui session lock is busy",
    )
    _acquire_lock_file(
        workspace.lock_path,
        payload,
        stale_timeout_seconds=stale_timeout_seconds,
        wait_timeout_seconds=wait_timeout_seconds,
        poll_interval_seconds=poll_interval_seconds,
        timeout_error_message="job lock is busy",
    )
    try:
        yield workspace.lock_path
    finally:
        try:
            workspace.lock_path.unlink()
        except (FileNotFoundError, PermissionError):
            pass
        try:
            global_lock_path.unlink()
        except (FileNotFoundError, PermissionError):
            pass


def _acquire_lock_file(
    lock_path: Path,
    payload: dict[str, object],
    *,
    stale_timeout_seconds: float,
    wait_timeout_seconds: float,
    poll_interval_seconds: float,
    timeout_error_message: str,
) -> None:
    deadline = time.monotonic() + wait_timeout_seconds
    while True:
        _reclaim_stale_gui_job_lock(lock_path, stale_timeout_seconds=stale_timeout_seconds)
        try:
            with lock_path.open("x", encoding="utf-8") as handle:
                json.dump(payload, handle, indent=2)
            return
        except FileExistsError:
            if time.monotonic() >= deadline:
                raise TimeoutError(timeout_error_message)
            time.sleep(poll_interval_seconds)


def _reclaim_stale_gui_job_lock(lock_path: Path, *, stale_timeout_seconds: float) -> None:
    if not lock_path.exists():
        return
    payload = _read_gui_job_lock_payload(lock_path)
    pid = payload.get("pid")
    created_at = payload.get("created_at")
    age_seconds = None
    if isinstance(created_at, (int, float)):
        age_seconds = max(0.0, time.time() - float(created_at))

    should_reclaim = False
    if isinstance(pid, int) and not _pid_is_running(pid):
        should_reclaim = True
    if age_seconds is not None and age_seconds >= stale_timeout_seconds:
        should_reclaim = True

    if should_reclaim:
        try:
            lock_path.unlink()
        except FileNotFoundError:
            return


def _read_gui_job_lock_payload(lock_path: Path) -> dict[str, object]:
    try:
        return json.loads(lock_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def _pid_is_running(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        if sys.platform.startswith("win"):
            import ctypes

            process = ctypes.windll.kernel32.OpenProcess(0x1000, False, pid)
            if not process:
                return False
            ctypes.windll.kernel32.CloseHandle(process)
            return True
        os.kill(pid, 0)
        return True
    except Exception:
        return False

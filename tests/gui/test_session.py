from pathlib import Path

import pytest

from eda2kicad.gui import session as session_module
from eda2kicad.gui.session import acquire_gui_job_lock, assert_gui_environment_ready, create_job_workspace


def test_create_job_workspace_builds_expected_directories(tmp_path: Path) -> None:
    workspace = create_job_workspace(tmp_path, "job-001")

    assert workspace.job_id == "job-001"
    assert workspace.root == tmp_path / "gui-jobs" / "job-001"
    assert workspace.input_dir == workspace.root / "input"
    assert workspace.run_dir == workspace.root / "run"
    assert workspace.output_dir == workspace.root / "output"
    assert workspace.artifacts_dir == workspace.root / "artifacts"
    assert workspace.input_dir.is_dir()
    assert workspace.run_dir.is_dir()
    assert workspace.output_dir.is_dir()
    assert workspace.artifacts_dir.is_dir()


def test_assert_gui_environment_ready_rejects_non_windows(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("eda2kicad.gui.session.sys.platform", "linux")

    with pytest.raises(ValueError, match="Windows"):
        assert_gui_environment_ready()


def test_acquire_gui_job_lock_creates_and_cleans_up_lock_file(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    global_lock_root = tmp_path / "global-locks"
    monkeypatch.setenv("EDA2KICAD_GUI_LOCK_DIR", str(global_lock_root))
    workspace = create_job_workspace(tmp_path, "job-002")
    global_lock_path = global_lock_root / "desktop-session.lock"

    with acquire_gui_job_lock(workspace) as lock_path:
        assert lock_path.exists()
        assert workspace.lock_path.exists()
        assert global_lock_path.exists()

    assert not workspace.lock_path.exists()
    assert not global_lock_path.exists()


def test_acquire_gui_job_lock_reclaims_stale_lock_when_process_is_gone(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("EDA2KICAD_GUI_LOCK_DIR", str(tmp_path / "global-locks"))
    workspace = create_job_workspace(tmp_path, "job-003")
    workspace.lock_path.write_text(
        '{\n  "pid": 999999,\n  "job_id": "old-job",\n  "created_at": 100.0\n}\n',
        encoding="utf-8",
    )

    monkeypatch.setattr(session_module.time, "time", lambda: 120.0)
    monkeypatch.setattr(session_module, "_pid_is_running", lambda _pid: False)

    with acquire_gui_job_lock(workspace, stale_timeout_seconds=300) as lock_path:
        assert lock_path.exists()
        payload = lock_path.read_text(encoding="utf-8")
        assert '"job_id": "job-003"' in payload

    assert not workspace.lock_path.exists()


def test_acquire_gui_job_lock_reclaims_expired_lock_even_if_process_still_exists(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("EDA2KICAD_GUI_LOCK_DIR", str(tmp_path / "global-locks"))
    workspace = create_job_workspace(tmp_path, "job-004")
    workspace.lock_path.write_text(
        '{\n  "pid": 12345,\n  "job_id": "old-job",\n  "created_at": 100.0\n}\n',
        encoding="utf-8",
    )

    monkeypatch.setattr(session_module.time, "time", lambda: 1000.0)
    monkeypatch.setattr(session_module, "_pid_is_running", lambda _pid: True)

    with acquire_gui_job_lock(workspace, stale_timeout_seconds=300) as lock_path:
        assert lock_path.exists()
        payload = lock_path.read_text(encoding="utf-8")
        assert '"job_id": "job-004"' in payload

    assert not workspace.lock_path.exists()


def test_acquire_gui_job_lock_serializes_across_jobs_with_global_lock(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("EDA2KICAD_GUI_LOCK_DIR", str(tmp_path / "global-locks"))
    workspace_a = create_job_workspace(tmp_path, "job-a")
    workspace_b = create_job_workspace(tmp_path, "job-b")

    with acquire_gui_job_lock(workspace_a):
        with pytest.raises(TimeoutError, match="global gui session lock is busy"):
            with acquire_gui_job_lock(
                workspace_b,
                wait_timeout_seconds=0.0,
                poll_interval_seconds=0.0,
            ):
                pass

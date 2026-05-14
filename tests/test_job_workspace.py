from datetime import datetime
from pathlib import Path

from eda2kicad.jobs.models import JobWorkspace
from eda2kicad.jobs.workspace import create_job_workspace


def test_create_job_workspace_creates_timestamped_job_directories(
    tmp_path: Path,
    monkeypatch,
) -> None:
    from eda2kicad.jobs import workspace as workspace_module

    class FrozenDatetime(datetime):
        @classmethod
        def now(cls, tz=None) -> "FrozenDatetime":
            del tz
            return cls(2026, 5, 13, 14, 15, 16)

    monkeypatch.setattr(workspace_module, "datetime", FrozenDatetime)

    workspace = create_job_workspace(tmp_path, "demo_input")

    expected_root = tmp_path / "20260513_141516_demo_input"
    assert workspace == JobWorkspace(
        root=expected_root,
        final_dir=expected_root,
        temp_dir=expected_root / "temp",
        input_dir=expected_root / "input",
    )
    assert workspace.root.exists()
    assert workspace.final_dir == workspace.root
    assert workspace.temp_dir.is_dir()
    assert workspace.input_dir.is_dir()


def test_create_job_workspace_appends_suffix_when_timestamped_directory_exists(
    tmp_path: Path,
    monkeypatch,
) -> None:
    from eda2kicad.jobs import workspace as workspace_module

    class FrozenDatetime(datetime):
        @classmethod
        def now(cls, tz=None) -> "FrozenDatetime":
            del tz
            return cls(2026, 5, 13, 14, 15, 16)

    monkeypatch.setattr(workspace_module, "datetime", FrozenDatetime)

    first = create_job_workspace(tmp_path, "demo_input")
    second = create_job_workspace(tmp_path, "demo_input")

    assert first.root == tmp_path / "20260513_141516_demo_input"
    assert second.root == tmp_path / "20260513_141516_demo_input_01"
    assert second.temp_dir.is_dir()
    assert second.input_dir.is_dir()


def test_create_job_workspace_normalizes_input_label_for_filesystem_safety(
    tmp_path: Path,
    monkeypatch,
) -> None:
    from eda2kicad.jobs import workspace as workspace_module

    class FrozenDatetime(datetime):
        @classmethod
        def now(cls, tz=None) -> "FrozenDatetime":
            del tz
            return cls(2026, 5, 13, 14, 15, 16)

    monkeypatch.setattr(workspace_module, "datetime", FrozenDatetime)

    workspace = create_job_workspace(tmp_path, '  a/b\\c:d*e?f"g<h>i|j  ')

    assert workspace.root == tmp_path / "20260513_141516_a_b_c_d_e_f_g_h_i_j"
    assert workspace.temp_dir.is_dir()
    assert workspace.input_dir.is_dir()

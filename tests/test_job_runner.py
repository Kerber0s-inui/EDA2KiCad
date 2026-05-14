from pathlib import Path
from unittest.mock import patch

from eda2kicad.jobs.runner import cleanup_intermediate_artifacts
from eda2kicad.jobs.reporting import collect_final_outputs


def _write_file(path: Path, content: str = "placeholder") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def test_collect_final_outputs_returns_only_delivery_artifacts(tmp_path: Path) -> None:
    board = _write_file(tmp_path / "demo.kicad_pcb")
    schematic = _write_file(tmp_path / "demo.kicad_sch")
    project = _write_file(tmp_path / "demo.kicad_pro")
    _write_file(tmp_path / "notes.txt")
    _write_file(tmp_path / "demo-cache.lib")
    _write_file(tmp_path / "subdir" / "ignored.net")

    outputs = collect_final_outputs(tmp_path)

    assert outputs == {
        "board": board,
        "schematic": schematic,
        "project": project,
    }


def test_collect_final_outputs_deletes_cache_library_artifacts(tmp_path: Path) -> None:
    cache_lib = _write_file(tmp_path / "demo-cache.lib")
    _write_file(tmp_path / "demo.kicad_sch")

    outputs = collect_final_outputs(tmp_path)

    assert outputs == {"schematic": tmp_path / "demo.kicad_sch"}
    assert not cache_lib.exists()


def test_cleanup_intermediate_artifacts_removes_cache_libs_and_requested_paths(
    tmp_path: Path,
) -> None:
    cache_lib = _write_file(tmp_path / "demo-cache.lib")
    temp_dir = tmp_path / "temp"
    _write_file(temp_dir / "nested" / "artifact.tmp")
    keep_file = _write_file(tmp_path / "demo.kicad_pcb")

    cleanup_intermediate_artifacts(tmp_path, extra_paths=[temp_dir])

    assert not cache_lib.exists()
    assert not temp_dir.exists()
    assert keep_file.exists()


def test_cleanup_intermediate_artifacts_collects_permission_warnings(tmp_path: Path) -> None:
    blocked_dir = tmp_path / "blocked"
    blocked_dir.mkdir()

    with patch("eda2kicad.jobs.runner._remove_path", side_effect=PermissionError("blocked")):
        warnings = cleanup_intermediate_artifacts(tmp_path, extra_paths=[blocked_dir])

    assert len(warnings) == 3
    assert all("blocked" in warning for warning in warnings)
    assert any(str(tmp_path / "input") in warning for warning in warnings)
    assert any(str(tmp_path / "temp") in warning for warning in warnings)
    assert any(str(blocked_dir) in warning for warning in warnings)

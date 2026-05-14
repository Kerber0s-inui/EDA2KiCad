from pathlib import Path

import pytest

from eda2kicad.strategies import kicad_gui_official
from eda2kicad.strategies.kicad_gui_official import _resolve_gui_import_input


def test_resolve_gui_import_input_accepts_direct_prjpcb(tmp_path: Path) -> None:
    project_file = tmp_path / "demo.PrjPcb"
    project_file.write_text("project", encoding="utf-8")

    resolved = _resolve_gui_import_input(project_file)

    assert resolved == project_file


def test_resolve_gui_import_input_uses_unique_sibling_project_for_pcbdoc(tmp_path: Path) -> None:
    board_file = tmp_path / "demo.PcbDoc"
    project_file = tmp_path / "demo.PrjPCB"
    board_file.write_text("board", encoding="utf-8")
    project_file.write_text("project", encoding="utf-8")

    resolved = _resolve_gui_import_input(board_file)

    assert resolved == project_file


def test_resolve_gui_import_input_rejects_ambiguous_sibling_projects(tmp_path: Path) -> None:
    board_file = tmp_path / "demo.PcbDoc"
    board_file.write_text("board", encoding="utf-8")
    (tmp_path / "a.PrjPcb").write_text("project-a", encoding="utf-8")
    (tmp_path / "b.PrjPcb").write_text("project-b", encoding="utf-8")

    with pytest.raises(ValueError, match=".PrjPcb"):
        _resolve_gui_import_input(board_file)


def test_resolve_gui_import_input_uses_unique_sibling_project_for_schdoc(tmp_path: Path) -> None:
    schematic_file = tmp_path / "demo.SchDoc"
    project_file = tmp_path / "demo.PrjPcb"
    schematic_file.write_text("schematic", encoding="utf-8")
    project_file.write_text("project", encoding="utf-8")

    resolved = _resolve_gui_import_input(schematic_file)

    assert resolved == project_file


def test_convert_routes_schdoc_to_native_schematic(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    schematic_file = tmp_path / "demo.SchDoc"
    schematic_file.write_text("schematic", encoding="utf-8")

    def fake_convert_native_schematic(
        _input_path: Path,
        *,
        output_root: Path | None = None,
    ) -> dict[str, object]:
        del _input_path
        del output_root
        return {
            "project_name": "demo",
            "schematic_text": "(kicad_sch (version 20231120))\n",
            "schematic_extension": ".kicad_sch",
            "board_text": None,
            "board_extension": None,
            "auxiliary_text_artifacts": {},
            "report": {"strategy": kicad_gui_official.get_strategy_metadata()},
        }

    monkeypatch.setattr(kicad_gui_official, "convert_native_schematic", fake_convert_native_schematic)

    result = kicad_gui_official.convert(schematic_file, tmp_path / "mapping.json")

    assert result["schematic_extension"] == ".kicad_sch"
    assert result["board_text"] is None


def test_convert_native_pcb_passes_pcbdoc_directly_to_gui_import(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    board_file = tmp_path / "demo.PcbDoc"
    board_file.write_text("board", encoding="utf-8")
    output_board = tmp_path / "demo.kicad_pcb"
    output_board.write_text("(kicad_pcb (version 20211014))", encoding="utf-8")
    seen: dict[str, Path] = {}

    monkeypatch.setattr(kicad_gui_official, "KICAD_GUI_PATH", tmp_path / "kicad.exe")
    (tmp_path / "kicad.exe").write_text("", encoding="utf-8")

    def fake_run_pcb_gui_import(input_path: Path, output_root: Path, *, kicad_exe: Path) -> dict[str, object]:
        seen["input_path"] = input_path
        seen["output_root"] = output_root
        seen["kicad_exe"] = kicad_exe
        return {
            "project_name": "demo",
            "board_path": output_board,
            "project_path": None,
            "report": {"automation": {"phase": "complete"}},
        }

    monkeypatch.setattr(kicad_gui_official, "run_pcb_gui_import", fake_run_pcb_gui_import)

    result = kicad_gui_official.convert_native_pcb(board_file)

    assert seen["input_path"] == board_file
    assert result["board_extension"] == ".kicad_pcb"


def test_convert_native_pcb_places_gui_job_under_requested_output_dir(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    board_file = tmp_path / "demo.PcbDoc"
    board_file.write_text("board", encoding="utf-8")
    output_board = tmp_path / "demo.kicad_pcb"
    output_board.write_text("(kicad_pcb (version 20211014))", encoding="utf-8")
    requested_output_dir = tmp_path / "user-output"
    seen: dict[str, Path] = {}

    monkeypatch.setattr(kicad_gui_official, "KICAD_GUI_PATH", tmp_path / "kicad.exe")
    (tmp_path / "kicad.exe").write_text("", encoding="utf-8")

    def fake_run_pcb_gui_import(input_path: Path, output_root: Path, *, kicad_exe: Path) -> dict[str, object]:
        seen["input_path"] = input_path
        seen["output_root"] = output_root
        seen["kicad_exe"] = kicad_exe
        return {
            "project_name": "demo",
            "board_path": output_board,
            "project_path": None,
            "report": {"automation": {"phase": "complete"}},
        }

    monkeypatch.setattr(kicad_gui_official, "run_pcb_gui_import", fake_run_pcb_gui_import)

    kicad_gui_official.convert_native_pcb(board_file, output_root=requested_output_dir)

    assert seen["input_path"] == board_file
    assert seen["output_root"] == requested_output_dir / ".eda2kicad" / "kicad-gui-official"


def test_convert_native_schematic_passes_schdoc_directly_to_gui_import(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    schematic_file = tmp_path / "demo.SchDoc"
    schematic_file.write_text("schematic", encoding="utf-8")
    output_schematic = tmp_path / "demo.kicad_sch"
    output_schematic.write_text("(kicad_sch (version 20231120))", encoding="utf-8")
    seen: dict[str, Path] = {}

    monkeypatch.setattr(kicad_gui_official, "KICAD_GUI_PATH", tmp_path / "kicad.exe")
    (tmp_path / "kicad.exe").write_text("", encoding="utf-8")

    def fake_run_schematic_gui_import(input_path: Path, output_root: Path, *, kicad_exe: Path) -> dict[str, object]:
        seen["input_path"] = input_path
        seen["output_root"] = output_root
        seen["kicad_exe"] = kicad_exe
        return {
            "project_name": "demo",
            "schematic_path": output_schematic,
            "project_path": None,
            "report": {"automation": {"phase": "complete"}},
        }

    monkeypatch.setattr(kicad_gui_official, "run_schematic_gui_import", fake_run_schematic_gui_import)

    result = kicad_gui_official.convert_native_schematic(schematic_file)

    assert seen["input_path"] == schematic_file
    assert result["schematic_extension"] == ".kicad_sch"


def test_convert_native_schematic_places_gui_job_under_requested_output_dir(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    schematic_file = tmp_path / "demo.SchDoc"
    schematic_file.write_text("schematic", encoding="utf-8")
    output_schematic = tmp_path / "demo.kicad_sch"
    output_schematic.write_text("(kicad_sch (version 20231120))", encoding="utf-8")
    requested_output_dir = tmp_path / "user-output"
    seen: dict[str, Path] = {}

    monkeypatch.setattr(kicad_gui_official, "KICAD_GUI_PATH", tmp_path / "kicad.exe")
    (tmp_path / "kicad.exe").write_text("", encoding="utf-8")

    def fake_run_schematic_gui_import(input_path: Path, output_root: Path, *, kicad_exe: Path) -> dict[str, object]:
        seen["input_path"] = input_path
        seen["output_root"] = output_root
        seen["kicad_exe"] = kicad_exe
        return {
            "project_name": "demo",
            "schematic_path": output_schematic,
            "project_path": None,
            "report": {"automation": {"phase": "complete"}},
        }

    monkeypatch.setattr(kicad_gui_official, "run_schematic_gui_import", fake_run_schematic_gui_import)

    kicad_gui_official.convert_native_schematic(schematic_file, output_root=requested_output_dir)

    assert seen["input_path"] == schematic_file
    assert seen["output_root"] == requested_output_dir / ".eda2kicad" / "kicad-gui-official"


def test_convert_native_bundle_routes_inputs_to_combined_gui_import(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    board_file = tmp_path / "demo.PcbDoc"
    schematic_file = tmp_path / "demo.SchDoc"
    project_file = tmp_path / "demo.PrjPcb"
    board_file.write_text("board", encoding="utf-8")
    schematic_file.write_text("schematic", encoding="utf-8")
    project_file.write_text("project", encoding="utf-8")
    requested_output_dir = tmp_path / "user-output"
    seen: dict[str, Path | None] = {}

    monkeypatch.setattr(kicad_gui_official, "KICAD_GUI_PATH", tmp_path / "kicad.exe")
    (tmp_path / "kicad.exe").write_text("", encoding="utf-8")

    def fake_run_combined_gui_import(
        *,
        pcb_input: Path | None,
        schematic_input: Path | None,
        project_input: Path | None = None,
        output_root: Path,
        kicad_exe: Path,
    ) -> dict[str, object]:
        seen["pcb_input"] = pcb_input
        seen["schematic_input"] = schematic_input
        seen["project_input"] = project_input
        seen["output_root"] = output_root
        seen["kicad_exe"] = kicad_exe
        project_path = tmp_path / "demo.kicad_pro"
        board_path = tmp_path / "demo.kicad_pcb"
        schematic_path = tmp_path / "demo.kicad_sch"
        project_path.write_text("{\n  \"meta\": {\"version\": 1}\n}\n", encoding="utf-8")
        board_path.write_text("(kicad_pcb (version 20231120))\n", encoding="utf-8")
        schematic_path.write_text("(kicad_sch (version 20231120))\n", encoding="utf-8")
        return {
            "project_name": "demo",
            "project_path": project_path,
            "board_path": board_path,
            "schematic_path": schematic_path,
            "report": {"automation": {"phase": "complete"}},
        }

    monkeypatch.setattr(kicad_gui_official, "run_combined_gui_import", fake_run_combined_gui_import)

    result = kicad_gui_official.convert_native_bundle(
        pcb_input=board_file,
        schematic_input=schematic_file,
        project_input=project_file,
        output_root=requested_output_dir,
    )

    assert seen["pcb_input"] == board_file
    assert seen["schematic_input"] == schematic_file
    assert seen["project_input"] == project_file
    assert seen["output_root"] == requested_output_dir / ".eda2kicad" / "kicad-gui-official"
    assert result["board_extension"] == ".kicad_pcb"
    assert result["schematic_extension"] == ".kicad_sch"
    assert "demo.kicad_pro" in result["auxiliary_text_artifacts"]

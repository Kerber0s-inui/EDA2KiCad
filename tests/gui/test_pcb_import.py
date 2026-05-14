from pathlib import Path

import pytest

from eda2kicad.gui import pcb_import as pcb_import_module
from eda2kicad.gui.pcb_import import _stage_input_file, run_pcb_gui_import
from eda2kicad.gui.session import create_job_workspace


class FakeDriver:
    def __init__(self, *, output_name: str = "demo_board.kicad_pcb", board_text: str = "(kicad_pcb (version 20211014))") -> None:
        self.output_name = output_name
        self.board_text = board_text
        self.calls: list[tuple[str, tuple, dict]] = []

    def launch_kicad(self, kicad_exe, project_path=None):
        self.calls.append(("launch_kicad", (kicad_exe, project_path), {}))

    def wait_main_window(self, timeout_seconds: int):
        self.calls.append(("wait_main_window", (timeout_seconds,), {}))

    def open_pcb_import(self, input_path: Path):
        self.calls.append(("open_pcb_import", (input_path,), {}))

    def open_pcb_editor(self):
        self.calls.append(("open_pcb_editor", (), {}))

    def confirm_editor_creation(self):
        self.calls.append(("confirm_editor_creation", (), {}))

    def open_pcb_editor_import(self):
        self.calls.append(("open_pcb_editor_import", (), {}))

    def select_input_file(self, input_path: Path):
        self.calls.append(("select_input_file", (input_path,), {}))

    def confirm_import(self, output_path: Path):
        self.calls.append(("confirm_import", (output_path,), {}))

    def wait_import_complete(self, timeout_seconds: int):
        self.calls.append(("wait_import_complete", (timeout_seconds,), {}))

    def validate_post_import_editor_state(self):
        self.calls.append(("validate_post_import_editor_state", (), {}))

    def save_output(self, output_path: Path):
        self.calls.append(("save_output", (output_path,), {}))
        output_path.write_text(self.board_text, encoding="utf-8")

    def close_kicad(self):
        self.calls.append(("close_kicad", (), {}))


def test_run_pcb_gui_import_happy_path(tmp_path: Path) -> None:
    input_path = tmp_path / "input" / "demo.PrjPcb"
    input_path.parent.mkdir(parents=True, exist_ok=True)
    input_path.write_text("mock project", encoding="utf-8")
    output_root = tmp_path / "output"
    driver = FakeDriver()

    result = run_pcb_gui_import(
        input_path,
        output_root,
        kicad_exe=Path("C:/KiCad/kicad.exe"),
        timeout_seconds=12,
        driver_factory=lambda *_args, **_kwargs: driver,
        job_id="job-42",
    )

    assert [call[0] for call in driver.calls] == [
        "launch_kicad",
        "wait_main_window",
        "open_pcb_import",
        "select_input_file",
        "confirm_import",
        "wait_import_complete",
        "validate_post_import_editor_state",
        "save_output",
        "close_kicad",
    ]
    assert result["project_name"] == "demo"
    assert result["board_path"].read_text(encoding="utf-8").startswith("(kicad_pcb")
    assert result["project_path"] is not None
    assert result["report"]["automation"]["phase"] == "complete"
    assert result["artifacts_dir"].is_dir()
    assert result["run_dir"].is_dir()


def test_run_pcb_gui_import_uses_empty_project_flow_for_pcbdoc(tmp_path: Path) -> None:
    input_path = tmp_path / "input" / "demo.PcbDoc"
    input_path.parent.mkdir(parents=True, exist_ok=True)
    input_path.write_text("mock pcb", encoding="utf-8")
    output_root = tmp_path / "output"
    driver = FakeDriver()

    result = run_pcb_gui_import(
        input_path,
        output_root,
        kicad_exe=Path("C:/KiCad/kicad.exe"),
        timeout_seconds=12,
        driver_factory=lambda *_args, **_kwargs: driver,
        job_id="job-42",
    )

    assert [call[0] for call in driver.calls] == [
        "launch_kicad",
        "wait_main_window",
        "open_pcb_editor",
        "confirm_editor_creation",
        "open_pcb_editor_import",
        "select_input_file",
        "confirm_import",
        "wait_import_complete",
        "validate_post_import_editor_state",
        "save_output",
        "close_kicad",
    ]
    assert driver.calls[0][1][1] == result["project_path"]
    assert result["project_name"] == "demo"
    assert result["board_path"].read_text(encoding="utf-8").startswith("(kicad_pcb")
    assert result["project_path"] is not None
    assert result["report"]["automation"]["phase"] == "complete"
    assert result["artifacts_dir"].is_dir()
    assert result["run_dir"].is_dir()
    assert result["report"]["automation"]["debug"]["source_input"] == str(input_path)
    assert result["report"]["automation"]["debug"]["staged_input"].endswith("demo.PcbDoc")
    assert result["report"]["automation"]["debug"]["workflow_mode"] == "pcb-standalone"
    assert result["report"]["automation"]["debug"]["requested_board_output"] == str(result["board_path"])


def test_run_pcb_gui_import_uses_90_second_timeout_by_default(tmp_path: Path) -> None:
    input_path = tmp_path / "input" / "demo.PcbDoc"
    input_path.parent.mkdir(parents=True, exist_ok=True)
    input_path.write_text("mock pcb", encoding="utf-8")
    output_root = tmp_path / "output"
    driver = FakeDriver()

    run_pcb_gui_import(
        input_path,
        output_root,
        kicad_exe=Path("C:/KiCad/kicad.exe"),
        driver_factory=lambda *_args, **_kwargs: driver,
        job_id="job-42-default-timeout",
    )

    assert ("wait_main_window", (90,), {}) in driver.calls
    assert ("wait_import_complete", (90,), {}) in driver.calls


def test_run_pcb_gui_import_records_detected_saved_board(tmp_path: Path) -> None:
    input_path = tmp_path / "input" / "demo.PcbDoc"
    input_path.parent.mkdir(parents=True, exist_ok=True)
    input_path.write_text("mock pcb", encoding="utf-8")
    output_root = tmp_path / "output"

    class SavingDriver(FakeDriver):
        def save_output(self, output_path: Path):
            super().save_output(output_path)
            detected_path = output_path.parent / "detected_board.kicad_pcb"
            detected_path.write_text(self.board_text, encoding="utf-8")

    driver = SavingDriver()

    result = run_pcb_gui_import(
        input_path,
        output_root,
        kicad_exe=Path("C:/KiCad/kicad.exe"),
        timeout_seconds=12,
        driver_factory=lambda *_args, **_kwargs: driver,
        job_id="job-42",
    )

    assert result["report"]["automation"]["debug"]["final_board_path"] == str(result["board_path"])


def test_run_pcb_gui_import_rejects_invalid_output(tmp_path: Path) -> None:
    input_path = tmp_path / "input" / "demo.PcbDoc"
    input_path.parent.mkdir(parents=True, exist_ok=True)
    input_path.write_text("mock pcb", encoding="utf-8")
    output_root = tmp_path / "output"
    driver = FakeDriver(board_text="not a kicad file")

    with pytest.raises(ValueError, match="save_output"):
        run_pcb_gui_import(
            input_path,
            output_root,
            driver_factory=lambda *_args, **_kwargs: driver,
            job_id="job-43",
        )


def test_run_pcb_gui_import_rejects_empty_kicad_pcb_skeleton_output(tmp_path: Path) -> None:
    input_path = tmp_path / "input" / "demo.PcbDoc"
    input_path.parent.mkdir(parents=True, exist_ok=True)
    input_path.write_text("mock pcb", encoding="utf-8")
    output_root = tmp_path / "output"
    driver = FakeDriver(
        board_text=(
            "(kicad_pcb\n"
            "\t(version 20260206)\n"
            '\t(generator "pcbnew")\n'
            '\t(generator_version "10.0")\n'
            "\t(general\n"
            "\t\t(thickness 1.6)\n"
            "\t\t(legacy_teardrops no)\n"
            "\t)\n"
            '\t(paper "A4")\n'
            "\t(layers\n"
            '\t\t(0 "F.Cu" signal)\n'
            '\t\t(2 "B.Cu" signal)\n'
            '\t\t(25 "Edge.Cuts" user)\n'
            "\t)\n"
            "\t(setup\n"
            "\t\t(pad_to_mask_clearance 0)\n"
            "\t)\n"
            "\t(embedded_fonts no)\n"
            ")\n"
        )
    )

    with pytest.raises(ValueError, match="appears empty after import"):
        run_pcb_gui_import(
            input_path,
            output_root,
            driver_factory=lambda *_args, **_kwargs: driver,
            job_id="job-43-empty",
        )


def test_run_pcb_gui_import_retries_empty_standalone_save_once_before_succeeding(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FlakySaveDriver(FakeDriver):
        def __init__(self) -> None:
            super().__init__()
            self._texts = [
                (
                    "(kicad_pcb\n"
                    "\t(version 20260206)\n"
                    '\t(generator "pcbnew")\n'
                    '\t(generator_version "10.0")\n'
                    "\t(general\n"
                    "\t\t(thickness 1.6)\n"
                    "\t\t(legacy_teardrops no)\n"
                    "\t)\n"
                    '\t(paper "A4")\n'
                    "\t(layers\n"
                    '\t\t(0 "F.Cu" signal)\n'
                    '\t\t(2 "B.Cu" signal)\n'
                    '\t\t(25 "Edge.Cuts" user)\n'
                    "\t)\n"
                    "\t(setup\n"
                    "\t\t(pad_to_mask_clearance 0)\n"
                    "\t)\n"
                    "\t(embedded_fonts no)\n"
                    ")\n"
                ),
                (
                    "(kicad_pcb\n"
                    "\t(version 20260206)\n"
                    '\t(generator "pcbnew")\n'
                    '\t(generator_version "10.0")\n'
                    "\t(general\n"
                    "\t\t(thickness 1.6)\n"
                    "\t\t(legacy_teardrops no)\n"
                    "\t)\n"
                    '\t(paper "A4")\n'
                    "\t(layers\n"
                    '\t\t(0 "F.Cu" signal)\n'
                    '\t\t(2 "B.Cu" signal)\n'
                    '\t\t(25 "Edge.Cuts" user)\n'
                    "\t)\n"
                    "\t(setup\n"
                    "\t\t(pad_to_mask_clearance 0)\n"
                    "\t)\n"
                    '\t(footprint "Device:R_0603" (layer "F.Cu") (at 0 0))\n'
                    '\t(segment (start 0 0) (end 1 1) (width 0.2) (layer "F.Cu") (net 0))\n'
                    "\t(embedded_fonts no)\n"
                    ")\n"
                ),
            ]

        def save_output(self, output_path: Path):
            self.calls.append(("save_output", (output_path,), {}))
            output_path.write_text(self._texts.pop(0), encoding="utf-8")

    input_path = tmp_path / "input" / "demo.PcbDoc"
    input_path.parent.mkdir(parents=True, exist_ok=True)
    input_path.write_text("mock pcb", encoding="utf-8")
    output_root = tmp_path / "output"
    driver = FlakySaveDriver()
    monkeypatch.setattr(pcb_import_module.time, "sleep", lambda _seconds: None)

    result = run_pcb_gui_import(
        input_path,
        output_root,
        driver_factory=lambda *_args, **_kwargs: driver,
        job_id="job-43-retry",
    )

    assert result["board_path"].read_text(encoding="utf-8").count("(footprint ") == 1
    assert [call[0] for call in driver.calls].count("save_output") == 2


def test_stage_input_file_copies_whole_project_tree_for_prjpcb(tmp_path: Path) -> None:
    source_root = tmp_path / "source"
    source_root.mkdir()
    project_file = source_root / "demo.PrjPcb"
    board_file = source_root / "demo.PcbDoc"
    project_file.write_text("project", encoding="utf-8")
    board_file.write_text("board", encoding="utf-8")
    workspace = create_job_workspace(tmp_path / "output", "job-44")

    staged_project = _stage_input_file(project_file, workspace)

    assert staged_project.read_text(encoding="utf-8") == "project"
    assert (staged_project.parent / "demo.PcbDoc").read_text(encoding="utf-8") == "board"

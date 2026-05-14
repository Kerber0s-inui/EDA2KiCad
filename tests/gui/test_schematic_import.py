from pathlib import Path

import pytest

from eda2kicad.gui import schematic_import as schematic_import_module
from eda2kicad.gui.schematic_import import run_schematic_gui_import


class FakeDriver:
    def __init__(self, *, schematic_text: str = "(kicad_sch (version 20231120))") -> None:
        self.schematic_text = schematic_text
        self.calls: list[tuple[str, tuple, dict]] = []

    def launch_kicad(self, kicad_exe, project_path=None):
        self.calls.append(("launch_kicad", (kicad_exe, project_path), {}))

    def wait_main_window(self, timeout_seconds: int):
        self.calls.append(("wait_main_window", (timeout_seconds,), {}))

    def open_pcb_import(self, input_path: Path):
        self.calls.append(("open_pcb_import", (input_path,), {}))

    def open_schematic_editor(self):
        self.calls.append(("open_schematic_editor", (), {}))

    def confirm_editor_creation(self):
        self.calls.append(("confirm_editor_creation", (), {}))

    def open_schematic_editor_import(self):
        self.calls.append(("open_schematic_editor_import", (), {}))

    def select_input_file(self, input_path: Path):
        self.calls.append(("select_input_file", (input_path,), {}))

    def confirm_import(self, output_path: Path):
        self.calls.append(("confirm_import", (output_path,), {}))

    def wait_import_complete(self, timeout_seconds: int):
        self.calls.append(("wait_import_complete", (timeout_seconds,), {}))

    def validate_post_import_editor_state(self):
        self.calls.append(("validate_post_import_editor_state", (), {}))

    def save_schematic_output(self, output_path: Path):
        self.calls.append(("save_schematic_output", (output_path,), {}))
        output_path.write_text(self.schematic_text, encoding="utf-8")

    def close_kicad(self):
        self.calls.append(("close_kicad", (), {}))


def test_run_schematic_gui_import_happy_path(tmp_path: Path) -> None:
    input_path = tmp_path / "input" / "demo.PrjPcb"
    input_path.parent.mkdir(parents=True, exist_ok=True)
    input_path.write_text("mock project", encoding="utf-8")
    output_root = tmp_path / "output"
    driver = FakeDriver()

    result = run_schematic_gui_import(
        input_path,
        output_root,
        kicad_exe=Path("C:/KiCad/kicad.exe"),
        timeout_seconds=12,
        driver_factory=lambda *_args, **_kwargs: driver,
        job_id="job-45",
    )

    assert [call[0] for call in driver.calls] == [
        "launch_kicad",
        "wait_main_window",
        "open_pcb_import",
        "select_input_file",
        "confirm_import",
        "wait_import_complete",
        "validate_post_import_editor_state",
        "save_schematic_output",
        "close_kicad",
    ]
    assert result["project_name"] == "demo"
    assert result["schematic_path"].read_text(encoding="utf-8").startswith("(kicad_sch")
    assert result["project_path"] is not None
    assert result["report"]["automation"]["phase"] == "complete"


def test_run_schematic_gui_import_uses_empty_project_flow_for_schdoc(tmp_path: Path) -> None:
    input_path = tmp_path / "input" / "demo.SchDoc"
    input_path.parent.mkdir(parents=True, exist_ok=True)
    input_path.write_text("mock sch", encoding="utf-8")
    output_root = tmp_path / "output"
    driver = FakeDriver()

    result = run_schematic_gui_import(
        input_path,
        output_root,
        kicad_exe=Path("C:/KiCad/kicad.exe"),
        timeout_seconds=12,
        driver_factory=lambda *_args, **_kwargs: driver,
        job_id="job-45",
    )

    assert [call[0] for call in driver.calls] == [
        "launch_kicad",
        "wait_main_window",
        "open_schematic_editor",
        "confirm_editor_creation",
        "open_schematic_editor_import",
        "select_input_file",
        "confirm_import",
        "wait_import_complete",
        "validate_post_import_editor_state",
        "save_schematic_output",
        "close_kicad",
    ]
    assert driver.calls[0][1][1] == result["project_path"]
    assert result["project_name"] == "demo"
    assert result["schematic_path"].read_text(encoding="utf-8").startswith("(kicad_sch")
    assert result["project_path"] is not None
    assert result["report"]["automation"]["phase"] == "complete"
    assert result["report"]["automation"]["debug"]["source_input"] == str(input_path)
    assert result["report"]["automation"]["debug"]["staged_input"].endswith("demo.SchDoc")
    assert result["report"]["automation"]["debug"]["workflow_mode"] == "schematic-standalone"
    assert result["report"]["automation"]["debug"]["requested_schematic_output"] == str(result["schematic_path"])


def test_run_schematic_gui_import_uses_90_second_timeout_by_default(tmp_path: Path) -> None:
    input_path = tmp_path / "input" / "demo.SchDoc"
    input_path.parent.mkdir(parents=True, exist_ok=True)
    input_path.write_text("mock sch", encoding="utf-8")
    output_root = tmp_path / "output"
    driver = FakeDriver()

    run_schematic_gui_import(
        input_path,
        output_root,
        kicad_exe=Path("C:/KiCad/kicad.exe"),
        driver_factory=lambda *_args, **_kwargs: driver,
        job_id="job-45-default-timeout",
    )

    assert ("wait_main_window", (90,), {}) in driver.calls
    assert ("wait_import_complete", (90,), {}) in driver.calls


def test_run_schematic_gui_import_rejects_invalid_output(tmp_path: Path) -> None:
    input_path = tmp_path / "input" / "demo.SchDoc"
    input_path.parent.mkdir(parents=True, exist_ok=True)
    input_path.write_text("mock sch", encoding="utf-8")
    output_root = tmp_path / "output"
    driver = FakeDriver(schematic_text="not a kicad schematic")

    with pytest.raises(ValueError, match="save_output"):
        run_schematic_gui_import(
            input_path,
            output_root,
            driver_factory=lambda *_args, **_kwargs: driver,
            job_id="job-46",
        )


def test_run_schematic_gui_import_rejects_empty_kicad_skeleton_output(tmp_path: Path) -> None:
    input_path = tmp_path / "input" / "demo.SchDoc"
    input_path.parent.mkdir(parents=True, exist_ok=True)
    input_path.write_text("mock sch", encoding="utf-8")
    output_root = tmp_path / "output"
    driver = FakeDriver(
        schematic_text=(
            "(kicad_sch\n"
            "\t(version 20260306)\n"
            '\t(generator "eeschema")\n'
            '\t(lib_symbols)\n'
            "\t(sheet_instances\n"
            '\t\t(path "/"\n'
            '\t\t\t(page "1")\n'
            "\t\t)\n"
            "\t)\n"
            "\t(embedded_fonts no)\n"
            ")\n"
        )
    )

    with pytest.raises(ValueError, match="appears empty after import"):
        run_schematic_gui_import(
            input_path,
            output_root,
            driver_factory=lambda *_args, **_kwargs: driver,
            job_id="job-47",
        )


def test_run_schematic_gui_import_retries_empty_standalone_save_once_before_succeeding(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FlakySaveDriver(FakeDriver):
        def __init__(self) -> None:
            super().__init__()
            self._texts = [
                (
                    "(kicad_sch\n"
                    "\t(version 20260306)\n"
                    '\t(generator "eeschema")\n'
                    '\t(lib_symbols)\n'
                    "\t(sheet_instances\n"
                    '\t\t(path "/"\n'
                    '\t\t\t(page "1")\n'
                    "\t\t)\n"
                    "\t)\n"
                    "\t(embedded_fonts no)\n"
                    ")\n"
                ),
                (
                    "(kicad_sch\n"
                    "\t(version 20260306)\n"
                    '\t(generator "eeschema")\n'
                    '\t(symbol (lib_id \"Device:R\") (at 0 0 0))\n'
                    "\t(lib_symbols)\n"
                    "\t(sheet_instances\n"
                    '\t\t(path "/"\n'
                    '\t\t\t(page "1")\n'
                    "\t\t)\n"
                    "\t)\n"
                    "\t(embedded_fonts no)\n"
                    ")\n"
                ),
            ]

        def save_schematic_output(self, output_path: Path):
            self.calls.append(("save_schematic_output", (output_path,), {}))
            output_path.write_text(self._texts.pop(0), encoding="utf-8")

    input_path = tmp_path / "input" / "demo.SchDoc"
    input_path.parent.mkdir(parents=True, exist_ok=True)
    input_path.write_text("mock sch", encoding="utf-8")
    output_root = tmp_path / "output"
    driver = FlakySaveDriver()
    monkeypatch.setattr(schematic_import_module.time, "sleep", lambda _seconds: None)

    result = run_schematic_gui_import(
        input_path,
        output_root,
        driver_factory=lambda *_args, **_kwargs: driver,
        job_id="job-48",
    )

    assert result["schematic_path"].read_text(encoding="utf-8").count("(symbol ") == 1
    assert [call[0] for call in driver.calls].count("save_schematic_output") == 2


def test_run_schematic_gui_import_captures_failure_diagnostics_before_closing_kicad(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FailingDriver(FakeDriver):
        def save_schematic_output(self, output_path: Path):
            self.calls.append(("save_schematic_output", (output_path,), {}))
            output_path.write_text("not a kicad schematic", encoding="utf-8")

    input_path = tmp_path / "input" / "demo.SchDoc"
    input_path.parent.mkdir(parents=True, exist_ok=True)
    input_path.write_text("mock sch", encoding="utf-8")
    output_root = tmp_path / "output"
    driver = FailingDriver()
    seen: list[list[str]] = []

    def fake_capture(runtime, captured_driver) -> None:
        del runtime
        assert captured_driver is driver
        seen.append([call[0] for call in driver.calls])

    monkeypatch.setattr(
        schematic_import_module,
        "capture_gui_failure_diagnostics",
        fake_capture,
    )

    with pytest.raises(ValueError, match="save_output"):
        run_schematic_gui_import(
            input_path,
            output_root,
            driver_factory=lambda *_args, **_kwargs: driver,
            job_id="job-49",
        )

    assert seen == [[
        "launch_kicad",
        "wait_main_window",
        "open_schematic_editor",
        "confirm_editor_creation",
        "open_schematic_editor_import",
        "select_input_file",
        "confirm_import",
        "wait_import_complete",
        "validate_post_import_editor_state",
        "save_schematic_output",
    ]]
    assert [call[0] for call in driver.calls][-1] == "close_kicad"

from pathlib import Path

from eda2kicad.gui.runtime import GuiAutomationRuntime


def test_runtime_records_failure_metadata(tmp_path: Path) -> None:
    runtime = GuiAutomationRuntime(artifacts_dir=tmp_path / "artifacts")
    runtime.set_phase("import")
    runtime.log_step("launch")
    log_path = runtime.write_log_file()
    runtime.record_failure(
        message="import failed",
        screenshot_path=tmp_path / "artifacts" / "failure.png",
        window_dump_path=tmp_path / "artifacts" / "windows.json",
        error_code="import_failed",
    )

    report = runtime.to_report()

    assert report["automation"]["phase"] == "import"
    assert report["automation"]["last_action"] == "launch"
    assert report["automation"]["artifacts_dir"] == str(tmp_path / "artifacts")
    assert report["automation"]["log"] == str(log_path)
    assert report["automation"]["steps"] == ["launch"]
    assert report["automation"]["screenshot"] == str(tmp_path / "artifacts" / "failure.png")
    assert report["automation"]["window_dump"] == str(tmp_path / "artifacts" / "windows.json")
    assert report["automation"]["failure"]["message"] == "import failed"
    assert report["automation"]["failure"]["error_code"] == "import_failed"


def test_runtime_includes_debug_context_in_report_and_log(tmp_path: Path) -> None:
    runtime = GuiAutomationRuntime(artifacts_dir=tmp_path / "artifacts")
    runtime.log_step("launch")
    runtime.record_debug_value("source_input", "C:/src/demo.PcbDoc")
    runtime.record_debug_value("staged_input", "C:/job/input/demo.PcbDoc")
    log_path = runtime.write_log_file()

    report = runtime.to_report()
    log_text = log_path.read_text(encoding="utf-8")

    assert report["automation"]["debug"]["source_input"] == "C:/src/demo.PcbDoc"
    assert report["automation"]["debug"]["staged_input"] == "C:/job/input/demo.PcbDoc"
    assert "source_input=C:/src/demo.PcbDoc" in log_text
    assert "staged_input=C:/job/input/demo.PcbDoc" in log_text

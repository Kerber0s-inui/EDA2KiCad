from __future__ import annotations

import time
from contextlib import suppress
from pathlib import Path
from uuid import uuid4

from eda2kicad.gui.driver import KiCadGuiDriver
from eda2kicad.gui.pcb_import import (
    _create_empty_project_file,
    _default_driver_factory,
    _resolve_project_file,
    _stage_input_file,
)
from eda2kicad.gui.runtime import GuiAutomationRuntime
from eda2kicad.gui.runtime import capture_gui_failure_diagnostics
from eda2kicad.gui.session import (
    acquire_gui_job_lock,
    assert_gui_environment_ready,
    create_job_workspace,
)


def _validate_kicad_schematic(schematic_path: Path, phase: str) -> None:
    if not schematic_path.exists():
        raise ValueError(f"{phase}: output file does not exist: {schematic_path}")
    schematic_text = schematic_path.read_text(encoding="utf-8", errors="ignore")
    if "(kicad_sch" not in schematic_text:
        raise ValueError(f"{phase}: output file is not a KiCad schematic file: {schematic_path}")
    if _looks_like_empty_schematic_skeleton(schematic_text):
        raise ValueError(f"{phase}: output schematic appears empty after import: {schematic_path}")


def _looks_like_empty_schematic_skeleton(schematic_text: str) -> bool:
    stripped_lines = [line.strip() for line in schematic_text.splitlines() if line.strip()]
    if not stripped_lines:
        return True
    joined = "\n".join(stripped_lines)
    skeleton_markers = [
        "(kicad_sch",
        "(version ",
        '(generator "eeschema")',
        "(lib_symbols)",
        "(sheet_instances",
        "(embedded_fonts no)",
    ]
    if not all(marker in joined for marker in skeleton_markers):
        return False

    content_markers = [
        "(symbol ",
        "(wire ",
        "(junction ",
        "(text ",
        "(label ",
        "(hierarchical_label ",
        "(global_label ",
        "(bus ",
        "(bus_entry ",
        "(polyline ",
        "(rectangle ",
        "(arc ",
        "(circle ",
        "(image ",
        "(sheet ",
    ]
    return not any(marker in joined for marker in content_markers)


def _save_validated_schematic_output(
    driver: KiCadGuiDriver,
    schematic_path: Path,
    *,
    runtime: GuiAutomationRuntime,
    standalone_import: bool,
    retry_count: int = 2,
    retry_delay_seconds: float = 2.0,
) -> None:
    attempts = 1 if not standalone_import else retry_count + 1
    last_error: Exception | None = None

    for attempt in range(1, attempts + 1):
        driver.save_schematic_output(schematic_path)
        try:
            _validate_kicad_schematic(schematic_path, "save_output")
            if attempt > 1:
                runtime.record_debug_value("save_schematic_retry_attempts", attempt - 1)
            return
        except ValueError as exc:
            last_error = exc
            if not standalone_import or "appears empty after import" not in str(exc) or attempt >= attempts:
                raise
            runtime.log_step(f"retry_save_schematic_output_{attempt}")
            time.sleep(retry_delay_seconds)

    if last_error is not None:
        raise last_error


def run_schematic_gui_import(
    input_path: Path,
    output_root: Path,
    *,
    kicad_exe: Path | None = None,
    timeout_seconds: int = 90,
    job_id: str | None = None,
    driver_factory=_default_driver_factory,
) -> dict[str, object]:
    input_path = Path(input_path)
    output_root = Path(output_root)
    if not input_path.exists():
        raise ValueError(f"precheck: input file does not exist: {input_path}")

    assert_gui_environment_ready(kicad_exe)
    job_id = job_id or uuid4().hex
    workspace = create_job_workspace(output_root, job_id)
    runtime = GuiAutomationRuntime(artifacts_dir=workspace.artifacts_dir)
    runtime.set_phase("precheck")
    runtime.log_step("create_job_workspace")
    runtime.record_debug_value("source_input", str(input_path))
    staged_input = _stage_input_file(input_path, workspace)
    runtime.log_step("stage_input")
    runtime.record_debug_value("staged_input", str(staged_input))

    driver: KiCadGuiDriver = driver_factory(
        workspace=workspace,
        runtime=runtime,
        kicad_exe=kicad_exe,
        timeout_seconds=timeout_seconds,
    )

    project_name = input_path.stem
    schematic_path = workspace.output_dir / f"{project_name}.kicad_sch"
    project_path = workspace.output_dir / f"{project_name}.kicad_pro"
    board_probe_path = workspace.output_dir / f"{project_name}.kicad_pcb"
    standalone_import = input_path.suffix.lower() == ".schdoc"
    runtime.record_debug_value("workflow_mode", "schematic-standalone" if standalone_import else "project-import")
    runtime.record_debug_value("requested_schematic_output", str(schematic_path))
    runtime.record_debug_value("requested_project_output", str(project_path))
    if standalone_import:
        project_path = _create_empty_project_file(workspace.output_dir, project_name)
        runtime.record_debug_value("launch_project_path", str(project_path))

    try:
        with acquire_gui_job_lock(workspace):
            runtime.set_phase("launch_kicad")
            runtime.log_step("launch_kicad")
            driver.launch_kicad(kicad_exe, project_path if standalone_import else None)

            runtime.set_phase("wait_main_window")
            runtime.log_step("wait_main_window")
            driver.wait_main_window(timeout_seconds)

            runtime.set_phase("open_import")
            if standalone_import:
                runtime.log_step("open_schematic_editor")
                driver.open_schematic_editor()

                runtime.set_phase("prepare_editor")
                runtime.log_step("confirm_editor_creation")
                driver.confirm_editor_creation()

                runtime.set_phase("open_import")
                runtime.log_step("open_schematic_editor_import")
                driver.open_schematic_editor_import()
            else:
                runtime.log_step("open_pcb_import")
                driver.open_pcb_import(staged_input)

            runtime.set_phase("select_input_file")
            runtime.log_step("select_input_file")
            driver.select_input_file(staged_input)

            runtime.set_phase("confirm_import")
            runtime.log_step("confirm_import")
            driver.confirm_import(board_probe_path)

            runtime.set_phase("wait_import_complete")
            runtime.log_step("wait_import_complete")
            driver.wait_import_complete(timeout_seconds)
            driver.validate_post_import_editor_state()

            runtime.set_phase("save_output")
            runtime.log_step("save_schematic_output")
            _save_validated_schematic_output(
                driver,
                schematic_path,
                runtime=runtime,
                standalone_import=standalone_import,
            )
            runtime.record_debug_value("final_schematic_path", str(schematic_path))
            project_path = _resolve_project_file(workspace.output_dir, project_path, project_name, board_probe_path)
            runtime.record_debug_value("final_project_path", str(project_path))

            runtime.set_phase("close_kicad")
            runtime.log_step("close_kicad")
            driver.close_kicad()

            runtime.set_phase("complete")
            runtime.write_log_file()
            report = runtime.to_report()
            return {
                "project_name": project_name,
                "schematic_path": schematic_path,
                "project_path": project_path,
                "report": report,
                "artifacts_dir": workspace.artifacts_dir,
                "run_dir": workspace.run_dir,
            }
    except Exception as exc:
        runtime.record_failure(
            f"{runtime.phase}: {exc}",
            error_code="schematic_gui_import_failed",
        )
        capture_gui_failure_diagnostics(runtime, driver)
        with suppress(Exception):
            if runtime.phase != "close_kicad":
                driver.close_kicad()
        runtime.write_log_file()
        raise ValueError(f"{runtime.phase}: {exc}") from exc

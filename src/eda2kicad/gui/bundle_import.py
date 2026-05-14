from __future__ import annotations

from contextlib import suppress
from pathlib import Path
from uuid import uuid4

from eda2kicad.gui.pcb_import import (
    _create_empty_project_file,
    _default_driver_factory,
    _resolve_project_file,
    _stage_input_file,
    save_validated_pcb_output,
)
from eda2kicad.gui.runtime import GuiAutomationRuntime
from eda2kicad.gui.runtime import capture_gui_failure_diagnostics
from eda2kicad.gui.schematic_import import _validate_kicad_schematic
from eda2kicad.gui.session import (
    acquire_gui_job_lock,
    assert_gui_environment_ready,
    create_job_workspace,
)


def run_combined_gui_import(
    *,
    pcb_input: Path | None,
    schematic_input: Path | None,
    project_input: Path | None = None,
    output_root: Path,
    kicad_exe: Path | None = None,
    timeout_seconds: int = 90,
    job_id: str | None = None,
    driver_factory=_default_driver_factory,
) -> dict[str, object]:
    if pcb_input is None and schematic_input is None:
        raise ValueError("combined gui import requires pcb_input or schematic_input")

    output_root = Path(output_root)
    pcb_input = Path(pcb_input) if pcb_input is not None else None
    schematic_input = Path(schematic_input) if schematic_input is not None else None
    project_input = Path(project_input) if project_input is not None else None

    assert_gui_environment_ready(kicad_exe)
    job_id = job_id or uuid4().hex
    workspace = create_job_workspace(output_root, job_id)
    runtime = GuiAutomationRuntime(artifacts_dir=workspace.artifacts_dir)
    runtime.set_phase("precheck")
    runtime.log_step("create_job_workspace")
    runtime.record_debug_value("source_project_input", str(project_input) if project_input is not None else None)
    runtime.record_debug_value("source_pcb_input", str(pcb_input) if pcb_input is not None else None)
    runtime.record_debug_value("source_schematic_input", str(schematic_input) if schematic_input is not None else None)

    staged_project_input = None
    if project_input is not None:
        staged_project_input = _stage_input_file(project_input, workspace)
        runtime.log_step("stage_project_input")
        runtime.record_debug_value("staged_project_input", str(staged_project_input))

    staged_pcb_input = _resolve_staged_bundle_input(pcb_input, staged_project_input, workspace)
    if staged_pcb_input is not None:
        runtime.log_step("stage_pcb_input")
        runtime.record_debug_value("staged_pcb_input", str(staged_pcb_input))

    staged_schematic_input = _resolve_staged_bundle_input(schematic_input, staged_project_input, workspace)
    if staged_schematic_input is not None:
        runtime.log_step("stage_schematic_input")
        runtime.record_debug_value("staged_schematic_input", str(staged_schematic_input))

    driver = driver_factory(
        workspace=workspace,
        runtime=runtime,
        kicad_exe=kicad_exe,
        timeout_seconds=timeout_seconds,
    )

    project_name = _resolve_project_name(project_input, pcb_input, schematic_input)
    board_path = workspace.output_dir / f"{project_name}.kicad_pcb"
    schematic_path = workspace.output_dir / f"{project_name}.kicad_sch"
    project_path = workspace.output_dir / f"{project_name}.kicad_pro"
    launch_project_path = None
    runtime.record_debug_value("workflow_mode", "project-bundle" if project_input is not None else "shared-empty-project")
    runtime.record_debug_value("requested_board_output", str(board_path))
    runtime.record_debug_value("requested_schematic_output", str(schematic_path))
    runtime.record_debug_value("requested_project_output", str(project_path))
    if project_input is None:
        launch_project_path = _create_empty_project_file(workspace.output_dir, project_name)
        project_path = launch_project_path
        runtime.record_debug_value("launch_project_path", str(project_path))

    try:
        with acquire_gui_job_lock(workspace):
            runtime.set_phase("launch_kicad")
            runtime.log_step("launch_kicad")
            driver.launch_kicad(kicad_exe, launch_project_path)

            runtime.set_phase("wait_main_window")
            runtime.log_step("wait_main_window")
            driver.wait_main_window(timeout_seconds)

            if staged_project_input is not None:
                runtime.set_phase("project_import")
                runtime.log_step("open_project_import")
                driver.open_pcb_import(staged_project_input)

                runtime.set_phase("select_project_input")
                runtime.log_step("select_project_input")
                driver.select_input_file(staged_project_input)

                runtime.set_phase("confirm_project_import")
                runtime.log_step("confirm_project_import")
                driver.confirm_import(board_path if staged_pcb_input is not None else schematic_path)

                runtime.set_phase("wait_project_import_complete")
                runtime.log_step("wait_project_import_complete")
                driver.wait_import_complete(timeout_seconds)
                driver.validate_post_import_editor_state()
            else:
                if staged_pcb_input is not None:
                    _import_board_into_empty_project(
                        driver=driver,
                        runtime=runtime,
                        staged_input=staged_pcb_input,
                        board_path=board_path,
                        timeout_seconds=timeout_seconds,
                    )

                if staged_schematic_input is not None:
                    _import_schematic_into_empty_project(
                        driver=driver,
                        runtime=runtime,
                        staged_input=staged_schematic_input,
                        schematic_path=schematic_path,
                        timeout_seconds=timeout_seconds,
                    )

            if staged_project_input is not None and staged_pcb_input is not None:
                runtime.set_phase("save_board_output")
                runtime.log_step("save_board_output")
                save_validated_pcb_output(
                    driver,
                    board_path,
                    runtime=runtime,
                    allow_retry_on_empty=False,
                )
                runtime.record_debug_value("final_board_path", str(board_path))

            if staged_project_input is not None and staged_schematic_input is not None:
                runtime.set_phase("save_schematic_output")
                runtime.log_step("save_schematic_output")
                driver.save_schematic_output(schematic_path)
                _validate_kicad_schematic(schematic_path, "save_schematic_output")
                runtime.record_debug_value("final_schematic_path", str(schematic_path))

            project_path = _resolve_project_file(workspace.output_dir, project_path, project_name, board_path)
            runtime.record_debug_value("final_project_path", str(project_path))

            runtime.set_phase("close_kicad")
            runtime.log_step("close_kicad")
            driver.close_kicad()

            runtime.set_phase("complete")
            runtime.write_log_file()
            return {
                "project_name": project_name,
                "project_path": project_path,
                "board_path": board_path if board_path.exists() else None,
                "schematic_path": schematic_path if schematic_path.exists() else None,
                "report": runtime.to_report(),
                "artifacts_dir": workspace.artifacts_dir,
                "run_dir": workspace.run_dir,
            }
    except Exception as exc:
        runtime.record_failure(
            f"{runtime.phase}: {exc}",
            error_code="combined_gui_import_failed",
        )
        capture_gui_failure_diagnostics(runtime, driver)
        with suppress(Exception):
            if runtime.phase != "close_kicad":
                driver.close_kicad()
        runtime.write_log_file()
        raise ValueError(f"{runtime.phase}: {exc}") from exc


def _resolve_project_name(
    project_input: Path | None,
    pcb_input: Path | None,
    schematic_input: Path | None,
) -> str:
    for candidate in (project_input, pcb_input, schematic_input):
        if candidate is not None:
            return candidate.stem
    raise ValueError("combined gui import requires at least one input")


def _resolve_staged_bundle_input(
    input_path: Path | None,
    staged_project_input: Path | None,
    workspace,
) -> Path | None:
    if input_path is None:
        return None
    if staged_project_input is not None:
        candidate = staged_project_input.parent / input_path.name
        if candidate.exists():
            return candidate
    return _stage_input_file(input_path, workspace)


def _import_board_into_empty_project(
    *,
    driver,
    runtime: GuiAutomationRuntime,
    staged_input: Path,
    board_path: Path,
    timeout_seconds: int,
) -> None:
    runtime.set_phase("open_pcb_editor")
    runtime.log_step("open_pcb_editor")
    driver.open_pcb_editor()

    runtime.set_phase("confirm_pcb_editor_creation")
    runtime.log_step("confirm_pcb_editor_creation")
    driver.confirm_editor_creation()

    runtime.set_phase("open_pcb_editor_import")
    runtime.log_step("open_pcb_editor_import")
    driver.open_pcb_editor_import()

    runtime.set_phase("select_pcb_input")
    runtime.log_step("select_pcb_input")
    driver.select_input_file(staged_input)

    runtime.set_phase("confirm_pcb_import")
    runtime.log_step("confirm_pcb_import")
    driver.confirm_import(board_path)

    runtime.set_phase("wait_pcb_import_complete")
    runtime.log_step("wait_pcb_import_complete")
    driver.wait_import_complete(timeout_seconds)
    driver.validate_post_import_editor_state()

    runtime.set_phase("save_board_output")
    runtime.log_step("save_board_output")
    save_validated_pcb_output(
        driver,
        board_path,
        runtime=runtime,
        allow_retry_on_empty=True,
    )


def _import_schematic_into_empty_project(
    *,
    driver,
    runtime: GuiAutomationRuntime,
    staged_input: Path,
    schematic_path: Path,
    timeout_seconds: int,
) -> None:
    runtime.set_phase("open_schematic_editor")
    runtime.log_step("open_schematic_editor")
    driver.open_schematic_editor()

    runtime.set_phase("confirm_schematic_editor_creation")
    runtime.log_step("confirm_schematic_editor_creation")
    driver.confirm_editor_creation()

    runtime.set_phase("open_schematic_editor_import")
    runtime.log_step("open_schematic_editor_import")
    driver.open_schematic_editor_import()

    runtime.set_phase("select_schematic_input")
    runtime.log_step("select_schematic_input")
    driver.select_input_file(staged_input)

    runtime.set_phase("confirm_schematic_import")
    runtime.log_step("confirm_schematic_import")
    driver.confirm_import(schematic_path)

    runtime.set_phase("wait_schematic_import_complete")
    runtime.log_step("wait_schematic_import_complete")
    driver.wait_import_complete(timeout_seconds)
    driver.validate_post_import_editor_state()

    runtime.set_phase("save_schematic_output")
    runtime.log_step("save_schematic_output")
    driver.save_schematic_output(schematic_path)
    _validate_kicad_schematic(schematic_path, "save_schematic_output")

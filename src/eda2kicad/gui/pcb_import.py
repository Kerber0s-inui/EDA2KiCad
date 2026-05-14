from __future__ import annotations

import shutil
import time
from contextlib import suppress
from pathlib import Path
from uuid import uuid4

from eda2kicad.gui.driver import KiCadGuiDriver
from eda2kicad.gui.runtime import GuiAutomationRuntime
from eda2kicad.gui.runtime import capture_gui_failure_diagnostics
from eda2kicad.gui.session import (
    GuiJobWorkspace,
    acquire_gui_job_lock,
    assert_gui_environment_ready,
    create_job_workspace,
)
from eda2kicad.strategies.tooling import KICAD_TEMPLATE_PROJECT_PATH


def _default_driver_factory(
    *,
    workspace: GuiJobWorkspace,
    runtime: GuiAutomationRuntime,
    kicad_exe: Path | None,
    timeout_seconds: int,
) -> KiCadGuiDriver:
    return KiCadGuiDriver(artifacts_dir=workspace.artifacts_dir, runtime=runtime)


def _validate_kicad_pcb(board_path: Path, phase: str) -> None:
    if not board_path.exists():
        raise ValueError(f"{phase}: output file does not exist: {board_path}")
    board_text = board_path.read_text(encoding="utf-8", errors="ignore")
    if "(kicad_pcb" not in board_text:
        raise ValueError(f"{phase}: output file is not a KiCad PCB file: {board_path}")
    if _looks_like_empty_pcb_skeleton(board_text):
        raise ValueError(f"{phase}: output pcb appears empty after import: {board_path}")


def _looks_like_empty_pcb_skeleton(board_text: str) -> bool:
    stripped_lines = [line.strip() for line in board_text.splitlines() if line.strip()]
    if not stripped_lines:
        return True
    joined = "\n".join(stripped_lines)
    skeleton_markers = [
        "(kicad_pcb",
        "(version ",
        '(generator "pcbnew")',
        "(layers",
        "(setup",
        "(embedded_fonts no)",
    ]
    if not all(marker in joined for marker in skeleton_markers):
        return False

    content_markers = [
        "(footprint ",
        "(segment ",
        "(via ",
        "(arc ",
        "(gr_line ",
        "(gr_arc ",
        "(gr_rect ",
        "(gr_poly ",
        "(gr_curve ",
        "(dimension ",
        "(zone ",
        "(target ",
        "(group ",
        "(net ",
    ]
    return not any(marker in joined for marker in content_markers)


def save_validated_pcb_output(
    driver: KiCadGuiDriver,
    board_path: Path,
    *,
    runtime: GuiAutomationRuntime,
    allow_retry_on_empty: bool,
    retry_count: int = 2,
    retry_delay_seconds: float = 2.0,
) -> None:
    attempts = retry_count + 1 if allow_retry_on_empty else 1
    last_error: Exception | None = None

    for attempt in range(1, attempts + 1):
        driver.save_output(board_path)
        try:
            _validate_kicad_pcb(board_path, "save_output")
            if attempt > 1:
                runtime.record_debug_value("save_pcb_retry_attempts", attempt - 1)
            return
        except ValueError as exc:
            last_error = exc
            if not allow_retry_on_empty or "appears empty after import" not in str(exc) or attempt >= attempts:
                raise
            runtime.log_step(f"retry_save_output_{attempt}")
            time.sleep(retry_delay_seconds)

    if last_error is not None:
        raise last_error


def _ensure_project_file(project_path: Path, project_name: str, board_path: Path) -> Path:
    if not project_path.exists():
        project_path.write_text(
            "{\n"
            f'  "board": "{board_path.name}",\n'
            f'  "project": "{project_name}"\n'
            "}\n",
            encoding="utf-8",
        )
    return project_path


def _resolve_project_file(output_dir: Path, project_path: Path, project_name: str, board_path: Path) -> Path:
    if project_path.exists():
        return project_path
    candidates = sorted(
        path
        for path in output_dir.glob("*.kicad_pro")
        if not path.name.endswith(".lck")
    )
    if len(candidates) == 1:
        return candidates[0]
    return _ensure_project_file(project_path, project_name, board_path)


def _create_empty_project_file(output_dir: Path, project_name: str) -> Path:
    if not KICAD_TEMPLATE_PROJECT_PATH.exists():
        raise ValueError(f"missing kicad project template: {KICAD_TEMPLATE_PROJECT_PATH}")
    project_path = output_dir / f"{project_name}.kicad_pro"
    shutil.copy2(KICAD_TEMPLATE_PROJECT_PATH, project_path)
    return project_path


def _stage_input_file(input_path: Path, workspace: GuiJobWorkspace) -> Path:
    if input_path.suffix.lower() != ".prjpcb":
        staged_input = workspace.input_dir / input_path.name
        shutil.copy2(input_path, staged_input)
        return staged_input

    staged_root = workspace.input_dir / input_path.parent.name
    if staged_root.exists():
        shutil.rmtree(staged_root)
    shutil.copytree(input_path.parent, staged_root)
    return staged_root / input_path.name


def run_pcb_gui_import(
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
    runtime.record_debug_value("driver_code_marker", "pcb-confirm-v3-alt-o")
    runtime.record_debug_value("source_input", str(input_path))
    staged_input = _stage_input_file(input_path, workspace)
    runtime.log_step("stage_input")
    runtime.record_debug_value("staged_input", str(staged_input))

    driver = driver_factory(
        workspace=workspace,
        runtime=runtime,
        kicad_exe=kicad_exe,
        timeout_seconds=timeout_seconds,
    )

    project_name = input_path.stem
    board_path = workspace.output_dir / f"{project_name}.kicad_pcb"
    project_path = workspace.output_dir / f"{project_name}.kicad_pro"
    standalone_import = input_path.suffix.lower() == ".pcbdoc"
    runtime.record_debug_value("workflow_mode", "pcb-standalone" if standalone_import else "project-import")
    runtime.record_debug_value("requested_board_output", str(board_path))
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
                runtime.log_step("open_pcb_editor")
                driver.open_pcb_editor()

                runtime.set_phase("prepare_editor")
                runtime.log_step("confirm_editor_creation")
                driver.confirm_editor_creation()

                runtime.set_phase("open_import")
                runtime.log_step("open_pcb_editor_import")
                driver.open_pcb_editor_import()
            else:
                runtime.log_step("open_pcb_import")
                driver.open_pcb_import(staged_input)

            runtime.set_phase("select_input_file")
            runtime.log_step("select_input_file")
            driver.select_input_file(staged_input)

            runtime.set_phase("confirm_import")
            runtime.log_step("confirm_import")
            driver.confirm_import(board_path)

            runtime.set_phase("wait_import_complete")
            runtime.log_step("wait_import_complete")
            driver.wait_import_complete(timeout_seconds)
            driver.validate_post_import_editor_state()

            runtime.set_phase("save_output")
            runtime.log_step("save_output")
            save_validated_pcb_output(
                driver,
                board_path,
                runtime=runtime,
                allow_retry_on_empty=standalone_import,
            )
            runtime.record_debug_value("final_board_path", str(board_path))
            project_path = _resolve_project_file(workspace.output_dir, project_path, project_name, board_path)
            runtime.record_debug_value("final_project_path", str(project_path))

            runtime.set_phase("close_kicad")
            runtime.log_step("close_kicad")
            driver.close_kicad()

            runtime.set_phase("complete")
            runtime.write_log_file()
            report = runtime.to_report()
            return {
                "project_name": project_name,
                "board_path": board_path,
                "project_path": project_path,
                "report": report,
                "artifacts_dir": workspace.artifacts_dir,
                "run_dir": workspace.run_dir,
            }
    except Exception as exc:
        runtime.record_failure(
            f"{runtime.phase}: {exc}",
            error_code="pcb_gui_import_failed",
        )
        capture_gui_failure_diagnostics(runtime, driver)
        with suppress(Exception):
            if runtime.phase != "close_kicad":
                driver.close_kicad()
        runtime.write_log_file()
        raise ValueError(f"{runtime.phase}: {exc}") from exc

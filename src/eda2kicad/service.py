import json
import shutil
import tempfile
from pathlib import Path
from typing import Any

from eda2kicad.jobs.planner import choose_job_mode, plan_job_inputs
from eda2kicad.jobs.runner import cleanup_intermediate_artifacts
from eda2kicad.jobs.workspace import create_job_workspace
from eda2kicad.paths import ensure_output_dir
from eda2kicad.strategies import kicad_gui_official
from eda2kicad.strategies import custom_pipeline
from eda2kicad.strategies.base import StrategyRunner
from eda2kicad.strategies.registry import STRATEGIES


class ConversionService:
    def __init__(self, mapping_path: Path) -> None:
        self.mapping_path = mapping_path

    def available_strategies(self) -> list[dict[str, object]]:
        return [metadata for metadata, _runner in STRATEGIES.values()]

    def _get_strategy_runner(self, strategy: str) -> StrategyRunner:
        try:
            _metadata, runner = STRATEGIES[strategy]
            return runner
        except KeyError as exc:
            raise ValueError(f"unknown strategy: {strategy}") from exc

    def convert_file(
        self,
        input_path: Path,
        output_dir: Path,
        strategy: str = custom_pipeline.STRATEGY_ID,
    ) -> dict[str, Path]:
        self._validate_supported_input(input_path)
        output_dir = ensure_output_dir(output_dir)
        plan_root = Path(tempfile.mkdtemp(prefix=".eda2kicad-plan-", dir=output_dir))
        planned = plan_job_inputs(input_path, plan_root / "extract")
        workspace = create_job_workspace(output_dir, planned.label)
        final_dir = workspace.final_dir
        job_mode = choose_job_mode(planned.prjpcb, planned.pcbdoc, planned.schdoc)
        run_reports: dict[str, dict[str, Any]] = {}
        artifacts: dict[str, Path] = {"job_dir": final_dir}

        try:
            if self._should_use_gui_bundle(strategy, planned.prjpcb, planned.pcbdoc, planned.schdoc):
                conversion = kicad_gui_official.convert_native_bundle(
                    pcb_input=planned.pcbdoc,
                    schematic_input=planned.schdoc,
                    project_input=planned.prjpcb,
                    output_root=final_dir,
                )
                artifacts.update(self._write_conversion_outputs(final_dir, conversion))
                run_reports["bundle"] = conversion["report"]
            else:
                if planned.pcbdoc is not None:
                    self._apply_conversion(planned.pcbdoc, final_dir, strategy, run_reports, artifacts, "board")
                if planned.schdoc is not None:
                    self._apply_conversion(planned.schdoc, final_dir, strategy, run_reports, artifacts, "schematic")
                elif planned.prjpcb is not None and planned.pcbdoc is None:
                    raise ValueError(f"strategy {strategy} does not support standalone .PrjPcb input")

            if ("board" in artifacts or "schematic" in artifacts) and "project" not in artifacts:
                artifacts["project"] = self._ensure_project_file(final_dir, planned.label, artifacts)

            report_path = final_dir / "report.json"
            report_payload = self._build_report(
                planned=planned,
                strategy=strategy,
                job_mode=job_mode,
                outputs=artifacts,
                run_reports=run_reports,
            )
            report_path.write_text(json.dumps(report_payload, indent=2), encoding="utf-8")
            cleanup_warnings = cleanup_intermediate_artifacts(final_dir, extra_paths=[final_dir / ".eda2kicad"])
            if cleanup_warnings:
                report_payload["cleanup"] = {"warnings": cleanup_warnings}
                report_path.write_text(json.dumps(report_payload, indent=2), encoding="utf-8")
            artifacts = {
                name: path
                for name, path in artifacts.items()
                if name == "job_dir" or path.exists()
            }
            artifacts["report"] = report_path
            return artifacts
        finally:
            shutil.rmtree(plan_root, ignore_errors=True)

    def _convert_single_input(
        self,
        input_path: Path,
        output_dir: Path,
        *,
        strategy: str,
    ) -> dict[str, Path]:
        workspace = create_job_workspace(output_dir, input_path.stem)
        final_dir = workspace.final_dir
        runner = self._get_strategy_runner(strategy)
        conversion = runner(input_path, self.mapping_path, final_dir)
        artifacts = self._write_conversion_outputs(final_dir, conversion)
        report_path = final_dir / "report.json"
        report_payload = dict(conversion["report"])
        report_path.write_text(json.dumps(report_payload, indent=2), encoding="utf-8")
        cleanup_warnings = cleanup_intermediate_artifacts(final_dir, extra_paths=[final_dir / ".eda2kicad"])
        if cleanup_warnings:
            report_payload["cleanup"] = {"warnings": cleanup_warnings}
            report_path.write_text(json.dumps(report_payload, indent=2), encoding="utf-8")
        artifacts = {
            name: path
            for name, path in artifacts.items()
            if path.exists()
        }
        artifacts["job_dir"] = final_dir
        artifacts["report"] = report_path
        return artifacts

    def _apply_conversion(
        self,
        input_path: Path,
        final_dir: Path,
        strategy: str,
        run_reports: dict[str, dict[str, Any]],
        artifacts: dict[str, Path],
        run_key: str,
    ) -> None:
        runner = self._get_strategy_runner(strategy)
        conversion = runner(input_path, self.mapping_path, final_dir)
        artifacts.update(self._write_conversion_outputs(final_dir, conversion))
        run_reports[run_key] = conversion["report"]

    @staticmethod
    def _write_conversion_outputs(final_dir: Path, conversion: dict[str, Any]) -> dict[str, Path]:
        artifacts: dict[str, Path] = {}
        if conversion["schematic_text"] is not None and conversion["schematic_extension"] is not None:
            schematic_path = final_dir / f"{conversion['project_name']}{conversion['schematic_extension']}"
            schematic_path.write_text(conversion["schematic_text"], encoding="utf-8")
            artifacts["schematic"] = schematic_path
        if conversion["board_text"] is not None and conversion["board_extension"] is not None:
            board_path = final_dir / f"{conversion['project_name']}{conversion['board_extension']}"
            board_path.write_text(conversion["board_text"], encoding="utf-8")
            artifacts["board"] = board_path
        for artifact_name, artifact_text in conversion["auxiliary_text_artifacts"].items():
            artifact_path = final_dir / artifact_name
            artifact_path.write_text(artifact_text, encoding="utf-8")
            if artifact_name.endswith("-cache.lib"):
                artifacts["cache_lib"] = artifact_path
            if artifact_name.endswith(".kicad_pro"):
                artifacts["project"] = artifact_path
        return artifacts

    @staticmethod
    def _should_use_gui_bundle(
        strategy: str,
        prjpcb: Path | None,
        pcbdoc: Path | None,
        schdoc: Path | None,
    ) -> bool:
        if strategy != kicad_gui_official.STRATEGY_ID:
            return False
        return prjpcb is not None or (pcbdoc is not None and schdoc is not None)

    @staticmethod
    def _ensure_project_file(final_dir: Path, project_name: str, outputs: dict[str, Path]) -> Path:
        project_path = final_dir / f"{project_name}.kicad_pro"
        board_name = outputs["board"].name if "board" in outputs else None
        schematic_name = outputs["schematic"].name if "schematic" in outputs else None
        payload = {
            "project": project_name,
            "board": board_name,
            "schematic": schematic_name,
        }
        project_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return project_path

    def _build_report(
        self,
        *,
        planned,
        strategy: str,
        job_mode: str,
        outputs: dict[str, Path],
        run_reports: dict[str, dict[str, Any]],
    ) -> dict[str, Any]:
        report_payload: dict[str, Any] = {
            "strategy": {"strategy_id": strategy},
            "job": {
                "input_mode": planned.input_mode,
                "job_mode": job_mode,
                "label": planned.label,
            },
            "inputs": {
                "prjpcb": str(planned.prjpcb) if planned.prjpcb is not None else None,
                "pcbdoc": str(planned.pcbdoc) if planned.pcbdoc is not None else None,
                "schdoc": str(planned.schdoc) if planned.schdoc is not None else None,
            },
            "outputs": {
                "board": str(outputs["board"]) if "board" in outputs else None,
                "schematic": str(outputs["schematic"]) if "schematic" in outputs else None,
                "project": str(outputs["project"]) if "project" in outputs else None,
            },
            "runs": run_reports,
        }
        if len(run_reports) == 1:
            only_report = next(iter(run_reports.values()))
            for key, value in only_report.items():
                if key not in report_payload:
                    report_payload[key] = value
        return report_payload

    @staticmethod
    def _validate_supported_input(input_path: Path) -> None:
        if input_path.suffix.lower() in {".zip", ".prjpcb", ".pcbdoc", ".schdoc"}:
            return
        raise ValueError(
            "only native Altium inputs are supported: .SchDoc, .PcbDoc, .PrjPcb or .zip bundles"
        )

import json
import subprocess
import tempfile
from pathlib import Path

from eda2kicad.altium_native import is_native_altium_path
from eda2kicad.strategies.base import ConversionPayload, StrategyMetadata, resolve_strategy_work_root
from eda2kicad.strategies.tooling import KICAD_CLI_PATH

STRATEGY_ID = "kicad-official"


def _run_kicad_cli(command: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, capture_output=True, text=True, check=False)


def get_strategy_metadata() -> StrategyMetadata:
    return {
        "strategy_id": STRATEGY_ID,
        "mode": "candidate",
        "uses_kicad_capability": True,
        "uses_external_project": False,
        "status": "active",
    }


def convert(
    input_path: Path,
    mapping_path: Path,
    output_root: Path | None = None,
) -> ConversionPayload:
    if not is_native_altium_path(input_path):
        raise ValueError("kicad-official strategy only supports native Altium .PcbDoc input")
    if input_path.suffix.lower() == ".pcbdoc":
        if output_root is None:
            return convert_native_pcb(input_path)
        return convert_native_pcb(input_path, output_root=output_root)
    raise ValueError("kicad-official strategy only supports native Altium .PcbDoc input")


def convert_native_pcb(input_path: Path, *, output_root: Path | None = None) -> ConversionPayload:
    if not KICAD_CLI_PATH.exists():
        raise ValueError(f"missing kicad-cli: {KICAD_CLI_PATH}")

    temp_root = resolve_strategy_work_root("kicad-official-native", output_root)
    run_dir = Path(tempfile.mkdtemp(prefix="pcb-import-", dir=temp_root))
    output_path = run_dir / f"{input_path.stem}.kicad_pcb"
    report_path = run_dir / "official-import-report.json"
    command = [
        str(KICAD_CLI_PATH),
        "pcb",
        "import",
        "--format",
        "altium",
        "--output",
        str(output_path),
        "--report-format",
        "json",
        "--report-file",
        str(report_path),
        str(input_path),
    ]
    result = _run_kicad_cli(command)
    if result.returncode != 0:
        stderr = result.stderr.strip() or result.stdout.strip() or "kicad-cli import failed"
        raise ValueError(stderr)
    if not output_path.exists():
        raise ValueError("kicad-cli import did not create output board")

    report_payload: dict[str, object] = {"summary": {"error_count": 0, "warning_count": 0}, "issues": []}
    if report_path.exists():
        try:
            report_payload["official_import_report"] = json.loads(report_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            report_payload["official_import_report"] = report_path.read_text(encoding="utf-8", errors="replace")
    report_payload["strategy"] = get_strategy_metadata()
    return {
        "project_name": input_path.stem,
        "schematic_text": None,
        "schematic_extension": None,
        "board_text": output_path.read_text(encoding="utf-8"),
        "board_extension": ".kicad_pcb",
        "auxiliary_text_artifacts": {},
        "report": report_payload,
    }

from pathlib import Path

from eda2kicad.altium_native import is_native_altium_path, parse_native_schematic_project
from eda2kicad.kicad.writer import render_kicad_schematic
from eda2kicad.symbols.resolver import resolve_symbol
from eda2kicad.strategies.base import ConversionPayload, StrategyMetadata, resolve_strategy_work_root
from eda2kicad.validation.checks import validate_project

STRATEGY_ID = "custom"


def get_strategy_metadata() -> StrategyMetadata:
    return {
        "strategy_id": STRATEGY_ID,
        "mode": "primary",
        "uses_kicad_capability": False,
        "uses_external_project": False,
        "status": "active",
    }


def convert(
    input_path: Path,
    mapping_path: Path,
    output_root: Path | None = None,
) -> ConversionPayload:
    if not is_native_altium_path(input_path):
        raise ValueError("custom strategy only supports native Altium .SchDoc input")
    if input_path.suffix.lower() == ".pcbdoc":
        raise ValueError("custom strategy does not yet emit KiCad PCB from native .PcbDoc")
    native_root = resolve_strategy_work_root("custom-native", output_root)
    project = parse_native_schematic_project(input_path, native_root)
    resolved_symbols = {
        component.designator: resolve_symbol(component, mapping_path).library_id
        for component in project.sheets[0].components
    }
    report = validate_project(project)
    report["strategy"] = get_strategy_metadata()
    return {
        "project_name": project.name,
        "schematic_text": render_kicad_schematic(project, resolved_symbols),
        "schematic_extension": ".kicad_sch",
        "board_text": None,
        "board_extension": None,
        "auxiliary_text_artifacts": {},
        "report": report,
    }

from pathlib import Path

from eda2kicad.altium_ascii.parser import parse_ascii_schematic
from eda2kicad.core.ir import ComponentInstance
from eda2kicad.kicad.writer import render_kicad_schematic
from eda2kicad.normalize.transform import parsed_records_to_project
from eda2kicad.symbols.resolver import resolve_symbol
from eda2kicad.strategies.base import ConversionPayload, StrategyMetadata
from eda2kicad.validation.checks import validate_project


def resolve_with_local_map(component: ComponentInstance, mapping_path: Path) -> str:
    return resolve_symbol(component, mapping_path).library_id


def resolve_with_kicad_official(component: ComponentInstance, mapping_path: Path) -> str:
    del mapping_path
    if component.library_key.startswith("RES_"):
        return "Device:R"
    if component.library_key.startswith("CAP_"):
        return "Device:C"
    return f"Device:{component.library_key}"


def resolve_with_third_party(component: ComponentInstance, mapping_path: Path) -> str:
    del mapping_path
    return f"ThirdParty:{component.library_key}"


def run_shared_pipeline(
    input_path: Path,
    mapping_path: Path,
    strategy_metadata: StrategyMetadata,
    symbol_resolver,
) -> ConversionPayload:
    text = input_path.read_text(encoding="utf-8")
    parsed = parse_ascii_schematic(text)
    project = parsed_records_to_project(input_path.stem, parsed)
    resolved_symbols = {
        component.designator: symbol_resolver(component, mapping_path)
        for component in project.sheets[0].components
    }
    report = validate_project(project)
    report["strategy"] = strategy_metadata
    return {
        "project_name": project.name,
        "schematic_text": render_kicad_schematic(project, resolved_symbols),
        "schematic_extension": ".kicad_sch",
        "board_text": None,
        "board_extension": None,
        "auxiliary_text_artifacts": {},
        "report": report,
    }

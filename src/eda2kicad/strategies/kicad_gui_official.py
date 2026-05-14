from pathlib import Path

from eda2kicad.gui.bundle_import import run_combined_gui_import
from eda2kicad.gui.pcb_import import run_pcb_gui_import
from eda2kicad.gui.schematic_import import run_schematic_gui_import
from eda2kicad.strategies.base import ConversionPayload, StrategyMetadata, resolve_strategy_work_root
from eda2kicad.strategies.tooling import KICAD_GUI_PATH

STRATEGY_ID = "kicad-gui-official"


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
    del mapping_path
    if input_path.suffix.lower() == ".schdoc":
        if output_root is None:
            return convert_native_schematic(input_path)
        return convert_native_schematic(input_path, output_root=output_root)
    if input_path.suffix.lower() in {".pcbdoc", ".prjpcb"}:
        if output_root is None:
            return convert_native_pcb(input_path)
        return convert_native_pcb(input_path, output_root=output_root)
    raise ValueError("kicad-gui-official strategy currently supports .SchDoc, .PcbDoc and .PrjPcb input")


def _resolve_gui_import_input(input_path: Path) -> Path:
    if input_path.suffix.lower() == ".prjpcb":
        return input_path
    sibling_projects = sorted(
        candidate
        for candidate in input_path.parent.glob("*.PrjPcb")
    ) + sorted(
        candidate
        for candidate in input_path.parent.glob("*.PrjPCB")
    )
    unique_projects: list[Path] = []
    seen: set[str] = set()
    for candidate in sibling_projects:
        normalized = str(candidate.resolve()).lower()
        if normalized in seen:
            continue
        seen.add(normalized)
        unique_projects.append(candidate)
    if len(unique_projects) == 1:
        return unique_projects[0]
    raise ValueError(
        "kicad-gui-official currently needs an Altium .PrjPcb project for real GUI import; "
        "please provide the .PrjPcb file directly, or keep exactly one sibling .PrjPcb next to the .PcbDoc"
    )


def convert_native_pcb(input_path: Path, *, output_root: Path | None = None) -> ConversionPayload:
    if not KICAD_GUI_PATH.exists():
        raise ValueError(f"missing kicad gui: {KICAD_GUI_PATH}")
    gui_output_root = resolve_strategy_work_root("kicad-gui-official", output_root)
    result = run_pcb_gui_import(
        input_path,
        gui_output_root,
        kicad_exe=KICAD_GUI_PATH,
    )
    board_path = Path(result["board_path"])
    board_text = board_path.read_text(encoding="utf-8")
    auxiliary_text_artifacts: dict[str, str] = {}

    project_path_value = result.get("project_path")
    if project_path_value:
        project_path = Path(project_path_value)
        if project_path.exists():
            auxiliary_text_artifacts[project_path.name] = project_path.read_text(encoding="utf-8")

    report = dict(result["report"])
    report["strategy"] = get_strategy_metadata()
    return {
        "project_name": str(result["project_name"]),
        "schematic_text": None,
        "schematic_extension": None,
        "board_text": board_text,
        "board_extension": ".kicad_pcb",
        "auxiliary_text_artifacts": auxiliary_text_artifacts,
        "report": report,
    }


def convert_native_schematic(input_path: Path, *, output_root: Path | None = None) -> ConversionPayload:
    if not KICAD_GUI_PATH.exists():
        raise ValueError(f"missing kicad gui: {KICAD_GUI_PATH}")
    gui_output_root = resolve_strategy_work_root("kicad-gui-official", output_root)
    result = run_schematic_gui_import(
        input_path,
        gui_output_root,
        kicad_exe=KICAD_GUI_PATH,
    )
    schematic_path = Path(result["schematic_path"])
    schematic_text = schematic_path.read_text(encoding="utf-8")
    auxiliary_text_artifacts: dict[str, str] = {}

    project_path_value = result.get("project_path")
    if project_path_value:
        project_path = Path(project_path_value)
        if project_path.exists():
            auxiliary_text_artifacts[project_path.name] = project_path.read_text(encoding="utf-8")

    report = dict(result["report"])
    report["strategy"] = get_strategy_metadata()
    return {
        "project_name": str(result["project_name"]),
        "schematic_text": schematic_text,
        "schematic_extension": ".kicad_sch",
        "board_text": None,
        "board_extension": None,
        "auxiliary_text_artifacts": auxiliary_text_artifacts,
        "report": report,
    }


def convert_native_bundle(
    *,
    pcb_input: Path | None,
    schematic_input: Path | None,
    project_input: Path | None = None,
    output_root: Path | None = None,
) -> ConversionPayload:
    if not KICAD_GUI_PATH.exists():
        raise ValueError(f"missing kicad gui: {KICAD_GUI_PATH}")
    gui_output_root = resolve_strategy_work_root("kicad-gui-official", output_root)
    result = run_combined_gui_import(
        pcb_input=pcb_input,
        schematic_input=schematic_input,
        project_input=project_input,
        output_root=gui_output_root,
        kicad_exe=KICAD_GUI_PATH,
    )

    board_path = Path(result["board_path"]) if result.get("board_path") else None
    schematic_path = Path(result["schematic_path"]) if result.get("schematic_path") else None
    project_path = Path(result["project_path"])
    auxiliary_text_artifacts = {}
    if project_path.exists():
        auxiliary_text_artifacts[project_path.name] = project_path.read_text(encoding="utf-8")

    report = dict(result["report"])
    report["strategy"] = get_strategy_metadata()
    return {
        "project_name": str(result["project_name"]),
        "schematic_text": schematic_path.read_text(encoding="utf-8") if schematic_path is not None else None,
        "schematic_extension": ".kicad_sch" if schematic_path is not None else None,
        "board_text": board_path.read_text(encoding="utf-8") if board_path is not None else None,
        "board_extension": ".kicad_pcb" if board_path is not None else None,
        "auxiliary_text_artifacts": auxiliary_text_artifacts,
        "report": report,
    }

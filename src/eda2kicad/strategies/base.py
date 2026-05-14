from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import TypedDict


class StrategyMetadata(TypedDict):
    strategy_id: str
    mode: str
    status: str
    uses_kicad_capability: bool
    uses_external_project: bool


class ConversionPayload(TypedDict):
    project_name: str
    schematic_text: str | None
    schematic_extension: str | None
    board_text: str | None
    board_extension: str | None
    auxiliary_text_artifacts: dict[str, str]
    report: dict


StrategyRunner = Callable[[Path, Path, Path | None], ConversionPayload]
SymbolResolver = Callable[[object, Path], str]


def resolve_strategy_work_root(work_dir_name: str, requested_output_dir: Path | None) -> Path:
    if requested_output_dir is not None:
        root = Path(requested_output_dir) / ".eda2kicad" / work_dir_name
    else:
        workspace_root = Path(__file__).resolve().parents[3]
        root = workspace_root / "outputs" / work_dir_name
    root.mkdir(parents=True, exist_ok=True)
    return root


@dataclass(slots=True)
class StrategyResult:
    strategy_id: str
    succeeded: bool
    report_summary: dict
    quality_signals: dict

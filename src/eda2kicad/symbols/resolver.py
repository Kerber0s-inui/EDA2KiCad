import json
from dataclasses import dataclass
from pathlib import Path

from eda2kicad.core.ir import ComponentInstance


@dataclass(slots=True)
class SymbolResolutionResult:
    library_id: str
    source: str
    needs_private_symbol: bool


def resolve_symbol(component: ComponentInstance, mapping_path: Path) -> SymbolResolutionResult:
    mapping = json.loads(mapping_path.read_text(encoding="utf-8"))
    if component.library_key in mapping:
        return SymbolResolutionResult(
            library_id=mapping[component.library_key],
            source="local-map",
            needs_private_symbol=False,
        )
    return SymbolResolutionResult(
        library_id=f"Generated:{component.library_key}",
        source="private-symbol",
        needs_private_symbol=True,
    )

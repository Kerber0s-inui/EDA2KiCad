from pathlib import Path

from eda2kicad.core.ir import ComponentInstance
from eda2kicad.symbols.resolver import SymbolResolutionResult, resolve_symbol
from eda2kicad.strategies.runtime import (
    resolve_with_kicad_official,
    resolve_with_third_party,
)


def test_resolver_prefers_local_library() -> None:
    component = ComponentInstance(
        designator="R1",
        library_key="RES_0603",
        value="10k",
        footprint="Resistor_SMD:R_0603_1608Metric",
    )

    result = resolve_symbol(
        component,
        Path(__file__).resolve().parents[2] / "libraries" / "local_symbol_map.json",
    )

    assert isinstance(result, SymbolResolutionResult)
    assert result.library_id == "CompanyLib:RES_0603"
    assert result.source == "local-map"
    assert result.needs_private_symbol is False


def test_resolver_generates_private_symbol_when_mapping_missing() -> None:
    component = ComponentInstance(
        designator="L1",
        library_key="IND_0805",
        value="1uH",
        footprint="Inductor_SMD:L_0805_2012Metric",
    )

    result = resolve_symbol(
        component,
        Path(__file__).resolve().parents[2] / "libraries" / "local_symbol_map.json",
    )

    assert isinstance(result, SymbolResolutionResult)
    assert result.source == "private-symbol"
    assert result.needs_private_symbol is True
    assert result.library_id.startswith("Generated:")


def test_kicad_official_strategy_maps_common_resistor_to_device_library() -> None:
    component = ComponentInstance(
        designator="R1",
        library_key="RES_0603",
        value="10k",
        footprint="Resistor_SMD:R_0603_1608Metric",
    )

    result = resolve_with_kicad_official(component, Path("unused.json"))

    assert result == "Device:R"


def test_third_party_strategy_preserves_library_key_namespace() -> None:
    component = ComponentInstance(
        designator="R1",
        library_key="RES_0603",
        value="10k",
        footprint="Resistor_SMD:R_0603_1608Metric",
    )

    result = resolve_with_third_party(component, Path("unused.json"))

    assert result == "ThirdParty:RES_0603"

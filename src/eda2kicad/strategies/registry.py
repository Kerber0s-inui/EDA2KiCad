from eda2kicad.strategies import custom_pipeline, kicad_gui_official, kicad_official, pcbnew_api, third_party
from eda2kicad.strategies.base import StrategyMetadata, StrategyRunner

STRATEGIES: dict[str, tuple[StrategyMetadata, StrategyRunner]] = {
    custom_pipeline.STRATEGY_ID: (
        custom_pipeline.get_strategy_metadata(),
        custom_pipeline.convert,
    ),
    kicad_official.STRATEGY_ID: (
        kicad_official.get_strategy_metadata(),
        kicad_official.convert,
    ),
    pcbnew_api.STRATEGY_ID: (
        pcbnew_api.get_strategy_metadata(),
        pcbnew_api.convert,
    ),
    kicad_gui_official.STRATEGY_ID: (
        kicad_gui_official.get_strategy_metadata(),
        kicad_gui_official.convert,
    ),
    third_party.STRATEGY_ID: (
        third_party.get_strategy_metadata(),
        third_party.convert,
    ),
}

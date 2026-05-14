from eda2kicad.strategies.base import StrategyResult


def compare_results(results: list[StrategyResult]) -> dict:
    return {
        "strategies": [result.strategy_id for result in results],
        "success_count": sum(result.succeeded for result in results),
        "net_label_pass_count": sum(
            bool(result.quality_signals.get("net_label_ok")) for result in results
        ),
    }

from eda2kicad.strategies.base import StrategyResult
from eda2kicad.strategies.compare import compare_results


def test_compare_results_summarizes_success_and_quality_signals() -> None:
    results = [
        StrategyResult(
            strategy_id="local-map",
            succeeded=True,
            report_summary={"error_count": 0},
            quality_signals={"net_label_ok": True},
        ),
        StrategyResult(
            strategy_id="private-symbol",
            succeeded=False,
            report_summary={"error_count": 1},
            quality_signals={"net_label_ok": False},
        ),
        StrategyResult(
            strategy_id="fallback",
            succeeded=True,
            report_summary={"error_count": 0},
            quality_signals={},
        ),
    ]

    summary = compare_results(results)

    assert summary == {
        "strategies": ["local-map", "private-symbol", "fallback"],
        "success_count": 2,
        "net_label_pass_count": 1,
    }

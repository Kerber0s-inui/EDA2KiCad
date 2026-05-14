from eda2kicad.strategies.base import StrategyResult
from eda2kicad.strategies.compare import compare_results
from eda2kicad.strategies.custom_pipeline import STRATEGY_ID


def test_custom_pipeline_strategy_id_is_custom() -> None:
    assert STRATEGY_ID == "custom"


def test_compare_results_summarizes_three_strategies() -> None:
    results = [
        StrategyResult(
            "custom",
            True,
            {"error_count": 0, "warning_count": 1},
            {"net_label_ok": True},
        ),
        StrategyResult(
            "kicad-official",
            True,
            {"error_count": 0, "warning_count": 0},
            {"net_label_ok": True},
        ),
        StrategyResult(
            "third-party",
            False,
            {"error_count": 1, "warning_count": 0},
            {"net_label_ok": False},
        ),
    ]

    summary = compare_results(results)

    assert summary["strategies"] == ["custom", "kicad-official", "third-party"]
    assert summary["success_count"] == 2
    assert summary["net_label_pass_count"] == 2


def test_kicad_official_strategy_exposes_metadata() -> None:
    from eda2kicad.strategies.kicad_official import get_strategy_metadata

    metadata = get_strategy_metadata()

    assert metadata["strategy_id"] == "kicad-official"
    assert metadata["mode"] == "candidate"
    assert metadata["uses_kicad_capability"] is True


def test_third_party_strategy_exposes_metadata() -> None:
    from eda2kicad.strategies.third_party import get_strategy_metadata

    metadata = get_strategy_metadata()

    assert metadata["strategy_id"] == "third-party"
    assert metadata["mode"] == "candidate"
    assert metadata["uses_external_project"] is True


def test_pcbnew_api_strategy_exposes_metadata() -> None:
    from eda2kicad.strategies.pcbnew_api import get_strategy_metadata

    metadata = get_strategy_metadata()

    assert metadata["strategy_id"] == "pcbnew-api"
    assert metadata["mode"] == "candidate"
    assert metadata["uses_kicad_capability"] is True


def test_candidate_strategies_are_not_stubbed_metadata_only() -> None:
    from eda2kicad.strategies.kicad_official import get_strategy_metadata as official_metadata
    from eda2kicad.strategies.pcbnew_api import get_strategy_metadata as pcbnew_api_metadata
    from eda2kicad.strategies.third_party import get_strategy_metadata as third_party_metadata

    assert official_metadata()["status"] == "active"
    assert pcbnew_api_metadata()["status"] == "active"
    assert third_party_metadata()["status"] == "active"

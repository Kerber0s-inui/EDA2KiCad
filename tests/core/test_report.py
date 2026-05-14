from eda2kicad.core.report import ConversionIssue, ConversionReport


def test_report_serializes_conversion_issues() -> None:
    report = ConversionReport()
    report.add_issue(
        ConversionIssue(
            severity="error",
            code="net_label_mismatch",
            message="NET_A label was not emitted at the expected coordinate",
        )
    )

    payload = report.to_dict()

    assert payload["summary"]["error_count"] == 1
    assert payload["summary"]["warning_count"] == 0
    assert len(payload["issues"]) == 1
    assert payload["issues"][0]["code"] == "net_label_mismatch"
    assert payload["issues"][0]["severity"] == "error"
    assert payload["issues"][0]["message"] == "NET_A label was not emitted at the expected coordinate"


def test_report_counts_warning_issues() -> None:
    report = ConversionReport()
    report.add_issue(
        ConversionIssue(
            severity="warning",
            code="missing_footprint",
            message="Footprint was not mapped for R1",
        )
    )

    payload = report.to_dict()

    assert payload["summary"]["warning_count"] == 1


def test_conversion_issue_rejects_invalid_severity() -> None:
    try:
        ConversionIssue(severity="warn", code="typo", message="bad severity")
    except ValueError as exc:
        assert "severity" in str(exc)
    else:
        raise AssertionError("ConversionIssue accepted an invalid severity")

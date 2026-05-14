from eda2kicad.core.ir import NetLabel, Project, Sheet
from eda2kicad.validation.checks import validate_project


def test_validation_rejects_missing_net_label() -> None:
    project = Project(name="demo", sheets=[Sheet(name="Sheet1", net_labels=[NetLabel("", (0, 0))])])

    report = validate_project(project)

    assert report["summary"]["error_count"] == 1
    assert report["issues"][0]["code"] == "invalid_net_label"

from eda2kicad.core.ir import Project
from eda2kicad.core.report import ConversionIssue, ConversionReport


def validate_project(project: Project) -> dict:
    report = ConversionReport()
    for sheet in project.sheets:
        for label in sheet.net_labels:
            if not label.text.strip():
                report.add_issue(
                    ConversionIssue(
                        severity="error",
                        code="invalid_net_label",
                        message="Net labels must not be empty",
                    )
                )
    return report.to_dict()

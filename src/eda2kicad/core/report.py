from dataclasses import asdict, dataclass, field


@dataclass(slots=True)
class ConversionIssue:
    severity: str
    code: str
    message: str

    def __post_init__(self) -> None:
        if self.severity not in {"error", "warning", "info"}:
            raise ValueError(f"invalid severity: {self.severity!r}")


@dataclass(slots=True)
class ConversionReport:
    issues: list[ConversionIssue] = field(default_factory=list)

    def add_issue(self, issue: ConversionIssue) -> None:
        self.issues.append(issue)

    def to_dict(self) -> dict:
        return {
            "summary": {
                "error_count": sum(issue.severity == "error" for issue in self.issues),
                "warning_count": sum(issue.severity == "warning" for issue in self.issues),
            },
            "issues": [asdict(issue) for issue in self.issues],
        }

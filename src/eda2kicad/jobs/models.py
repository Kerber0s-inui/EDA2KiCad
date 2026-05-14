from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class JobWorkspace:
    root: Path
    final_dir: Path
    temp_dir: Path
    input_dir: Path


@dataclass(frozen=True)
class PlannedInputs:
    input_mode: str
    label: str
    prjpcb: Path | None
    pcbdoc: Path | None
    schdoc: Path | None

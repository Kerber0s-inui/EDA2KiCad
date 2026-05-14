import re
from datetime import datetime
from pathlib import Path

from eda2kicad.jobs.models import JobWorkspace


def create_job_workspace(output_dir: Path, input_label: str) -> JobWorkspace:
    normalized_label = _normalize_input_label(input_label)
    root = _allocate_workspace_root(output_dir, normalized_label)
    temp_dir = root / "temp"
    input_dir = root / "input"

    temp_dir.mkdir(parents=True, exist_ok=False)
    input_dir.mkdir(parents=True, exist_ok=False)

    return JobWorkspace(
        root=root,
        final_dir=root,
        temp_dir=temp_dir,
        input_dir=input_dir,
    )


def _allocate_workspace_root(output_dir: Path, input_label: str) -> Path:
    base_name = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{input_label}"
    candidate = output_dir / base_name
    if not candidate.exists():
        return candidate

    suffix = 1
    while True:
        candidate = output_dir / f"{base_name}_{suffix:02d}"
        if not candidate.exists():
            return candidate
        suffix += 1


def _normalize_input_label(input_label: str) -> str:
    normalized = input_label.strip()
    normalized = normalized.replace("/", "_").replace("\\", "_")
    normalized = re.sub(r'[<>:"|?*]', "_", normalized)
    normalized = re.sub(r"\s+", "_", normalized)
    normalized = re.sub(r"_+", "_", normalized).strip("._ ")
    return normalized or "job"

from __future__ import annotations

from pathlib import Path


_FINAL_OUTPUT_NAMES = {
    ".kicad_pcb": "board",
    ".kicad_sch": "schematic",
    ".kicad_pro": "project",
}


def collect_final_outputs(final_dir: Path) -> dict[str, Path]:
    outputs: dict[str, Path] = {}

    for path in sorted(final_dir.rglob("*")):
        if not path.is_file():
            continue
        if _is_cache_library(path):
            path.unlink(missing_ok=True)
            continue

        artifact_kind = _FINAL_OUTPUT_NAMES.get(path.suffix.lower())
        if artifact_kind is not None:
            outputs[artifact_kind] = path

    return outputs


def _is_cache_library(path: Path) -> bool:
    return path.name.lower().endswith("-cache.lib")

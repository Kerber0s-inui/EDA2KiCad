from __future__ import annotations

import shutil
from pathlib import Path
from zipfile import ZipFile

from eda2kicad.jobs.models import PlannedInputs


_SUPPORTED_SUFFIXES = {
    ".prjpcb": "prjpcb",
    ".pcbdoc": "pcbdoc",
    ".schdoc": "schdoc",
}


def plan_job_inputs(input_path: Path, extract_root: Path) -> PlannedInputs:
    if not input_path.exists() or not input_path.is_file():
        raise ValueError(f"input file does not exist: {input_path}")
    suffix = input_path.suffix.lower()
    if suffix == ".zip":
        return _plan_zip_inputs(input_path, extract_root)
    if suffix in _SUPPORTED_SUFFIXES:
        return _plan_single_file_inputs(input_path)
    raise ValueError(f"unsupported input file: {input_path}")


def choose_job_mode(
    prjpcb: Path | None,
    pcbdoc: Path | None,
    schdoc: Path | None,
) -> str:
    if prjpcb is not None:
        return "reuse-project"
    if pcbdoc is not None and schdoc is not None:
        return "shared-empty-project"
    if pcbdoc is not None or schdoc is not None:
        return "single-empty-project"
    raise ValueError("at least one input file is required")


def _plan_single_file_inputs(input_path: Path) -> PlannedInputs:
    label = input_path.stem
    prjpcb = input_path if input_path.suffix.lower() == ".prjpcb" else None
    pcbdoc = input_path if input_path.suffix.lower() == ".pcbdoc" else None
    schdoc = input_path if input_path.suffix.lower() == ".schdoc" else None
    return PlannedInputs(
        input_mode="single-file",
        label=label,
        prjpcb=prjpcb,
        pcbdoc=pcbdoc,
        schdoc=schdoc,
    )


def _plan_zip_inputs(input_path: Path, extract_root: Path) -> PlannedInputs:
    if extract_root.exists():
        shutil.rmtree(extract_root)
    extract_root.mkdir(parents=True, exist_ok=True)
    with ZipFile(input_path) as archive:
        archive.extractall(extract_root)

    candidates: dict[str, list[Path]] = {"prjpcb": [], "pcbdoc": [], "schdoc": []}
    for path in extract_root.rglob("*"):
        if not path.is_file():
            continue
        kind = _SUPPORTED_SUFFIXES.get(path.suffix.lower())
        if kind is not None:
            candidates[kind].append(path)

    planned = _choose_unique_group(candidates)
    return PlannedInputs(
        input_mode="zip-archive",
        label=planned["label"],
        prjpcb=planned["prjpcb"],
        pcbdoc=planned["pcbdoc"],
        schdoc=planned["schdoc"],
    )


def _choose_unique_group(candidates: dict[str, list[Path]]) -> dict[str, Path | None | str]:
    grouped: dict[str, dict[str, list[Path]]] = {}
    for kind, paths in candidates.items():
        for path in paths:
            grouped.setdefault(path.stem.lower(), {}).setdefault(kind, []).append(path)

    for group in grouped.values():
        for kind_paths in group.values():
            if len(kind_paths) > 1:
                raise ValueError("ambiguous zip inputs: duplicate files share the same stem")

    triplets = [
        (stem, group)
        for stem, group in grouped.items()
        if {"prjpcb", "pcbdoc", "schdoc"}.issubset(group)
    ]
    if len(triplets) == 1:
        stem, group = triplets[0]
        return {
            "label": group["prjpcb"][0].stem,
            "prjpcb": group["prjpcb"][0],
            "pcbdoc": group["pcbdoc"][0],
            "schdoc": group["schdoc"][0],
        }
    if len(triplets) > 1:
        raise ValueError("ambiguous zip inputs: multiple matching file groups found")

    if len(grouped) > 1:
        raise ValueError("ambiguous zip inputs: input files do not form one coherent file set")

    selected: dict[str, Path | None] = {}
    for kind, paths in candidates.items():
        if len(paths) > 1:
            raise ValueError(f"ambiguous zip inputs: multiple {kind} files found")
        selected[kind] = paths[0] if paths else None

    label_source = selected["prjpcb"] or selected["pcbdoc"] or selected["schdoc"]
    if label_source is None:
        raise ValueError("zip archive does not contain supported input files")

    return {
        "label": label_source.stem,
        "prjpcb": selected["prjpcb"],
        "pcbdoc": selected["pcbdoc"],
        "schdoc": selected["schdoc"],
    }

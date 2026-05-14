from pathlib import Path
import zipfile

import pytest

from eda2kicad.jobs.models import PlannedInputs
from eda2kicad.jobs.planner import choose_job_mode, plan_job_inputs


def _write_file(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("placeholder", encoding="utf-8")
    return path


def _write_zip(zip_path: Path, members: list[str]) -> Path:
    with zipfile.ZipFile(zip_path, "w") as archive:
        for member in members:
            archive.writestr(member, "placeholder")
    return zip_path


def test_plan_job_inputs_for_single_prjpcb_file(tmp_path: Path) -> None:
    input_path = _write_file(tmp_path / "demo.PrjPcb")

    planned = plan_job_inputs(input_path, tmp_path / "extract")

    assert planned == PlannedInputs(
        input_mode="single-file",
        label="demo",
        prjpcb=input_path,
        pcbdoc=None,
        schdoc=None,
    )


def test_plan_job_inputs_rejects_missing_single_file(tmp_path: Path) -> None:
    missing = tmp_path / "missing.PcbDoc"

    with pytest.raises(ValueError, match="does not exist"):
        plan_job_inputs(missing, tmp_path / "extract")


def test_plan_job_inputs_for_zip_with_matching_triplet(tmp_path: Path) -> None:
    archive_path = _write_zip(
        tmp_path / "bundle.zip",
        [
            "nested/board.PrjPcb",
            "nested/board.PcbDoc",
            "nested/board.SchDoc",
        ],
    )

    planned = plan_job_inputs(archive_path, tmp_path / "extract")

    assert planned.input_mode == "zip-archive"
    assert planned.label == "board"
    assert planned.prjpcb == tmp_path / "extract" / "nested" / "board.PrjPcb"
    assert planned.pcbdoc == tmp_path / "extract" / "nested" / "board.PcbDoc"
    assert planned.schdoc == tmp_path / "extract" / "nested" / "board.SchDoc"


def test_plan_job_inputs_prefers_the_only_complete_matching_triplet_in_zip(
    tmp_path: Path,
) -> None:
    archive_path = _write_zip(
        tmp_path / "mixed.zip",
        [
            "project/board.PrjPcb",
            "project/board.PcbDoc",
            "project/board.SchDoc",
            "extras/other.PcbDoc",
            "extras/another.SchDoc",
        ],
    )

    planned = plan_job_inputs(archive_path, tmp_path / "extract")

    assert planned == PlannedInputs(
        input_mode="zip-archive",
        label="board",
        prjpcb=tmp_path / "extract" / "project" / "board.PrjPcb",
        pcbdoc=tmp_path / "extract" / "project" / "board.PcbDoc",
        schdoc=tmp_path / "extract" / "project" / "board.SchDoc",
    )


def test_plan_job_inputs_rejects_ambiguous_zip_candidates(tmp_path: Path) -> None:
    archive_path = _write_zip(
        tmp_path / "ambiguous.zip",
        [
            "first/alpha.PcbDoc",
            "second/beta.PcbDoc",
        ],
    )

    with pytest.raises(ValueError, match="ambiguous"):
        plan_job_inputs(archive_path, tmp_path / "extract")


def test_plan_job_inputs_clears_stale_extract_root_before_scanning(tmp_path: Path) -> None:
    extract_root = tmp_path / "extract"
    _write_file(extract_root / "stale" / "ghost.PcbDoc")
    archive_path = _write_zip(
        tmp_path / "bundle.zip",
        [
            "nested/board.PrjPcb",
            "nested/board.PcbDoc",
            "nested/board.SchDoc",
        ],
    )

    planned = plan_job_inputs(archive_path, extract_root)

    assert planned.label == "board"
    assert not (extract_root / "stale").exists()


def test_plan_job_inputs_rejects_duplicate_kind_with_same_stem_in_zip(tmp_path: Path) -> None:
    archive_path = _write_zip(
        tmp_path / "duplicate.zip",
        [
            "one/board.PcbDoc",
            "two/board.PcbDoc",
            "three/board.SchDoc",
        ],
    )

    with pytest.raises(ValueError, match="ambiguous"):
        plan_job_inputs(archive_path, tmp_path / "extract")


def test_plan_job_inputs_rejects_duplicate_kind_in_complete_triplet_zip(
    tmp_path: Path,
) -> None:
    archive_path = _write_zip(
        tmp_path / "duplicate-triplet.zip",
        [
            "one/board.PrjPcb",
            "one/board.PcbDoc",
            "one/board.SchDoc",
            "two/board.PcbDoc",
        ],
    )

    with pytest.raises(ValueError, match="ambiguous"):
        plan_job_inputs(archive_path, tmp_path / "extract")


def test_plan_job_inputs_rejects_mixed_stem_partial_bundle(tmp_path: Path) -> None:
    archive_path = _write_zip(
        tmp_path / "mixed-partial.zip",
        [
            "project/board.PrjPcb",
            "other/another.PcbDoc",
        ],
    )

    with pytest.raises(ValueError, match="coherent file set"):
        plan_job_inputs(archive_path, tmp_path / "extract")


@pytest.mark.parametrize(
    ("prjpcb", "pcbdoc", "schdoc", "expected"),
    [
        (Path("demo.PrjPcb"), None, None, "reuse-project"),
        (None, Path("board.PcbDoc"), Path("board.SchDoc"), "shared-empty-project"),
        (None, Path("board.PcbDoc"), None, "single-empty-project"),
        (None, None, Path("board.SchDoc"), "single-empty-project"),
    ],
)
def test_choose_job_mode(
    prjpcb: Path | None,
    pcbdoc: Path | None,
    schdoc: Path | None,
    expected: str,
) -> None:
    assert choose_job_mode(prjpcb=prjpcb, pcbdoc=pcbdoc, schdoc=schdoc) == expected

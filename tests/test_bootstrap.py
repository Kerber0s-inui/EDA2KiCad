from pathlib import Path

from eda2kicad import __version__
from eda2kicad.paths import ensure_output_dir


def test_package_exposes_version_and_output_dir(tmp_path: Path) -> None:
    assert __version__ == "0.1.0"

    output_dir = ensure_output_dir(tmp_path / "artifacts")

    assert output_dir.exists()
    assert output_dir.is_dir()

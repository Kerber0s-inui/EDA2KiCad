from pathlib import Path

import pytest

from eda2kicad.service import ConversionService


REPO_ROOT = Path(__file__).resolve().parents[2]
SYMBOL_MAP_PATH = REPO_ROOT / "libraries" / "local_symbol_map.json"


def test_ascii_demo_input_is_rejected(tmp_path: Path) -> None:
    input_path = REPO_ROOT / "tests" / "fixtures" / "altium_ascii" / "minimal_ascii_schematic.txt"
    service = ConversionService(mapping_path=SYMBOL_MAP_PATH)

    with pytest.raises(ValueError, match="only native Altium inputs are supported"):
        service.convert_file(input_path=input_path, output_dir=tmp_path)

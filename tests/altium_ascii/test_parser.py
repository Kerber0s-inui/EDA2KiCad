from pathlib import Path

from eda2kicad.altium_ascii.parser import parse_ascii_schematic


def test_parse_ascii_schematic_reads_records() -> None:
    fixture = (
        Path(__file__).resolve().parents[1]
        / "fixtures"
        / "altium_ascii"
        / "minimal_ascii_schematic.txt"
    )

    parsed = parse_ascii_schematic(fixture.read_text(encoding="utf-8"))

    assert parsed["components"][0]["DESIGNATOR"] == "R1"
    assert parsed["fields"][0]["NAME"] == "Manufacturer"
    assert parsed["wires"][0]["X2"] == "100"
    assert parsed["net_labels"][0]["TEXT"] == "NET_A"

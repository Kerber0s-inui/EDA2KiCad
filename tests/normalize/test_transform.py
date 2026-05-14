from eda2kicad.altium_ascii.parser import parse_ascii_schematic
from eda2kicad.normalize.transform import parsed_records_to_project


ASCII_TEXT = """\
RECORD=COMPONENT
DESIGNATOR=R1
LIBRARY=RES_0603
VALUE=10k
FOOTPRINT=Resistor_SMD:R_0603_1608Metric

RECORD=COMPONENT
DESIGNATOR=C1
LIBRARY=CAP_0603
VALUE=100n
FOOTPRINT=Capacitor_SMD:C_0603_1608Metric

RECORD=FIELD
OWNER=R1
NAME=Manufacturer
VALUE=Yageo

RECORD=FIELD
OWNER=C1
NAME=Voltage
VALUE=16V

RECORD=WIRE
X1=0
Y1=0
X2=100
Y2=0

RECORD=NET_LABEL
TEXT=NET_A
X=100
Y=0
"""


def test_transform_builds_single_sheet_project() -> None:
    parsed = parse_ascii_schematic(ASCII_TEXT)

    project = parsed_records_to_project("demo", parsed)

    assert project.name == "demo"
    assert len(project.sheets) == 1

    sheet = project.sheets[0]
    assert sheet.name == "Sheet1"

    resistor = sheet.components[0]
    assert resistor.designator == "R1"
    assert resistor.library_key == "RES_0603"
    assert resistor.value == "10k"
    assert resistor.footprint == "Resistor_SMD:R_0603_1608Metric"
    assert len(resistor.fields) == 1
    assert resistor.fields[0].name == "Manufacturer"
    assert resistor.fields[0].value == "Yageo"

    capacitor = sheet.components[1]
    assert capacitor.designator == "C1"
    assert capacitor.library_key == "CAP_0603"
    assert capacitor.value == "100n"
    assert capacitor.footprint == "Capacitor_SMD:C_0603_1608Metric"
    assert len(capacitor.fields) == 1
    assert capacitor.fields[0].name == "Voltage"
    assert capacitor.fields[0].value == "16V"

    wire = sheet.wires[0]
    assert wire.start == (0, 0)
    assert wire.end == (100, 0)

    net_label = sheet.net_labels[0]
    assert net_label.text == "NET_A"
    assert net_label.position == (100, 0)

from eda2kicad.core.ir import ComponentInstance, NetLabel, Project, Sheet, WireSegment
from eda2kicad.kicad.writer import render_kicad_schematic


def test_writer_emits_components_wires_and_labels() -> None:
    project = Project(
        name="demo",
        sheets=[
            Sheet(
                name="Sheet1",
                components=[
                    ComponentInstance(
                        designator="R1",
                        library_key="RES_0603",
                        value="10k",
                        footprint="Resistor_SMD:R_0603_1608Metric",
                    )
                ],
                wires=[WireSegment((0, 0), (100, 0))],
                net_labels=[NetLabel("NET_A", (100, 0))],
            )
        ],
    )

    output = render_kicad_schematic(project, {"R1": "CompanyLib:RES_0603"})

    assert "(symbol" in output
    assert "(wire" in output
    assert "(label" in output
    assert "CompanyLib:RES_0603" in output
    assert "R1" in output
    assert "NET_A" in output

from eda2kicad.core.ir import ComponentInstance, Field, NetLabel, Project, Sheet, WireSegment


def test_project_keeps_confirmed_engineering_fields() -> None:
    project = Project(
        name="demo",
        sheets=[
            Sheet(
                name="Main",
                components=[
                    ComponentInstance(
                        designator="R1",
                        library_key="RES_0603",
                        value="10k",
                        footprint="Resistor_SMD:R_0603_1608Metric",
                        fields=[
                            Field("Part Number", "RC0603FR-0710KL"),
                            Field("Manufacturer", "Yageo"),
                            Field("Supplier", "LCSC"),
                        ],
                    )
                ],
                wires=[WireSegment((0, 0), (100, 0))],
                net_labels=[NetLabel("NET_A", (100, 0))],
            )
        ],
    )

    component = project.sheets[0].components[0]
    sheet = project.sheets[0]

    assert project.name == "demo"
    assert project.sheets == [sheet]
    assert sheet.name == "Main"
    assert sheet.components == [component]
    assert sheet.wires == [WireSegment((0, 0), (100, 0))]
    assert sheet.net_labels == [NetLabel("NET_A", (100, 0))]
    assert component.designator == "R1"
    assert component.library_key == "RES_0603"
    assert component.value == "10k"
    assert component.footprint.endswith("0603_1608Metric")
    assert [field.value for field in component.fields] == [
        "RC0603FR-0710KL",
        "Yageo",
        "LCSC",
    ]
    assert [field.name for field in component.fields] == [
        "Part Number",
        "Manufacturer",
        "Supplier",
    ]

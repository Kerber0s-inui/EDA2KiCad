from eda2kicad.core.ir import ComponentInstance, Field, NetLabel, Project, Sheet, WireSegment


def parsed_records_to_project(name: str, parsed: dict[str, list[dict[str, str]]]) -> Project:
    component_fields: dict[str, list[Field]] = {}
    for field_record in parsed["fields"]:
        owner = field_record["OWNER"]
        component_fields.setdefault(owner, []).append(Field(field_record["NAME"], field_record["VALUE"]))

    components = [
        ComponentInstance(
            designator=record["DESIGNATOR"],
            library_key=record["LIBRARY"],
            value=record["VALUE"],
            footprint=record["FOOTPRINT"],
            fields=component_fields.get(record["DESIGNATOR"], []),
        )
        for record in parsed["components"]
    ]
    wires = [
        WireSegment(
            (int(record["X1"]), int(record["Y1"])),
            (int(record["X2"]), int(record["Y2"])),
        )
        for record in parsed["wires"]
    ]
    net_labels = [
        NetLabel(record["TEXT"], (int(record["X"]), int(record["Y"])))
        for record in parsed["net_labels"]
    ]
    return Project(name=name, sheets=[Sheet(name="Sheet1", components=components, wires=wires, net_labels=net_labels)])

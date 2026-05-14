from eda2kicad.core.ir import Project


def render_kicad_schematic(project: Project, resolved_symbols: dict[str, str]) -> str:
    lines = ["(kicad_sch (version 20231120) (generator eda2kicad)"]
    for sheet in project.sheets:
        for component in sheet.components:
            library_id = resolved_symbols[component.designator]
            lines.append(
                f'  (symbol (lib_id "{library_id}") (property "Reference" "{component.designator}") (property "Value" "{component.value}"))'
            )
        for wire in sheet.wires:
            lines.append(f"  (wire (pts (xy {wire.start[0]} {wire.start[1]}) (xy {wire.end[0]} {wire.end[1]})))")
        for label in sheet.net_labels:
            lines.append(f'  (label "{label.text}" (at {label.position[0]} {label.position[1]} 0))')
    lines.append(")")
    return "\n".join(lines)

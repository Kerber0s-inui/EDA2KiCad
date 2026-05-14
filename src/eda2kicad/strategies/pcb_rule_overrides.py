from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


_FLOAT = r"-?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?"
_SETUP_FIELDS = {
    "trace_clearance": "trace_clearance",
    "trace_min": "trace_min",
    "zone_clearance": "zone_clearance",
    "via_size": "via_size",
    "via_drill": "via_drill",
    "via_min_size": "via_min_size",
    "via_min_drill": "via_min_drill",
    "uvia_size": "uvia_size",
    "uvia_drill": "uvia_drill",
    "uvia_min_size": "uvia_min_size",
    "uvia_min_drill": "uvia_min_drill",
}
_NET_CLASS_FIELDS = {
    "clearance": "clearance",
    "trace_width": "trace_width",
    "via_dia": "via_dia",
    "via_drill": "via_drill",
    "uvia_dia": "uvia_dia",
    "uvia_drill": "uvia_drill",
    "diff_pair_gap": "diff_pair_gap",
    "diff_pair_width": "diff_pair_width",
}


def extract_board_rule_overrides(board_text: str) -> dict[str, Any]:
    setup = _extract_setup_values(board_text)
    net_classes = _extract_net_classes(board_text)
    return {
        "source": "third-party-board-postprocess",
        "board": setup,
        "net_classes": net_classes,
    }


def extract_native_board_rule_overrides(native_board_root: Path) -> dict[str, Any]:
    rules_text = _read_native_rule_file(native_board_root, "Rules6")
    classes_text = _read_native_rule_file(native_board_root, "Classes6")
    rules_records = _parse_native_records(rules_text) if rules_text else []
    board = _extract_native_board_setup(rules_records)
    board.update(_extract_native_zone_rules(rules_records))
    net_classes = _extract_native_net_classes(classes_text, rules_records) if classes_text else []
    return {
        "source": "third-party-native-rules",
        "board": board,
        "net_classes": net_classes,
    }


def apply_board_rule_overrides(board_text: str, board_overrides: dict[str, Any]) -> str:
    override_board = board_overrides.get("board") or {}
    override_classes = board_overrides.get("net_classes") or []
    if not override_board and not override_classes:
        return board_text

    current = extract_board_rule_overrides(board_text)
    merged_board = {**current["board"], **override_board}
    merged_classes = override_classes or current["net_classes"]

    rewritten = _rewrite_board_setup_values(board_text, merged_board)
    rewritten = _rewrite_zone_sections(rewritten, merged_board)
    if override_classes:
        rewritten = _replace_net_class_section(rewritten, merged_classes, merged_board)
    return rewritten


def build_kicad_project_text(project_name: str, board_overrides: dict[str, Any]) -> str:
    net_classes = board_overrides.get("net_classes") or []
    if not net_classes:
        net_classes = [_default_net_class(board_overrides.get("board", {}))]

    payload = {
        "board": {
            "design_settings": {
                "defaults": {
                    "board_outline_line_width": 0.1,
                    "copper_line_width": 0.2,
                    "copper_text_size_h": 1.5,
                    "copper_text_size_v": 1.5,
                    "copper_text_thickness": 0.3,
                    "other_line_width": 0.15,
                    "silk_line_width": 0.15,
                    "silk_text_size_h": 1.0,
                    "silk_text_size_v": 1.0,
                    "silk_text_thickness": 0.15,
                },
                "diff_pair_dimensions": [],
                "drc_exclusions": [],
                "rules": {
                    "min_copper_edge_clearance": board_overrides.get("board", {}).get(
                        "board_outline_clearance",
                        0.0,
                    ),
                    "solder_mask_clearance": 0.0,
                    "solder_mask_min_width": 0.0,
                },
                "track_widths": [],
                "via_dimensions": [],
            },
            "layer_presets": [],
        },
        "boards": [],
        "cvpcb": {
            "equivalence_files": [],
        },
        "libraries": {
            "pinned_footprint_libs": [],
            "pinned_symbol_libs": [],
        },
        "meta": {
            "filename": f"{project_name}.kicad_pro",
            "version": 1,
        },
        "net_settings": {
            "classes": [
                _project_net_class(class_data, board_overrides.get("board", {}))
                for class_data in net_classes
            ],
            "meta": {
                "version": 2,
            },
            "net_colors": None,
        },
        "pcbnew": {
            "last_paths": {
                "gencad": "",
                "idf": "",
                "netlist": "",
                "specctra_dsn": "",
                "step": "",
                "vrml": "",
            },
            "page_layout_descr_file": "",
        },
        "schematic": {
            "legacy_lib_dir": "",
            "legacy_lib_list": [],
        },
        "sheets": [],
        "text_variables": {},
    }
    return json.dumps(payload, indent=2, ensure_ascii=False) + "\n"


def _read_native_rule_file(native_board_root: Path, subdirectory: str) -> str:
    data_path = native_board_root / "Root Entry" / subdirectory / "Data.dat.txt"
    if not data_path.exists():
        return ""
    return data_path.read_text(encoding="utf-8", errors="replace")


def _parse_native_records(text: str) -> list[dict[str, str]]:
    records: list[dict[str, str]] = []
    for line in text.splitlines():
        if not line.startswith("Pos:"):
            continue
        record: dict[str, str] = {}
        for segment in line.split("|"):
            if "=" not in segment:
                continue
            key, value = segment.split("=", 1)
            key = key.strip()
            value = value.strip()
            if not key or key.startswith("Pos:"):
                continue
            record[key] = value
        if record:
            records.append(record)
    return records


def _extract_native_board_setup(records: list[dict[str, str]]) -> dict[str, float]:
    board: dict[str, float] = {}
    clearance_rule = _find_native_rule(records, "Clearance")
    if clearance_rule:
        clearance = _measure_to_mm(clearance_rule.get("GAP") or clearance_rule.get("GENERICCLEARANCE"))
        if clearance is not None:
            board["trace_clearance"] = clearance
    width_rule = _find_native_rule(records, "Width")
    if width_rule:
        trace_min = _measure_to_mm(width_rule.get("MINLIMIT") or width_rule.get("PREFEREDWIDTH"))
        if trace_min is not None:
            board["trace_min"] = trace_min
    vias_rule = _find_native_rule(records, "RoutingVias")
    if vias_rule:
        via_size = _measure_to_mm(vias_rule.get("WIDTH") or vias_rule.get("MAXWIDTH"))
        via_drill = _measure_to_mm(vias_rule.get("HOLEWIDTH") or vias_rule.get("MINHOLEWIDTH"))
        via_min_size = _measure_to_mm(vias_rule.get("MINWIDTH")) or via_size
        via_min_drill = _measure_to_mm(vias_rule.get("MINHOLEWIDTH")) or via_drill
        uvia_size = _measure_to_mm(vias_rule.get("UVIASIZE"))
        uvia_drill = _measure_to_mm(vias_rule.get("UVIAHOLEWIDTH"))
        if via_size is not None:
            board["via_size"] = via_size
        if via_drill is not None:
            board["via_drill"] = via_drill
        if via_min_size is not None:
            board["via_min_size"] = via_min_size
        if via_min_drill is not None:
            board["via_min_drill"] = via_min_drill
        if uvia_size is not None:
            board["uvia_size"] = uvia_size
            board["uvia_min_size"] = uvia_size
        if uvia_drill is not None:
            board["uvia_drill"] = uvia_drill
            board["uvia_min_drill"] = uvia_drill
    return board


def _extract_native_zone_rules(records: list[dict[str, str]]) -> dict[str, Any]:
    board: dict[str, Any] = {}
    board_outline_rule = _find_native_rule(records, "BoardOutlineClearance")
    if board_outline_rule:
        board_outline_clearance = _measure_to_mm(
            board_outline_rule.get("GAP") or board_outline_rule.get("GENERICCLEARANCE")
        )
        if board_outline_clearance is not None:
            board["board_outline_clearance"] = board_outline_clearance

    plane_clearance_rule = _find_native_rule(records, "PlaneClearance")
    if plane_clearance_rule:
        plane_clearance = _measure_to_mm(
            plane_clearance_rule.get("CLEARANCE") or plane_clearance_rule.get("GAP")
        )
        if plane_clearance is not None:
            board["zone_clearance"] = plane_clearance

    connection_rule = _find_native_rule(records, "PlaneConnect") or _find_native_rule(records, "PolygonConnect")
    if connection_rule:
        style = connection_rule.get("PLANECONNECTSTYLE") or connection_rule.get("CONNECTSTYLE")
        if style:
            board["zone_connection_style"] = style.split()[0].lower()
        thermal_gap = _measure_to_mm(
            connection_rule.get("RELIEFEXPANSION")
            or connection_rule.get("AIRGAPWIDTH")
            or connection_rule.get("RELIEFAIRGAP")
        )
        thermal_bridge_width = _measure_to_mm(connection_rule.get("RELIEFCONDUCTORWIDTH"))
        if thermal_gap is not None:
            board["zone_thermal_gap"] = thermal_gap
        if thermal_bridge_width is not None:
            board["zone_thermal_bridge_width"] = thermal_bridge_width

    if "zone_clearance" not in board:
        clearance_rule = _find_native_rule(records, "Clearance")
        fallback_clearance = _measure_to_mm(
            clearance_rule.get("GAP") or clearance_rule.get("GENERICCLEARANCE")
        ) if clearance_rule else None
        if fallback_clearance is not None:
            board["zone_clearance"] = fallback_clearance
    return board


def _extract_native_net_classes(
    classes_text: str,
    rules_records: list[dict[str, str]],
) -> list[dict[str, Any]]:
    records = _parse_native_records(classes_text)
    defaults = _extract_native_class_defaults(rules_records)
    net_classes: list[dict[str, Any]] = []
    for record in records:
        if record.get("KIND") != "0":
            continue
        nets = _extract_nets_from_native_class(record)
        if not nets:
            continue
        name = record.get("NAME", "Default")
        class_data: dict[str, Any] = {
            "name": name,
            "description": record.get("DESCRIPTION", name),
            "nets": nets,
        }
        for key, dest in _NET_CLASS_FIELDS.items():
            value = _measure_to_mm(record.get(key))
            if value is not None:
                class_data[dest] = value
        for key, value in defaults.items():
            class_data.setdefault(key, value)
        net_classes.append(class_data)
    return net_classes


def _extract_native_class_defaults(rules_records: list[dict[str, str]]) -> dict[str, float]:
    defaults: dict[str, float] = {}
    clearance_rule = _find_native_rule(rules_records, "Clearance")
    width_rule = _find_native_rule(rules_records, "Width")
    vias_rule = _find_native_rule(rules_records, "RoutingVias")
    clearance = _measure_to_mm(clearance_rule.get("GAP") or clearance_rule.get("GENERICCLEARANCE")) if clearance_rule else None
    trace_width = _measure_to_mm(width_rule.get("PREFEREDWIDTH") or width_rule.get("MINLIMIT")) if width_rule else None
    via_dia = _measure_to_mm(vias_rule.get("WIDTH") or vias_rule.get("MAXWIDTH")) if vias_rule else None
    via_drill = _measure_to_mm(vias_rule.get("HOLEWIDTH") or vias_rule.get("MINHOLEWIDTH")) if vias_rule else None
    if clearance is not None:
        defaults["clearance"] = clearance
    if trace_width is not None:
        defaults["trace_width"] = trace_width
    if via_dia is not None:
        defaults["via_dia"] = via_dia
    if via_drill is not None:
        defaults["via_drill"] = via_drill
    return defaults


def _extract_nets_from_native_class(record: dict[str, str]) -> list[str]:
    nets: list[tuple[int, str]] = []
    for key, value in record.items():
        if not re.fullmatch(r"M\d+", key):
            continue
        if not value:
            continue
        nets.append((int(key[1:]), value))
    nets.sort(key=lambda item: item[0])
    return [value for _index, value in nets]


def _find_native_rule(records: list[dict[str, str]], rule_name: str) -> dict[str, str] | None:
    for record in records:
        if record.get("RULEKIND") == rule_name or record.get("NAME") == rule_name:
            return record
    return None


def _measure_to_mm(value: str | None) -> float | None:
    if value is None:
        return None
    match = re.fullmatch(r"\s*(-?(?:\d+(?:\.\d*)?|\.\d+))\s*([A-Za-zµ]*)\s*", value)
    if not match:
        return None
    number = float(match.group(1))
    unit = match.group(2).lower()
    if unit in {"", "mm"}:
        return number
    if unit == "mil":
        return round(number * 0.0254, 3)
    if unit in {"in", "inch", "inches"}:
        return round(number * 25.4, 6)
    if unit in {"um", "µm"}:
        return round(number / 1000.0, 6)
    return number


def _rewrite_board_setup_values(board_text: str, board_values: dict[str, float]) -> str:
    rewritten = board_text
    for field in _SETUP_FIELDS:
        if field not in board_values:
            continue
        rewritten = re.sub(
            rf"(\({re.escape(field)}\s+)([^\s\)]+)(\))",
            rf"\g<1>{_format_mm(board_values[field])}\3",
            rewritten,
            count=1,
        )
    return rewritten


def _rewrite_zone_sections(board_text: str, board_values: dict[str, Any]) -> str:
    if not any(
        key in board_values
        for key in ("zone_clearance", "zone_thermal_gap", "zone_thermal_bridge_width")
    ):
        return board_text

    lines = board_text.splitlines(keepends=True)
    rewritten_lines: list[str] = []
    index = 0
    while index < len(lines):
        if lines[index].lstrip().startswith("(zone"):
            end = _consume_block(lines, index)
            rewritten_lines.extend(_rewrite_zone_block(lines[index:end], board_values))
            index = end
            continue
        rewritten_lines.append(lines[index])
        index += 1
    return "".join(rewritten_lines)


def _rewrite_zone_block(zone_lines: list[str], board_values: dict[str, Any]) -> list[str]:
    rewritten_lines: list[str] = []
    for line in zone_lines:
        rewritten_line = line
        if line.lstrip().startswith("(connect_pads") and "zone_clearance" in board_values:
            rewritten_line = _rewrite_connect_pads_line(rewritten_line, board_values["zone_clearance"])
        if line.lstrip().startswith("(fill"):
            rewritten_line = _rewrite_fill_line(rewritten_line, board_values)
        rewritten_lines.append(rewritten_line)
    return rewritten_lines


def _rewrite_connect_pads_line(line: str, clearance: float) -> str:
    if "(clearance " not in line:
        return line
    return _rewrite_bracketed_value(line, "clearance", clearance)


def _rewrite_fill_line(line: str, board_values: dict[str, Any]) -> str:
    rewritten = line
    thermal_gap = board_values.get("zone_thermal_gap")
    thermal_bridge_width = board_values.get("zone_thermal_bridge_width")
    if thermal_gap is not None:
        rewritten = _rewrite_bracketed_value(rewritten, "thermal_gap", thermal_gap)
    if thermal_bridge_width is not None:
        rewritten = _rewrite_bracketed_value(rewritten, "thermal_bridge_width", thermal_bridge_width)
    return rewritten


def _rewrite_bracketed_value(line: str, key: str, value: float) -> str:
    pattern = rf"\({re.escape(key)}\s+[^\)]+\)"
    replacement = f"({key} {_format_mm(value)})"
    if re.search(pattern, line):
        return re.sub(pattern, replacement, line)

    stripped = line.rstrip("\r\n")
    suffix = line[len(stripped):]
    if not stripped.rstrip().endswith(")"):
        return line
    base = stripped.rstrip()
    base = base[:-1].rstrip()
    return f"{base} {replacement}){suffix}"


def _replace_net_class_section(
    board_text: str,
    net_classes: list[dict[str, Any]],
    board_values: dict[str, float],
) -> str:
    lines = board_text.splitlines(keepends=True)
    start = _find_first_block_start(lines, "(net_class")
    if start is None:
        return board_text
    end = start
    while end < len(lines):
        stripped = lines[end].strip()
        if not stripped:
            end += 1
            continue
        if stripped.startswith("(net_class"):
            end = _consume_block(lines, end)
            continue
        break
    replacement = "".join(_render_board_net_class_block(class_data, board_values) for class_data in net_classes)
    return "".join(lines[:start]) + replacement + "".join(lines[end:])


def _find_first_block_start(lines: list[str], prefix: str) -> int | None:
    for index, line in enumerate(lines):
        if line.lstrip().startswith(prefix):
            return index
    return None


def _consume_block(lines: list[str], start_index: int) -> int:
    balance = 0
    seen_open = False
    for index in range(start_index, len(lines)):
        line = lines[index]
        balance += line.count("(") - line.count(")")
        if "(" in line:
            seen_open = True
        if seen_open and balance <= 0:
            return index + 1
    return len(lines)


def _render_board_net_class_block(class_data: dict[str, Any], board_values: dict[str, float]) -> str:
    clearance = class_data.get("clearance", board_values.get("trace_clearance", 0.25))
    trace_width = class_data.get("trace_width", board_values.get("trace_min", 0.25))
    via_dia = class_data.get("via_dia", board_values.get("via_size", 0.8))
    via_drill = class_data.get("via_drill", board_values.get("via_drill", 0.4))
    uvia_dia = class_data.get("uvia_dia", board_values.get("uvia_size", 0.508))
    uvia_drill = class_data.get("uvia_drill", board_values.get("uvia_drill", 0.127))
    description = class_data.get("description") or class_data.get("name", "Default")
    nets = class_data.get("nets") or []

    lines = [
        f'  (net_class {class_data.get("name", "Default")} "{description}"',
        f"    (clearance {_format_mm(clearance)})",
        f"    (trace_width {_format_mm(trace_width)})",
        f"    (via_dia {_format_mm(via_dia)})",
        f"    (via_drill {_format_mm(via_drill)})",
        f"    (uvia_dia {_format_mm(uvia_dia)})",
        f"    (uvia_drill {_format_mm(uvia_drill)})",
    ]
    if "diff_pair_gap" in class_data:
        lines.append(f"    (diff_pair_gap {_format_mm(class_data['diff_pair_gap'])})")
    if "diff_pair_width" in class_data:
        lines.append(f"    (diff_pair_width {_format_mm(class_data['diff_pair_width'])})")
    for net in nets:
        lines.append(f'    (add_net "{net}")')
    lines.append("  )")
    return "\n".join(lines) + "\n"


def _extract_setup_values(board_text: str) -> dict[str, float]:
    setup: dict[str, float] = {}
    for key, dest in _SETUP_FIELDS.items():
        value = _first_float(board_text, rf"\({re.escape(key)}\s+({_FLOAT})\)")
        if value is not None:
            setup[dest] = value
    return setup


def _extract_net_classes(board_text: str) -> list[dict[str, Any]]:
    classes: list[dict[str, Any]] = []
    for match in re.finditer(
        r"\(net_class\s+(?P<name>(?:\"[^\"]*\"|[^\s()]+))\s+\"(?P<description>[^\"]*)\"(?P<body>.*?)\n\s*\)",
        board_text,
        re.S,
    ):
        body = match.group("body")
        entry: dict[str, Any] = {
            "name": _unquote(match.group("name")),
            "description": match.group("description"),
            "nets": _extract_nets(body),
        }
        for key, dest in _NET_CLASS_FIELDS.items():
            value = _first_float(body, rf"\({re.escape(key)}\s+({_FLOAT})\)")
            if value is not None:
                entry[dest] = value
        classes.append(entry)
    return classes


def _extract_nets(body: str) -> list[str]:
    nets: list[str] = []
    for net_match in re.finditer(r'\(add_net\s+"?(?P<net>[^"\)\r\n]+)"?\)', body):
        nets.append(net_match.group("net"))
    return nets


def _project_net_class(class_data: dict[str, Any], board_defaults: dict[str, float]) -> dict[str, Any]:
    clearance = class_data.get("clearance", board_defaults.get("trace_clearance", 0.25))
    track_width = class_data.get("trace_width", board_defaults.get("trace_min", 0.25))
    via_dia = class_data.get("via_dia", board_defaults.get("via_size", 0.8))
    via_drill = class_data.get("via_drill", board_defaults.get("via_drill", 0.4))
    uvia_dia = class_data.get("uvia_dia", board_defaults.get("uvia_size", 0.508))
    uvia_drill = class_data.get("uvia_drill", board_defaults.get("uvia_drill", 0.127))
    return {
        "bus_width": 12.0,
        "clearance": clearance,
        "diff_pair_gap": class_data.get("diff_pair_gap", 0.25),
        "diff_pair_via_gap": 0.25,
        "diff_pair_width": class_data.get("diff_pair_width", 0.2),
        "line_style": 0,
        "microvia_diameter": uvia_dia,
        "microvia_drill": uvia_drill,
        "name": class_data.get("name", "Default"),
        "pcb_color": "rgba(0, 0, 0, 0.000)",
        "schematic_color": "rgba(0, 0, 0, 0.000)",
        "track_width": track_width,
        "via_diameter": via_dia,
        "via_drill": via_drill,
        "wire_width": 6.0,
    }


def _default_net_class(board_defaults: dict[str, float]) -> dict[str, Any]:
    return {
        "name": "Default",
        "clearance": board_defaults.get("trace_clearance", 0.25),
        "trace_width": board_defaults.get("trace_min", 0.25),
        "via_dia": board_defaults.get("via_size", 0.8),
        "via_drill": board_defaults.get("via_drill", 0.4),
        "uvia_dia": board_defaults.get("uvia_size", 0.508),
        "uvia_drill": board_defaults.get("uvia_drill", 0.127),
        "diff_pair_gap": 0.25,
        "diff_pair_width": 0.2,
    }


def _first_float(text: str, pattern: str) -> float | None:
    match = re.search(pattern, text)
    if not match:
        return None
    return float(match.group(1))


def _format_mm(value: float) -> str:
    text = f"{value:.6f}".rstrip("0").rstrip(".")
    return text if text else "0"


def _unquote(value: str) -> str:
    if value.startswith('"') and value.endswith('"'):
        return value[1:-1]
    return value

from eda2kicad.altium_ascii.lexer import split_records


def parse_ascii_schematic(text: str) -> dict[str, list[dict[str, str]]]:
    buckets = {
        "components": [],
        "fields": [],
        "wires": [],
        "net_labels": [],
    }
    for record in split_records(text):
        record_type = record["RECORD"]
        if record_type == "COMPONENT":
            buckets["components"].append(record)
        elif record_type == "FIELD":
            buckets["fields"].append(record)
        elif record_type == "WIRE":
            buckets["wires"].append(record)
        elif record_type == "NET_LABEL":
            buckets["net_labels"].append(record)
    return buckets

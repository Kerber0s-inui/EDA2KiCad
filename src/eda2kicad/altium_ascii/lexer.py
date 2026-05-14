def split_records(text: str) -> list[dict[str, str]]:
    blocks = [block.strip() for block in text.strip().split("\n\n") if block.strip()]
    records: list[dict[str, str]] = []
    for block in blocks:
        record: dict[str, str] = {}
        for line in block.splitlines():
            key, value = line.split("=", 1)
            record[key.strip()] = value.strip()
        records.append(record)
    return records

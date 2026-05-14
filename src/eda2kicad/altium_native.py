import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from eda2kicad.core.ir import ComponentInstance, NetLabel, Project, Sheet
from eda2kicad.strategies.tooling import ALTIUM2KICAD_DIR, PERL_PATH


def is_native_altium_path(input_path: Path) -> bool:
    return input_path.suffix.lower() in {".schdoc", ".pcbdoc"}


def is_ascii_pcbdoc_path(input_path: Path) -> bool:
    if input_path.suffix.lower() != ".pcbdoc":
        return False
    try:
        header = input_path.read_bytes()[:32].lstrip(b"\xef\xbb\xbf\r\n\t ")
    except OSError:
        return False
    return header.startswith(b"|RECORD=Board|")


def unpack_native_file(input_path: Path, output_root: Path) -> Path:
    if not PERL_PATH.exists():
        raise ValueError(f"missing perl: {PERL_PATH}")
    if not ALTIUM2KICAD_DIR.exists():
        raise ValueError(f"missing altium2kicad: {ALTIUM2KICAD_DIR}")

    run_dir = Path(tempfile.mkdtemp(prefix=f"{input_path.stem}-", dir=output_root))
    staged_input = run_dir / input_path.name
    shutil.copy2(input_path, staged_input)
    _run_perl(
        [str(PERL_PATH), str(ALTIUM2KICAD_DIR / "unpack.pl"), staged_input.name],
        cwd=run_dir,
        env=_native_tool_env(),
    )
    unpacked_dir = run_dir / f"{input_path.stem}-{input_path.suffix.lstrip('.')}"
    if not unpacked_dir.exists():
        raise ValueError(f"native unpack did not create directory for {input_path.name}")
    return unpacked_dir


def parse_native_schematic_project(input_path: Path, output_root: Path) -> Project:
    unpacked_dir = unpack_native_file(input_path, output_root)
    file_header = unpacked_dir / "Root Entry" / "FileHeader.dat"
    if not file_header.exists():
        raise ValueError(f"missing native schematic payload: {file_header}")

    records = list(iter_native_records(file_header.read_text(encoding="utf-8", errors="ignore")))
    components_by_owner: dict[str, dict[str, str]] = {}
    labels: list[NetLabel] = []

    for record_index, record in enumerate(records):
        record_type = record.get("RECORD")
        if record_type == "1":
            components_by_owner[str(record_index)] = record
        elif record_type == "25":
            text = record.get("TEXT", "").strip()
            x = _parse_int(record.get("LOCATION.X"))
            y = _parse_int(record.get("LOCATION.Y"))
            if text and x is not None and y is not None:
                labels.append(NetLabel(text=text, position=(x, y)))
        elif record_type == "34":
            owner_index = record.get("OWNERINDEX")
            if owner_index and owner_index in components_by_owner:
                components_by_owner[owner_index]["DESIGNATOR"] = record.get("TEXT", "").strip()
        elif record_type == "41":
            owner_index = record.get("OWNERINDEX")
            name = record.get("NAME")
            if owner_index and owner_index in components_by_owner and name == "Comment":
                components_by_owner[owner_index]["VALUE"] = record.get("TEXT", "").strip()

    components = [
        ComponentInstance(
            designator=component.get("DESIGNATOR", f"U{index + 1}"),
            library_key=component.get("LIBREFERENCE", "UNKNOWN"),
            value=component.get("VALUE", component.get("LIBREFERENCE", "")),
            footprint=component.get("PACKAGEREFERENCE", ""),
            fields=[],
        )
        for index, component in enumerate(components_by_owner.values())
    ]
    return Project(name=input_path.stem, sheets=[Sheet(name="Sheet1", components=components, net_labels=labels)])


def iter_native_records(text: str):
    for chunk in text.split("\x00"):
        if "|RECORD=" not in chunk:
            continue
        start = chunk.find("|RECORD=")
        payload = chunk[start:].strip("|")
        record: dict[str, str] = {}
        for item in payload.split("|"):
            if "=" not in item:
                continue
            key, value = item.split("=", 1)
            record[key.strip()] = value.strip()
        if "RECORD" in record:
            yield record


def _parse_int(value: str | None) -> int | None:
    if value is None:
        return None
    digits = []
    for char in value:
        if char in "-0123456789":
            digits.append(char)
        else:
            break
    if not digits or digits == ["-"]:
        return None
    return int("".join(digits))


def _native_tool_env() -> dict[str, str]:
    env = os.environ.copy()
    env["PERL5LIB"] = str(ALTIUM2KICAD_DIR)
    return env


def _run_perl(command: list[str], cwd: Path, env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(command, cwd=cwd, env=env, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        stderr = result.stderr.strip() or result.stdout.strip() or "perl conversion failed"
        raise ValueError(stderr)
    return result

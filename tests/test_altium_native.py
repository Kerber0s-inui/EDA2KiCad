from pathlib import Path

from eda2kicad import altium_native
from tests._paths import ALTIUM2KICAD_ROOT


def test_unpack_native_file_uses_absolute_unpack_script_path(
    tmp_path: Path,
    monkeypatch,
) -> None:
    input_file = tmp_path / "demo.SchDoc"
    input_file.write_bytes(b"native")
    output_root = tmp_path / "out"
    output_root.mkdir()

    captured: dict[str, object] = {}

    def fake_run_perl(command: list[str], cwd: Path, env: dict[str, str]):
        captured["command"] = command
        unpacked_dir = cwd / "demo-SchDoc"
        unpacked_dir.mkdir()
        return None

    monkeypatch.setattr(altium_native, "_run_perl", fake_run_perl)

    unpacked_dir = altium_native.unpack_native_file(input_file, output_root)

    assert unpacked_dir == next(output_root.iterdir()) / "demo-SchDoc"
    assert captured["command"][1] == str(ALTIUM2KICAD_ROOT / "unpack.pl")

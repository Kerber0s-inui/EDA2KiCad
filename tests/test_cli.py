from pathlib import Path
from typer.testing import CliRunner

from eda2kicad.cli import app
from tests._paths import ALTIUM2KICAD_TESTS


def test_cli_convert_writes_kicad_output(tmp_path: Path) -> None:
    input_file = tmp_path / "demo.txt"
    input_file.write_text("RECORD=NET_LABEL\nTEXT=NET_A\nX=100\nY=0\n", encoding="utf-8")
    output_dir = tmp_path / "output"

    result = CliRunner().invoke(
        app,
        ["convert", str(input_file), "--output", str(output_dir), "--strategy", "kicad-official"],
    )

    assert result.exit_code != 0
    assert "only native Altium inputs are supported" in result.output


def test_cli_rejects_unknown_strategy(tmp_path: Path) -> None:
    input_file = tmp_path / "demo.SchDoc"
    input_file.write_bytes(b"dummy schdoc")
    output_dir = tmp_path / "output"

    result = CliRunner().invoke(
        app,
        ["convert", str(input_file), "--output", str(output_dir), "--strategy", "unknown"],
    )

    assert result.exit_code != 0
    assert "unknown strategy" in result.output


def test_cli_convert_native_pcbdoc_with_kicad_official_strategy(
    tmp_path: Path,
    monkeypatch,
) -> None:
    import subprocess

    from eda2kicad.strategies import kicad_official

    input_file = ALTIUM2KICAD_TESTS / "via2.PcbDoc"
    output_dir = tmp_path / "output"

    def fake_run(command: list[str]) -> subprocess.CompletedProcess[str]:
        output_index = command.index("--output") + 1
        report_index = command.index("--report-file") + 1
        output_path = Path(command[output_index])
        report_path = Path(command[report_index])
        output_path.write_text("(kicad_pcb (version 20231120) (generator pcbnew))\n", encoding="utf-8")
        report_path.write_text('{"issues":[],"summary":{"error_count":0,"warning_count":0}}', encoding="utf-8")
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr(kicad_official, "_run_kicad_cli", fake_run)

    result = CliRunner().invoke(
        app,
        ["convert", str(input_file), "--output", str(output_dir), "--strategy", "kicad-official"],
    )

    assert result.exit_code == 0
    board_path = Path(next(line for line in result.output.splitlines() if line.startswith("board=")).split("=", 1)[1])
    assert board_path.exists()


def test_cli_convert_native_pcbdoc_with_pcbnew_api_strategy(
    tmp_path: Path,
    monkeypatch,
) -> None:
    from eda2kicad.strategies import pcbnew_api

    input_file = ALTIUM2KICAD_TESTS / "via2.PcbDoc"
    output_dir = tmp_path / "output"

    def fake_convert_native_pcb(
        _input_path: Path,
        *,
        output_root: Path | None = None,
    ) -> dict[str, object]:
        del _input_path
        del output_root
        return {
            "project_name": "via2",
            "schematic_text": None,
            "schematic_extension": None,
            "board_text": "(kicad_pcb (version 20231120) (generator pcbnew))\n",
            "board_extension": ".kicad_pcb",
            "auxiliary_text_artifacts": {
                "via2.kicad_pro": "{\n  \"meta\": {\"version\": 1}\n}\n",
            },
            "report": {
                "summary": {"error_count": 0, "warning_count": 0},
                "issues": [],
                "strategy": pcbnew_api.get_strategy_metadata(),
            },
        }

    monkeypatch.setattr(pcbnew_api, "convert_native_pcb", fake_convert_native_pcb)

    result = CliRunner().invoke(
        app,
        ["convert", str(input_file), "--output", str(output_dir), "--strategy", "pcbnew-api"],
    )

    assert result.exit_code == 0
    board_path = Path(next(line for line in result.output.splitlines() if line.startswith("board=")).split("=", 1)[1])
    assert board_path.exists()


def test_cli_convert_native_pcbdoc_with_kicad_gui_official_strategy(
    tmp_path: Path,
    monkeypatch,
) -> None:
    from eda2kicad.strategies import kicad_gui_official

    input_file = ALTIUM2KICAD_TESTS / "via2.PcbDoc"
    output_dir = tmp_path / "output"

    def fake_convert_native_pcb(
        _input_path: Path,
        *,
        output_root: Path | None = None,
    ) -> dict[str, object]:
        del _input_path
        del output_root
        return {
            "project_name": "via2",
            "schematic_text": None,
            "schematic_extension": None,
            "board_text": "(kicad_pcb (version 20231120) (generator pcbnew))\n",
            "board_extension": ".kicad_pcb",
            "auxiliary_text_artifacts": {
                "via2.kicad_pro": "{\n  \"meta\": {\"version\": 1}\n}\n",
            },
            "report": {
                "summary": {"error_count": 0, "warning_count": 0},
                "issues": [],
                "automation": {"phase": "completed"},
                "strategy": kicad_gui_official.get_strategy_metadata(),
            },
        }

    monkeypatch.setattr(kicad_gui_official, "convert_native_pcb", fake_convert_native_pcb)

    result = CliRunner().invoke(
        app,
        ["convert", str(input_file), "--output", str(output_dir), "--strategy", "kicad-gui-official"],
    )

    assert result.exit_code == 0
    board_path = Path(next(line for line in result.output.splitlines() if line.startswith("board=")).split("=", 1)[1])
    assert board_path.exists()


def test_cli_convert_native_schdoc_with_kicad_gui_official_strategy(
    tmp_path: Path,
    monkeypatch,
) -> None:
    from eda2kicad.strategies import kicad_gui_official

    input_file = ALTIUM2KICAD_TESTS / "via2.SchDoc"
    output_dir = tmp_path / "output"

    def fake_convert_native_schematic(
        _input_path: Path,
        *,
        output_root: Path | None = None,
    ) -> dict[str, object]:
        del _input_path
        del output_root
        return {
            "project_name": "via2",
            "schematic_text": "(kicad_sch (version 20231120) (generator eeschema))\n",
            "schematic_extension": ".kicad_sch",
            "board_text": None,
            "board_extension": None,
            "auxiliary_text_artifacts": {
                "via2.kicad_pro": "{\n  \"meta\": {\"version\": 1}\n}\n",
            },
            "report": {
                "summary": {"error_count": 0, "warning_count": 0},
                "issues": [],
                "automation": {"phase": "completed"},
                "strategy": kicad_gui_official.get_strategy_metadata(),
            },
        }

    monkeypatch.setattr(kicad_gui_official, "convert_native_schematic", fake_convert_native_schematic)

    result = CliRunner().invoke(
        app,
        ["convert", str(input_file), "--output", str(output_dir), "--strategy", "kicad-gui-official"],
    )

    assert result.exit_code == 0
    schematic_path = Path(next(line for line in result.output.splitlines() if line.startswith("schematic=")).split("=", 1)[1])
    assert schematic_path.exists()


def test_cli_convert_native_schdoc_with_third_party_strategy(
    tmp_path: Path,
    monkeypatch,
) -> None:
    import subprocess

    from eda2kicad.strategies import third_party

    input_file = ALTIUM2KICAD_TESTS / "via2.SchDoc"
    output_dir = tmp_path / "output"

    def fake_run(command: list[str], cwd: Path, env: dict[str, str]) -> subprocess.CompletedProcess[str]:
        del env
        if command[1] == "unpack.pl":
            (cwd / "via2.SchDoc").write_bytes(input_file.read_bytes())
            (cwd / "via2-SchDoc").mkdir(parents=True, exist_ok=True)
        elif command[1] == "convertschema.pl":
            (cwd / "via2-SchDoc.sch").write_text(
                '(kicad_sch (version 20231120) (generator third-party))\n',
                encoding="utf-8",
            )
            (cwd / "via2-SchDoc-cache.lib").write_text("EESchema-LIBRARY Version 2.4\n", encoding="utf-8")
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr(third_party, "_run_command", fake_run)

    result = CliRunner().invoke(
        app,
        ["convert", str(input_file), "--output", str(output_dir), "--strategy", "third-party"],
    )

    assert result.exit_code == 0
    schematic_path = Path(next(line for line in result.output.splitlines() if line.startswith("schematic=")).split("=", 1)[1])
    assert schematic_path.exists()
    assert "cache_lib=" not in result.output
    assert not list(schematic_path.parent.glob("*-cache.lib"))


def test_cli_convert_native_pcbdoc_with_third_party_strategy(
    tmp_path: Path,
    monkeypatch,
) -> None:
    import subprocess

    from eda2kicad.strategies import third_party

    input_file = ALTIUM2KICAD_TESTS / "via2.PcbDoc"
    output_dir = tmp_path / "output"

    def fake_run(command: list[str], cwd: Path, env: dict[str, str]) -> subprocess.CompletedProcess[str]:
        del env
        if command[1] == "unpack.pl":
            (cwd / "via2.PcbDoc").write_bytes(input_file.read_bytes())
            (cwd / "via2-PcbDoc").mkdir(parents=True, exist_ok=True)
        elif command[1] == "convertpcb.pl":
            (cwd / "via2-PcbDoc.kicad_pcb").write_text(
                "(kicad_pcb (version 20231120) (generator pcbnew))\n",
                encoding="utf-8",
            )
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr(third_party, "_run_command", fake_run)

    result = CliRunner().invoke(
        app,
        ["convert", str(input_file), "--output", str(output_dir), "--strategy", "third-party"],
    )

    assert result.exit_code == 0
    board_path = Path(next(line for line in result.output.splitlines() if line.startswith("board=")).split("=", 1)[1])
    assert board_path.exists()

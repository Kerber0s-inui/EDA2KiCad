import json
import subprocess
from pathlib import Path

import pytest

from eda2kicad.strategies import pcbnew_api


def test_convert_native_pcb_uses_pcbnew_python_and_reads_generated_outputs(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    input_file = tmp_path / "demo.PcbDoc"
    input_file.write_bytes(b"pcbdoc")
    requested_output_root = tmp_path / "requested-output"
    seen: dict[str, object] = {}

    def fake_run(command: list[str]) -> subprocess.CompletedProcess[str]:
        seen["command"] = command
        output_index = command.index("--output") + 1
        report_index = command.index("--report-file") + 1
        output_path = Path(command[output_index])
        report_path = Path(command[report_index])
        output_path.write_text("(kicad_pcb (version 20231120) (generator pcbnew))\n", encoding="utf-8")
        report_path.write_text(
            json.dumps({"issues": [], "summary": {"error_count": 0, "warning_count": 0}}),
            encoding="utf-8",
        )
        return subprocess.CompletedProcess(command, 0, "ok", "")

    monkeypatch.setattr(pcbnew_api, "_run_pcbnew_python", fake_run)

    result = pcbnew_api.convert_native_pcb(input_file, output_root=requested_output_root)

    command = seen["command"]
    assert isinstance(command, list)
    assert command[0] == str(pcbnew_api.KICAD_PYTHON_PATH)
    assert "board_text" in result
    assert result["board_text"] is not None
    assert "(generator pcbnew)" in result["board_text"]
    assert result["board_extension"] == ".kicad_pcb"
    assert result["report"]["strategy"]["strategy_id"] == "pcbnew-api"
    assert result["report"]["pcbnew_import_report"]["summary"]["error_count"] == 0


def test_convert_rejects_non_pcbdoc_input(tmp_path: Path) -> None:
    input_file = tmp_path / "demo.SchDoc"
    input_file.write_text("schematic", encoding="utf-8")

    with pytest.raises(ValueError, match="only supports \\.PcbDoc"):
        pcbnew_api.convert(input_file, tmp_path / "mapping.json")


def test_convert_native_pcb_accepts_nonzero_exit_when_board_output_exists(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    input_file = tmp_path / "demo.PcbDoc"
    input_file.write_bytes(b"pcbdoc")

    def fake_run(command: list[str]) -> subprocess.CompletedProcess[str]:
        output_index = command.index("--output") + 1
        output_path = Path(command[output_index])
        output_path.write_text("(kicad_pcb (version 20231120) (generator pcbnew))\n", encoding="utf-8")
        return subprocess.CompletedProcess(command, 1, "partial output", "warning dialog interrupted exit")

    monkeypatch.setattr(pcbnew_api, "_run_pcbnew_python", fake_run)

    result = pcbnew_api.convert_native_pcb(input_file, output_root=tmp_path / "out")

    assert result["board_extension"] == ".kicad_pcb"
    assert result["board_text"] is not None
    assert result["report"]["summary"]["warning_count"] == 1
    runtime = result["report"]["pcbnew_runtime"]
    assert runtime["returncode"] == 1
    assert runtime["output_created"] is True
    assert "warning dialog interrupted exit" in runtime["stderr"]


def test_run_pcbnew_python_dismisses_windows_dialogs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen: dict[str, object] = {}

    class DummyProcess:
        returncode = 0

        def poll(self):
            if not seen.get("communicate_called"):
                return None
            return 0

        def communicate(self):
            seen["communicate_called"] = True
            return (b"ok", b"")

    class DummyThread:
        def __init__(self, *, target, daemon):
            seen["thread_target"] = target
            seen["thread_daemon"] = daemon

        def start(self):
            seen["thread_started"] = True

    monkeypatch.setattr(pcbnew_api.platform, "system", lambda: "Windows")
    monkeypatch.setattr(pcbnew_api.subprocess, "Popen", lambda *args, **kwargs: DummyProcess())
    monkeypatch.setattr(pcbnew_api.threading, "Thread", DummyThread)

    result = pcbnew_api._run_pcbnew_python(["cmd"])

    assert result.returncode == 0
    assert seen["thread_daemon"] is True
    assert seen["thread_started"] is True
    assert seen["communicate_called"] is True

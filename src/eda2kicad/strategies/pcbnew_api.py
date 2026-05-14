import json
import platform
import subprocess
import tempfile
import threading
import time
from pathlib import Path

from eda2kicad.strategies.base import ConversionPayload, StrategyMetadata, resolve_strategy_work_root
from eda2kicad.strategies.tooling import KICAD_PYTHON_PATH

STRATEGY_ID = "pcbnew-api"


def get_strategy_metadata() -> StrategyMetadata:
    return {
        "strategy_id": STRATEGY_ID,
        "mode": "candidate",
        "uses_kicad_capability": True,
        "uses_external_project": False,
        "status": "active",
    }


def convert(
    input_path: Path,
    mapping_path: Path,
    output_root: Path | None = None,
) -> ConversionPayload:
    del mapping_path
    if input_path.suffix.lower() != ".pcbdoc":
        raise ValueError("pcbnew-api only supports .PcbDoc input")
    return convert_native_pcb(input_path, output_root=output_root)


def convert_native_pcb(input_path: Path, *, output_root: Path | None = None) -> ConversionPayload:
    if not KICAD_PYTHON_PATH.exists():
        raise ValueError(f"missing KiCad python runtime: {KICAD_PYTHON_PATH}")

    temp_root = resolve_strategy_work_root("pcbnew-api-native", output_root)
    run_dir = Path(tempfile.mkdtemp(prefix="pcbnew-import-", dir=temp_root))
    output_path = run_dir / f"{input_path.stem}.kicad_pcb"
    report_path = run_dir / "pcbnew-import-report.json"
    command = _build_pcbnew_python_command(input_path, output_path, report_path)
    result = _run_pcbnew_python(command)
    output_exists = output_path.exists()
    if result.returncode != 0 and not output_exists:
        stderr = result.stderr.strip() or result.stdout.strip() or "pcbnew-api import failed"
        raise ValueError(stderr)
    if not output_exists:
        raise ValueError("pcbnew-api import did not create output board")

    warning_count = 1 if result.returncode != 0 else 0
    report_payload: dict[str, object] = {
        "summary": {"error_count": 0, "warning_count": warning_count},
        "issues": [],
    }
    if report_path.exists():
        try:
            report_payload["pcbnew_import_report"] = json.loads(report_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            report_payload["pcbnew_import_report"] = report_path.read_text(encoding="utf-8", errors="replace")
    report_payload["pcbnew_runtime"] = {
        "returncode": result.returncode,
        "stdout": result.stdout.strip(),
        "stderr": result.stderr.strip(),
        "output_created": output_exists,
        "report_created": report_path.exists(),
    }
    report_payload["strategy"] = get_strategy_metadata()
    return {
        "project_name": input_path.stem,
        "schematic_text": None,
        "schematic_extension": None,
        "board_text": output_path.read_text(encoding="utf-8"),
        "board_extension": ".kicad_pcb",
        "auxiliary_text_artifacts": {},
        "report": report_payload,
    }


def _build_pcbnew_python_command(input_path: Path, output_path: Path, report_path: Path) -> list[str]:
    script = "\n".join(
        [
            "import json",
            "import sys",
            "from pathlib import Path",
            "import pcbnew",
            "",
            "args = sys.argv[1:]",
            "input_path = Path(args[args.index('--input') + 1])",
            "output_path = Path(args[args.index('--output') + 1])",
            "report_path = Path(args[args.index('--report-file') + 1])",
            "board = pcbnew.PCB_IO_MGR.Load(pcbnew.PCB_IO_MGR.ALTIUM_DESIGNER, str(input_path))",
            "if board is None:",
            "    raise RuntimeError('pcbnew returned None while importing Altium board')",
            "board.Save(str(output_path))",
            "report = {",
            "    'summary': {'error_count': 0, 'warning_count': 0},",
            "    'issues': [],",
            "    'footprint_count': len(board.GetFootprints()),",
            "}",
            "report_path.write_text(json.dumps(report, indent=2), encoding='utf-8')",
            "print(str(output_path))",
        ]
    )
    return [
        str(KICAD_PYTHON_PATH),
        "-c",
        script,
        "--input",
        str(input_path),
        "--output",
        str(output_path),
        "--report-file",
        str(report_path),
    ]


def _run_pcbnew_python(command: list[str]) -> subprocess.CompletedProcess[str]:
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if platform.system() == "Windows":
        threading.Thread(target=lambda: _dismiss_windows_dialogs(process), daemon=True).start()
    stdout, stderr = process.communicate()
    return subprocess.CompletedProcess(
        command,
        process.returncode,
        stdout.decode("utf-8", errors="replace"),
        stderr.decode("utf-8", errors="replace"),
    )


def _dismiss_windows_dialogs(process: subprocess.Popen[bytes]) -> None:
    import ctypes

    user32 = ctypes.windll.user32
    while process.poll() is None:
        hwnd = user32.FindWindowW("wxWindowNR", None)
        if not hwnd:
            hwnd = user32.FindWindowW(None, "Message")
        if hwnd:
            user32.PostMessageW(hwnd, 0x0010, 0, 0)
        time.sleep(0.2)

import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

from eda2kicad.altium_native import is_ascii_pcbdoc_path, is_native_altium_path
from eda2kicad.strategies.base import ConversionPayload, StrategyMetadata, resolve_strategy_work_root
from eda2kicad.strategies.pcb_rule_overrides import (
    apply_board_rule_overrides,
    build_kicad_project_text,
    extract_board_rule_overrides,
    extract_native_board_rule_overrides,
)
from eda2kicad.strategies.tooling import ALTIUM2KICAD_DIR, PERL_PATH

STRATEGY_ID = "third-party"


def get_strategy_metadata() -> StrategyMetadata:
    return {
        "strategy_id": STRATEGY_ID,
        "mode": "candidate",
        "uses_kicad_capability": False,
        "uses_external_project": True,
        "status": "active",
    }


def convert(
    input_path: Path,
    mapping_path: Path,
    output_root: Path | None = None,
) -> ConversionPayload:
    if not is_native_altium_path(input_path):
        raise ValueError("third-party strategy only supports native Altium .SchDoc/.PcbDoc input")
    if output_root is None:
        return convert_native(input_path)
    return convert_native(input_path, output_root=output_root)


def convert_native(input_path: Path, *, output_root: Path | None = None) -> ConversionPayload:
    if is_ascii_pcbdoc_path(input_path):
        raise ValueError(
            "third-party PCB does not support ASCII .PcbDoc input yet; "
            "please provide a binary .PcbDoc"
        )
    native_root = resolve_strategy_work_root("third-party-native", output_root)
    run_dir = Path(tempfile.mkdtemp(prefix=f"{input_path.stem}-", dir=native_root))
    staged_input = run_dir / input_path.name
    shutil.copy2(input_path, staged_input)
    env = _native_tool_env()
    _run_command([str(PERL_PATH), "unpack.pl", staged_input.name], cwd=run_dir, env=env)

    if input_path.suffix.lower() == ".schdoc":
        _run_command([str(PERL_PATH), "convertschema.pl"], cwd=run_dir, env=env)
        schematic_path = _find_generated_native_schematic(run_dir, input_path)
        cache_lib_path = _find_generated_native_cache_lib(run_dir, input_path)
        if not schematic_path.exists():
            raise ValueError("third-party schematic conversion did not create .sch output")
        report = {
            "summary": {"error_count": 0, "warning_count": 0},
            "issues": [],
            "strategy": get_strategy_metadata(),
        }
        if cache_lib_path.exists():
            report["third_party_cache_lib"] = str(cache_lib_path)
        return {
            "project_name": input_path.stem,
            "schematic_text": _repair_schematic_text(
                schematic_path.read_text(encoding="utf-8", errors="replace")
            ),
            "schematic_extension": ".sch",
            "board_text": None,
            "board_extension": None,
            "auxiliary_text_artifacts": {
                f"{input_path.stem}-cache.lib": _repair_schematic_text(
                    cache_lib_path.read_text(encoding="utf-8", errors="replace")
                )
            }
            if cache_lib_path.exists()
            else {},
            "report": report,
        }

    _run_command([str(PERL_PATH), "convertpcb.pl"], cwd=run_dir, env=env)
    board_path = run_dir / f"{input_path.stem}-PcbDoc.kicad_pcb"
    if not board_path.exists():
        raise ValueError("third-party pcb conversion did not create .kicad_pcb output")
    board_text = board_path.read_text(encoding="utf-8", errors="replace")
    native_board_root = run_dir / f"{input_path.stem}-PcbDoc"
    board_overrides = extract_native_board_rule_overrides(native_board_root)
    if board_overrides["board"] or board_overrides["net_classes"]:
        board_text = apply_board_rule_overrides(board_text, board_overrides)
    else:
        board_overrides = extract_board_rule_overrides(board_text)
    auxiliary_text_artifacts: dict[str, str] = {}
    if board_overrides["board"] or board_overrides["net_classes"]:
        auxiliary_text_artifacts[f"{input_path.stem}.kicad_pro"] = build_kicad_project_text(
            input_path.stem,
            board_overrides,
        )
    return {
        "project_name": input_path.stem,
        "schematic_text": None,
        "schematic_extension": None,
        "board_text": board_text,
        "board_extension": ".kicad_pcb",
        "auxiliary_text_artifacts": auxiliary_text_artifacts,
        "report": {
            "summary": {"error_count": 0, "warning_count": 0},
            "issues": [],
            "design_rule_overrides": board_overrides,
            "strategy": get_strategy_metadata(),
        },
    }


def _run_command(command: list[str], cwd: Path, env: dict[str, str]):
    if not ALTIUM2KICAD_DIR.exists():
        raise ValueError(f"missing altium2kicad: {ALTIUM2KICAD_DIR}")
    if not PERL_PATH.exists():
        raise ValueError(f"missing perl: {PERL_PATH}")
    script_name = command[1]
    script_path = ALTIUM2KICAD_DIR / script_name
    if not script_path.exists():
        raise ValueError(f"missing third-party script: {script_path}")

    actual_command = [command[0], str(script_path), *command[2:]]
    result = subprocess.run(actual_command, cwd=cwd, env=env, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        stderr = result.stderr.strip() or result.stdout.strip() or "third-party conversion failed"
        raise ValueError(stderr)
    return result


def _native_tool_env() -> dict[str, str]:
    env = os.environ.copy()
    env["PERL5LIB"] = str(ALTIUM2KICAD_DIR)
    return env


def _find_generated_native_schematic(run_dir: Path, input_path: Path) -> Path:
    preferred = [
        run_dir / f"{input_path.stem}-SchDoc.sch",
        run_dir / f"{input_path.name}.sch",
    ]
    for candidate in preferred:
        if candidate.exists():
            return candidate
    fallback_matches = sorted(run_dir.glob("*.sch"))
    if fallback_matches:
        return fallback_matches[0]
    return preferred[0]


def _find_generated_native_cache_lib(run_dir: Path, input_path: Path) -> Path:
    preferred = [
        run_dir / f"{input_path.stem}-SchDoc-cache.lib",
        run_dir / f"{input_path.name}-cache.lib",
    ]
    for candidate in preferred:
        if candidate.exists():
            return candidate
    fallback_matches = sorted(run_dir.glob("*-cache.lib"))
    if fallback_matches:
        return fallback_matches[0]
    return preferred[0]


def _repair_schematic_text(text: str) -> str:
    repaired_lines = []
    for line in text.splitlines():
        repaired_lines.append(_repair_mojibake_line(line))
    return "\n".join(repaired_lines) + ("\n" if text.endswith("\n") else "")


def _repair_mojibake_line(line: str) -> str:
    if not line:
        return line
    if not any(128 <= ord(char) <= 255 for char in line):
        return line
    try:
        repaired = line.encode("latin1").decode("gbk")
    except UnicodeEncodeError:
        return line
    except UnicodeDecodeError:
        return line

    # Prefer the repaired line only when it clearly introduces meaningful CJK text.
    cjk_count = sum(1 for char in repaired if "\u4e00" <= char <= "\u9fff")
    if cjk_count == 0:
        return line
    return repaired

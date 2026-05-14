from pathlib import Path
import json

import pytest
from fastapi.testclient import TestClient

from eda2kicad.web.app import app
from tests._paths import ALTIUM2KICAD_TESTS


def test_root_page_exposes_strategy_selector() -> None:
    response = TestClient(app).get("/")

    assert response.status_code == 200
    assert 'history.replaceState({}, "", "/");' not in response.text
    assert "拖拽文件到这里" in response.text
    assert 'id="input-dropzone"' in response.text
    assert 'option value="custom"' in response.text
    assert 'option value="kicad-official"' in response.text
    assert 'option value="kicad-gui-official"' in response.text
    assert 'option value="pcbnew-api"' in response.text
    assert 'option value="third-party"' in response.text
    assert "支持 PCB 图，效果较好，未来可能不再支持。" in response.text
    assert "支持原理图、PCB 图，效果较好，但稳定性差，不适合作为长期策略。" in response.text
    assert "支持 PCB 图，暂不可用，理论最佳策略，需等待官方进一步支持。" in response.text
    assert "来源：altium2kicad。支持原理图、PCB 图，原理图效果差，PCB 效果较好。" in response.text
    assert "支持原理图，效果极差，待开发。" in response.text
    assert 'class="strategy-summary"' in response.text
    assert 'class="strategy-meta"' in response.text
    assert 'name="input_path" type="text"' in response.text
    assert 'name="output_dir" type="text"' in response.text
    assert 'name="input_path" type="text" value=' not in response.text
    assert 'name="output_dir" type="text" value=' not in response.text
    assert 'placeholder="C:\\\\path\\\\to\\\\file.SchDoc"' not in response.text
    assert 'placeholder="C:\\\\path\\\\to\\\\output"' not in response.text

    order = [
        response.text.index('option value="pcbnew-api"'),
        response.text.index('option value="kicad-gui-official"'),
        response.text.index('option value="kicad-official"'),
        response.text.index('option value="third-party"'),
        response.text.index('option value="custom"'),
    ]
    assert order == sorted(order)


def test_conversion_form_uses_selected_strategy(tmp_path: Path) -> None:
    input_file = tmp_path / "demo.txt"
    input_file.write_text("RECORD=NET_LABEL\nTEXT=NET_A\nX=100\nY=0\n", encoding="utf-8")
    output_dir = tmp_path / "output"

    response = TestClient(app).post(
        "/convert",
        data={
            "input_path": str(input_file),
            "output_dir": str(output_dir),
            "strategy": "third-party",
        },
    )

    assert response.status_code == 400
    assert "only native Altium inputs are supported" in response.text


@pytest.mark.parametrize("output_dir_value", [None, "   "])
def test_conversion_form_requires_output_dir(
    tmp_path: Path,
    output_dir_value: str | None,
) -> None:
    input_file = tmp_path / "demo.txt"
    input_file.write_text("RECORD=NET_LABEL\nTEXT=NET_A\nX=100\nY=0\n", encoding="utf-8")

    data: dict[str, str] = {
        "input_path": str(input_file),
        "strategy": "custom",
    }
    if output_dir_value is not None:
        data["output_dir"] = output_dir_value

    response = TestClient(app).post("/convert", data=data)

    assert response.status_code == 400
    assert "output_dir" in response.text
    assert "不能为空" in response.text


def test_conversion_form_rejects_unknown_strategy(tmp_path: Path) -> None:
    input_file = tmp_path / "demo.SchDoc"
    input_file.write_bytes(b"dummy schdoc")
    output_dir = tmp_path / "output"

    response = TestClient(app).post(
        "/convert",
        data={
            "input_path": str(input_file),
            "output_dir": str(output_dir),
            "strategy": "unknown",
        },
    )

    assert response.status_code == 400
    assert "unknown strategy: unknown" in response.text


def test_conversion_form_renders_internal_errors_as_page_message(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from eda2kicad import web as web_package

    input_file = tmp_path / "demo.txt"
    input_file.write_text("RECORD=NET_LABEL\nTEXT=NET_A\nX=100\nY=0\n", encoding="utf-8")
    output_dir = tmp_path / "output"

    class FailingService:
        def available_strategies(self) -> list[dict[str, object]]:
            return [
                {
                    "strategy_id": "custom",
                    "mode": "primary",
                    "uses_kicad_capability": False,
                    "uses_external_project": False,
                    "status": "active",
                }
            ]

        def convert_file(self, input_path: Path, output_dir: Path, strategy: str = "custom") -> dict[str, Path]:
            del input_path, output_dir, strategy
            raise RuntimeError("boom")

    monkeypatch.setattr(web_package.app, "_service", lambda: FailingService())

    response = TestClient(app, raise_server_exceptions=False).post(
        "/convert",
        data={
            "input_path": str(input_file),
            "output_dir": str(output_dir),
            "strategy": "custom",
        },
    )

    assert response.status_code == 500
    assert "RuntimeError: boom" in response.text
    assert 'history.replaceState({}, "", "/");' in response.text


def test_conversion_form_requires_paths() -> None:
    response = TestClient(app).post("/convert", data={"strategy": "custom"})

    assert response.status_code == 400
    assert "input_path" in response.text
    assert "output_dir" in response.text


def test_conversion_form_accepts_uploaded_native_file(
    tmp_path: Path,
    monkeypatch,
) -> None:
    import subprocess

    from eda2kicad.strategies import third_party

    uploaded_file = tmp_path / "demo.PcbDoc"
    uploaded_file.write_bytes(b"dummy pcbdoc")
    output_dir = tmp_path / "output"

    def fake_run(command: list[str], cwd: Path, env: dict[str, str]) -> subprocess.CompletedProcess[str]:
        del env
        if command[1] == "unpack.pl":
            (cwd / "demo.PcbDoc").write_bytes(uploaded_file.read_bytes())
            (cwd / "demo-PcbDoc").mkdir(parents=True, exist_ok=True)
        elif command[1] == "convertpcb.pl":
            (cwd / "demo-PcbDoc.kicad_pcb").write_text(
                "(kicad_pcb (version 20231120) (generator pcbnew))\n",
                encoding="utf-8",
            )
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr(third_party, "_run_command", fake_run)

    with uploaded_file.open("rb") as handle:
        response = TestClient(app).post(
            "/convert",
            data={"output_dir": str(output_dir), "strategy": "third-party"},
            files={"input_file": ("demo.PcbDoc", handle, "application/octet-stream")},
        )

    assert response.status_code == 200
    assert "demo.kicad_pcb" in response.text
    job_dirs = [path for path in output_dir.iterdir() if path.is_dir()]
    assert len(job_dirs) == 1
    assert any(path.name == "demo.kicad_pcb" for path in job_dirs[0].iterdir())


def test_conversion_form_renders_board_result_for_native_pcb(
    tmp_path: Path,
    monkeypatch,
) -> None:
    from eda2kicad.strategies import kicad_official

    input_file = ALTIUM2KICAD_TESTS / "via2.PcbDoc"
    output_dir = tmp_path / "output"

    def fake_import(
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
                "strategy": kicad_official.get_strategy_metadata(),
            },
        }

    monkeypatch.setattr(kicad_official, "convert_native_pcb", fake_import)

    response = TestClient(app).post(
        "/convert",
        data={
            "input_path": str(input_file),
            "output_dir": str(output_dir),
            "strategy": "kicad-official",
        },
    )

    assert response.status_code == 200
    assert "via2.kicad_pcb" in response.text
    assert "via2.kicad_pro" in response.text


def test_conversion_form_renders_board_result_for_pcbnew_api_native_pcb(
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

    response = TestClient(app).post(
        "/convert",
        data={
            "input_path": str(input_file),
            "output_dir": str(output_dir),
            "strategy": "pcbnew-api",
        },
    )

    assert response.status_code == 200
    assert "via2.kicad_pcb" in response.text
    assert "via2.kicad_pro" in response.text


def test_conversion_form_renders_schematic_result_for_gui_native_schematic(
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

    response = TestClient(app).post(
        "/convert",
        data={
            "input_path": str(input_file),
            "output_dir": str(output_dir),
            "strategy": "kicad-gui-official",
        },
    )

    assert response.status_code == 200
    assert "via2.kicad_sch" in response.text
    assert "via2.kicad_pro" in response.text


def test_conversion_form_renders_board_result_for_gui_native_pcb(
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

    response = TestClient(app).post(
        "/convert",
        data={
            "input_path": str(input_file),
            "output_dir": str(output_dir),
            "strategy": "kicad-gui-official",
        },
    )

    assert response.status_code == 200
    assert "via2.kicad_pcb" in response.text
    assert "via2.kicad_pro" in response.text

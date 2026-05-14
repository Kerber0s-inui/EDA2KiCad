from pathlib import Path

import json
import subprocess
import pytest

from eda2kicad.service import ConversionService
from tests._paths import ALTIUM2KICAD_TESTS


def test_conversion_service_passes_output_dir_to_strategy_runner(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from eda2kicad import service as service_module

    input_file = tmp_path / "demo.SchDoc"
    input_file.write_bytes(b"dummy schdoc")
    output_dir = tmp_path / "user-output"
    seen: dict[str, Path] = {}

    def fake_runner(input_path: Path, mapping_path: Path, requested_output_dir: Path | None) -> dict[str, object]:
        seen["input_path"] = input_path
        seen["mapping_path"] = mapping_path
        if requested_output_dir is not None:
            seen["output_dir"] = requested_output_dir
        return {
            "project_name": "demo",
            "schematic_text": "(kicad_sch (version 20231120))\n",
            "schematic_extension": ".kicad_sch",
            "board_text": None,
            "board_extension": None,
            "auxiliary_text_artifacts": {},
            "report": {"strategy": {"strategy_id": "fake"}},
        }

    monkeypatch.setitem(
        service_module.STRATEGIES,
        "fake",
        (
            {
                "strategy_id": "fake",
                "mode": "candidate",
                "uses_kicad_capability": False,
                "uses_external_project": False,
                "status": "active",
            },
            fake_runner,
        ),
    )

    service = ConversionService(tmp_path / "mapping.json")
    artifacts = service.convert_file(input_file, output_dir, strategy="fake")

    assert seen["input_path"] == input_file
    assert seen["mapping_path"] == tmp_path / "mapping.json"
    assert seen["output_dir"].parent == output_dir
    assert artifacts["job_dir"] == seen["output_dir"]
    assert artifacts["report"].parent == artifacts["job_dir"]


def test_conversion_service_writes_outputs_under_job_subdirectory(tmp_path: Path) -> None:
    from eda2kicad import service as service_module

    repo_root = Path(__file__).resolve().parents[1]
    input_file = tmp_path / "demo.SchDoc"
    input_file.write_bytes(b"dummy schdoc")
    output_dir = tmp_path / "output"
    service = ConversionService(repo_root / "libraries" / "local_symbol_map.json")

    def fake_runner(input_path: Path, mapping_path: Path, requested_output_dir: Path | None) -> dict[str, object]:
        del input_path, mapping_path
        assert requested_output_dir is not None
        return {
            "project_name": "demo",
            "schematic_text": "(kicad_sch (version 20231120))\n",
            "schematic_extension": ".kicad_sch",
            "board_text": None,
            "board_extension": None,
            "auxiliary_text_artifacts": {},
            "report": {"strategy": {"strategy_id": "fake"}},
        }

    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setitem(
        service_module.STRATEGIES,
        "fake",
        (
            {
                "strategy_id": "fake",
                "mode": "candidate",
                "uses_kicad_capability": False,
                "uses_external_project": False,
                "status": "active",
            },
            fake_runner,
        ),
    )

    try:
        artifacts = service.convert_file(input_file, output_dir, strategy="fake")
    finally:
        monkeypatch.undo()

    assert artifacts["job_dir"].parent == output_dir
    assert artifacts["schematic"].parent == artifacts["job_dir"]
    assert artifacts["report"].parent == artifacts["job_dir"]
    assert not (output_dir / "demo.kicad_sch").exists()
    assert not (output_dir / "report.json").exists()


def test_conversion_service_removes_intermediate_job_directories_from_final_output(tmp_path: Path) -> None:
    from eda2kicad import service as service_module

    repo_root = Path(__file__).resolve().parents[1]
    input_file = tmp_path / "demo.SchDoc"
    input_file.write_bytes(b"dummy schdoc")
    output_dir = tmp_path / "output"
    service = ConversionService(repo_root / "libraries" / "local_symbol_map.json")

    def fake_runner(input_path: Path, mapping_path: Path, requested_output_dir: Path | None) -> dict[str, object]:
        del input_path, mapping_path
        assert requested_output_dir is not None
        return {
            "project_name": "demo",
            "schematic_text": "(kicad_sch (version 20231120))\n",
            "schematic_extension": ".kicad_sch",
            "board_text": None,
            "board_extension": None,
            "auxiliary_text_artifacts": {},
            "report": {"strategy": {"strategy_id": "fake"}},
        }

    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setitem(
        service_module.STRATEGIES,
        "fake",
        (
            {
                "strategy_id": "fake",
                "mode": "candidate",
                "uses_kicad_capability": False,
                "uses_external_project": False,
                "status": "active",
            },
            fake_runner,
        ),
    )

    try:
        artifacts = service.convert_file(input_file, output_dir, strategy="fake")
    finally:
        monkeypatch.undo()

    assert not (artifacts["job_dir"] / "input").exists()
    assert not (artifacts["job_dir"] / "temp").exists()
    assert not (artifacts["job_dir"] / ".eda2kicad").exists()
    assert artifacts["schematic"].exists()
    assert artifacts["report"].exists()


def test_conversion_service_converts_zip_with_pcbdoc_and_schdoc_into_one_job_dir(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import zipfile

    from eda2kicad import service as service_module

    archive_path = tmp_path / "bundle.zip"
    with zipfile.ZipFile(archive_path, "w") as archive:
        archive.writestr("demo.PcbDoc", "board")
        archive.writestr("demo.SchDoc", "schematic")

    seen_inputs: list[Path] = []

    def fake_runner(input_path: Path, mapping_path: Path, requested_output_dir: Path | None) -> dict[str, object]:
        del mapping_path
        assert requested_output_dir is not None
        seen_inputs.append(input_path)
        if input_path.suffix.lower() == ".pcbdoc":
            return {
                "project_name": "demo",
                "schematic_text": None,
                "schematic_extension": None,
                "board_text": "(kicad_pcb (version 20231120))\n",
                "board_extension": ".kicad_pcb",
                "auxiliary_text_artifacts": {},
                "report": {"strategy": {"strategy_id": "fake"}, "kind": "board"},
            }
        return {
            "project_name": "demo",
            "schematic_text": "(kicad_sch (version 20231120))\n",
            "schematic_extension": ".kicad_sch",
            "board_text": None,
            "board_extension": None,
            "auxiliary_text_artifacts": {},
            "report": {"strategy": {"strategy_id": "fake"}, "kind": "schematic"},
        }

    monkeypatch.setitem(
        service_module.STRATEGIES,
        "fake",
        (
            {
                "strategy_id": "fake",
                "mode": "candidate",
                "uses_kicad_capability": False,
                "uses_external_project": False,
                "status": "active",
            },
            fake_runner,
        ),
    )

    service = ConversionService(tmp_path / "mapping.json")
    artifacts = service.convert_file(archive_path, tmp_path / "out", strategy="fake")
    report = json.loads(artifacts["report"].read_text(encoding="utf-8"))

    assert len(seen_inputs) == 2
    assert artifacts["board"].parent == artifacts["job_dir"]
    assert artifacts["schematic"].parent == artifacts["job_dir"]
    assert artifacts["project"].parent == artifacts["job_dir"]
    assert report["job"]["input_mode"] == "zip-archive"
    assert report["job"]["job_mode"] == "shared-empty-project"
    assert report["runs"]["board"]["kind"] == "board"
    assert report["runs"]["schematic"]["kind"] == "schematic"


def test_conversion_service_records_selected_strategy_in_report(tmp_path: Path) -> None:
    from eda2kicad.strategies import third_party

    repo_root = Path(__file__).resolve().parents[1]
    input_file = ALTIUM2KICAD_TESTS / "via2.SchDoc"
    output_dir = tmp_path / "output"
    service = ConversionService(repo_root / "libraries" / "local_symbol_map.json")

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

    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(third_party, "_run_command", fake_run)

    try:
        artifacts = service.convert_file(input_file, output_dir, strategy="third-party")
    finally:
        monkeypatch.undo()

    report = json.loads(artifacts["report"].read_text(encoding="utf-8"))

    assert report["strategy"]["strategy_id"] == "third-party"


def test_conversion_service_tolerates_cleanup_permission_errors(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from eda2kicad import service as service_module

    input_file = tmp_path / "demo.SchDoc"
    input_file.write_bytes(b"dummy schdoc")
    output_dir = tmp_path / "output"

    def fake_runner(input_path: Path, mapping_path: Path, requested_output_dir: Path | None) -> dict[str, object]:
        del input_path, mapping_path
        assert requested_output_dir is not None
        return {
            "project_name": "demo",
            "schematic_text": "(kicad_sch (version 20231120))\n",
            "schematic_extension": ".kicad_sch",
            "board_text": None,
            "board_extension": None,
            "auxiliary_text_artifacts": {},
            "report": {"strategy": {"strategy_id": "fake"}},
        }

    def fake_cleanup(workspace_root: Path, *, extra_paths=()) -> list[str]:
        del workspace_root, extra_paths
        return ["cleanup warning"]

    monkeypatch.setitem(
        service_module.STRATEGIES,
        "fake",
        (
            {
                "strategy_id": "fake",
                "mode": "candidate",
                "uses_kicad_capability": False,
                "uses_external_project": False,
                "status": "active",
            },
            fake_runner,
        ),
    )
    monkeypatch.setattr(service_module, "cleanup_intermediate_artifacts", fake_cleanup)

    service = ConversionService(tmp_path / "mapping.json")
    artifacts = service.convert_file(input_file, output_dir, strategy="fake")
    report = json.loads(artifacts["report"].read_text(encoding="utf-8"))

    assert artifacts["schematic"].exists()
    assert report["cleanup"]["warnings"] == ["cleanup warning"]


def test_conversion_service_rejects_ascii_schematic_text_input(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    input_file = tmp_path / "demo.txt"
    input_file.write_text(
        "RECORD=COMPONENT\n"
        "DESIGNATOR=R1\n"
        "LIBRARY=RES_0603\n"
        "VALUE=10k\n"
        "FOOTPRINT=Resistor_SMD:R_0603_1608Metric\n\n"
        "RECORD=NET_LABEL\n"
        "TEXT=NET_A\n"
        "X=100\n"
        "Y=0\n",
        encoding="utf-8",
    )
    service = ConversionService(repo_root / "libraries" / "local_symbol_map.json")

    with pytest.raises(ValueError, match="only native Altium inputs are supported"):
        service.convert_file(input_file, tmp_path / "custom", strategy="custom")


def test_kicad_official_strategy_imports_native_pcbdoc_to_kicad_pcb(
    tmp_path: Path,
    monkeypatch,
) -> None:
    from eda2kicad.strategies import kicad_official

    repo_root = Path(__file__).resolve().parents[1]
    input_file = ALTIUM2KICAD_TESTS / "via2.PcbDoc"
    output_dir = tmp_path / "official-pcb"
    service = ConversionService(repo_root / "libraries" / "local_symbol_map.json")

    def fake_run(command: list[str]) -> subprocess.CompletedProcess[str]:
        output_index = command.index("--output") + 1
        report_index = command.index("--report-file") + 1
        output_path = Path(command[output_index])
        report_path = Path(command[report_index])
        output_path.write_text("(kicad_pcb (version 20231120) (generator pcbnew))\n", encoding="utf-8")
        report_path.write_text('{"issues":[],"summary":{"error_count":0,"warning_count":0}}', encoding="utf-8")
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr(kicad_official, "_run_kicad_cli", fake_run)

    artifacts = service.convert_file(input_file, output_dir, strategy="kicad-official")

    assert "board" in artifacts
    assert artifacts["board"].suffix == ".kicad_pcb"
    assert artifacts["board"].exists()


def test_pcbnew_api_strategy_imports_native_pcbdoc_to_kicad_pcb(
    tmp_path: Path,
    monkeypatch,
) -> None:
    from eda2kicad.strategies import pcbnew_api

    repo_root = Path(__file__).resolve().parents[1]
    input_file = ALTIUM2KICAD_TESTS / "via2.PcbDoc"
    output_dir = tmp_path / "pcbnew-api-pcb"
    service = ConversionService(repo_root / "libraries" / "local_symbol_map.json")

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

    artifacts = service.convert_file(input_file, output_dir, strategy="pcbnew-api")
    report = json.loads(artifacts["report"].read_text(encoding="utf-8"))

    assert "board" in artifacts
    assert artifacts["board"].suffix == ".kicad_pcb"
    assert artifacts["board"].exists()
    assert artifacts["project"].suffix == ".kicad_pro"
    assert report["strategy"]["strategy_id"] == "pcbnew-api"


def test_kicad_gui_official_strategy_imports_native_pcbdoc_to_kicad_pcb(
    tmp_path: Path,
    monkeypatch,
) -> None:
    from eda2kicad.strategies import kicad_gui_official

    repo_root = Path(__file__).resolve().parents[1]
    input_file = ALTIUM2KICAD_TESTS / "via2.PcbDoc"
    output_dir = tmp_path / "gui-official-pcb"
    service = ConversionService(repo_root / "libraries" / "local_symbol_map.json")

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
                "automation": {
                    "phase": "completed",
                    "last_action": "save_output",
                },
                "strategy": kicad_gui_official.get_strategy_metadata(),
            },
        }

    monkeypatch.setattr(kicad_gui_official, "convert_native_pcb", fake_convert_native_pcb)

    artifacts = service.convert_file(input_file, output_dir, strategy="kicad-gui-official")
    report = json.loads(artifacts["report"].read_text(encoding="utf-8"))

    assert "board" in artifacts
    assert artifacts["board"].suffix == ".kicad_pcb"
    assert artifacts["board"].exists()
    assert artifacts["project"].suffix == ".kicad_pro"
    assert report["strategy"]["strategy_id"] == "kicad-gui-official"
    assert report["automation"]["phase"] == "completed"


def test_kicad_gui_official_strategy_imports_native_schdoc_to_kicad_schematic(
    tmp_path: Path,
    monkeypatch,
) -> None:
    from eda2kicad.strategies import kicad_gui_official

    repo_root = Path(__file__).resolve().parents[1]
    input_file = ALTIUM2KICAD_TESTS / "via2.SchDoc"
    output_dir = tmp_path / "gui-official-sch"
    service = ConversionService(repo_root / "libraries" / "local_symbol_map.json")

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
                "automation": {
                    "phase": "completed",
                    "last_action": "save_schematic_output",
                },
                "strategy": kicad_gui_official.get_strategy_metadata(),
            },
        }

    monkeypatch.setattr(kicad_gui_official, "convert_native_schematic", fake_convert_native_schematic)

    artifacts = service.convert_file(input_file, output_dir, strategy="kicad-gui-official")
    report = json.loads(artifacts["report"].read_text(encoding="utf-8"))

    assert "schematic" in artifacts
    assert artifacts["schematic"].suffix == ".kicad_sch"
    assert artifacts["schematic"].exists()
    assert artifacts["project"].suffix == ".kicad_pro"
    assert report["strategy"]["strategy_id"] == "kicad-gui-official"
    assert report["automation"]["last_action"] == "save_schematic_output"


def test_conversion_service_uses_gui_bundle_for_zip_with_pcbdoc_and_schdoc(
    tmp_path: Path,
    monkeypatch,
) -> None:
    import zipfile

    from eda2kicad.strategies import kicad_gui_official

    repo_root = Path(__file__).resolve().parents[1]
    archive_path = tmp_path / "bundle.zip"
    with zipfile.ZipFile(archive_path, "w") as archive:
        archive.writestr("demo.PcbDoc", "board")
        archive.writestr("demo.SchDoc", "schematic")

    seen: dict[str, object] = {}

    def fake_convert_native_bundle(
        *,
        pcb_input: Path | None,
        schematic_input: Path | None,
        project_input: Path | None = None,
        output_root: Path | None = None,
    ) -> dict[str, object]:
        seen["pcb_input"] = pcb_input
        seen["schematic_input"] = schematic_input
        seen["project_input"] = project_input
        seen["output_root"] = output_root
        return {
            "project_name": "demo",
            "schematic_text": "(kicad_sch (version 20231120) (generator eeschema))\n",
            "schematic_extension": ".kicad_sch",
            "board_text": "(kicad_pcb (version 20231120) (generator pcbnew))\n",
            "board_extension": ".kicad_pcb",
            "auxiliary_text_artifacts": {
                "demo.kicad_pro": "{\n  \"meta\": {\"version\": 1}\n}\n",
            },
            "report": {
                "summary": {"error_count": 0, "warning_count": 0},
                "issues": [],
                "automation": {"phase": "completed"},
                "strategy": kicad_gui_official.get_strategy_metadata(),
            },
        }

    monkeypatch.setattr(kicad_gui_official, "convert_native_bundle", fake_convert_native_bundle)

    service = ConversionService(repo_root / "libraries" / "local_symbol_map.json")
    artifacts = service.convert_file(archive_path, tmp_path / "out", strategy="kicad-gui-official")
    report = json.loads(artifacts["report"].read_text(encoding="utf-8"))

    assert seen["project_input"] is None
    assert isinstance(seen["pcb_input"], Path)
    assert isinstance(seen["schematic_input"], Path)
    assert seen["output_root"] == artifacts["job_dir"]
    assert artifacts["board"].parent == artifacts["job_dir"]
    assert artifacts["schematic"].parent == artifacts["job_dir"]
    assert artifacts["project"].parent == artifacts["job_dir"]
    assert report["job"]["job_mode"] == "shared-empty-project"
    assert report["strategy"]["strategy_id"] == "kicad-gui-official"


def test_conversion_service_uses_gui_bundle_for_zip_with_project_triplet(
    tmp_path: Path,
    monkeypatch,
) -> None:
    import zipfile

    from eda2kicad.strategies import kicad_gui_official

    repo_root = Path(__file__).resolve().parents[1]
    archive_path = tmp_path / "bundle.zip"
    with zipfile.ZipFile(archive_path, "w") as archive:
        archive.writestr("nested/demo.PrjPcb", "project")
        archive.writestr("nested/demo.PcbDoc", "board")
        archive.writestr("nested/demo.SchDoc", "schematic")

    seen: dict[str, object] = {}

    def fake_convert_native_bundle(
        *,
        pcb_input: Path | None,
        schematic_input: Path | None,
        project_input: Path | None = None,
        output_root: Path | None = None,
    ) -> dict[str, object]:
        seen["pcb_input"] = pcb_input
        seen["schematic_input"] = schematic_input
        seen["project_input"] = project_input
        seen["output_root"] = output_root
        return {
            "project_name": "demo",
            "schematic_text": "(kicad_sch (version 20231120) (generator eeschema))\n",
            "schematic_extension": ".kicad_sch",
            "board_text": "(kicad_pcb (version 20231120) (generator pcbnew))\n",
            "board_extension": ".kicad_pcb",
            "auxiliary_text_artifacts": {
                "demo.kicad_pro": "{\n  \"meta\": {\"version\": 1}\n}\n",
            },
            "report": {
                "summary": {"error_count": 0, "warning_count": 0},
                "issues": [],
                "automation": {"phase": "completed"},
                "strategy": kicad_gui_official.get_strategy_metadata(),
            },
        }

    monkeypatch.setattr(kicad_gui_official, "convert_native_bundle", fake_convert_native_bundle)

    service = ConversionService(repo_root / "libraries" / "local_symbol_map.json")
    artifacts = service.convert_file(archive_path, tmp_path / "out", strategy="kicad-gui-official")
    report = json.loads(artifacts["report"].read_text(encoding="utf-8"))

    assert isinstance(seen["project_input"], Path)
    assert isinstance(seen["pcb_input"], Path)
    assert isinstance(seen["schematic_input"], Path)
    assert seen["output_root"] == artifacts["job_dir"]
    assert artifacts["project"].parent == artifacts["job_dir"]
    assert report["job"]["job_mode"] == "reuse-project"
    assert report["strategy"]["strategy_id"] == "kicad-gui-official"


def test_third_party_strategy_imports_native_schdoc_to_kicad_schematic(
    tmp_path: Path,
    monkeypatch,
) -> None:
    from eda2kicad.strategies import third_party

    repo_root = Path(__file__).resolve().parents[1]
    input_file = ALTIUM2KICAD_TESTS / "via2.SchDoc"
    output_dir = tmp_path / "third-party-sch"
    service = ConversionService(repo_root / "libraries" / "local_symbol_map.json")

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

    artifacts = service.convert_file(input_file, output_dir, strategy="third-party")

    assert "schematic" in artifacts
    assert artifacts["schematic"].suffix == ".sch"
    assert artifacts["schematic"].exists()
    assert "cache_lib" not in artifacts
    assert not list(artifacts["job_dir"].glob("*-cache.lib"))


def test_third_party_strategy_accepts_lowercase_native_schdoc_output_names(
    tmp_path: Path,
    monkeypatch,
) -> None:
    from eda2kicad.strategies import third_party

    repo_root = Path(__file__).resolve().parents[1]
    input_file = tmp_path / "via2.schdoc"
    input_file.write_bytes((ALTIUM2KICAD_TESTS / "via2.SchDoc").read_bytes())
    output_dir = tmp_path / "third-party-sch-lowercase"
    service = ConversionService(repo_root / "libraries" / "local_symbol_map.json")

    def fake_run(command: list[str], cwd: Path, env: dict[str, str]) -> subprocess.CompletedProcess[str]:
        del env
        if command[1] == "unpack.pl":
            (cwd / "via2.schdoc").write_bytes(input_file.read_bytes())
            (cwd / "via2-schdoc").mkdir(parents=True, exist_ok=True)
        elif command[1] == "convertschema.pl":
            (cwd / "via2.schdoc.sch").write_text(
                '(kicad_sch (version 20231120) (generator third-party))\n',
                encoding="utf-8",
            )
            (cwd / "via2.schdoc-cache.lib").write_text("EESchema-LIBRARY Version 2.4\n", encoding="utf-8")
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr(third_party, "_run_command", fake_run)

    artifacts = service.convert_file(input_file, output_dir, strategy="third-party")

    assert artifacts["schematic"].suffix == ".sch"
    assert artifacts["schematic"].exists()
    assert "cache_lib" not in artifacts
    assert not list(artifacts["job_dir"].glob("*-cache.lib"))


def test_third_party_strategy_repairs_gbk_mojibake_in_native_schematic_outputs(
    tmp_path: Path,
    monkeypatch,
) -> None:
    from eda2kicad.strategies import third_party

    repo_root = Path(__file__).resolve().parents[1]
    input_file = ALTIUM2KICAD_TESTS / "via2.SchDoc"
    output_dir = tmp_path / "third-party-sch-repaired"
    service = ConversionService(repo_root / "libraries" / "local_symbol_map.json")

    def fake_run(command: list[str], cwd: Path, env: dict[str, str]) -> subprocess.CompletedProcess[str]:
        del env
        if command[1] == "unpack.pl":
            (cwd / "via2.SchDoc").write_bytes(input_file.read_bytes())
            (cwd / "via2-SchDoc").mkdir(parents=True, exist_ok=True)
        elif command[1] == "convertschema.pl":
            (cwd / "via2-SchDoc.sch").write_text(
                'EESchema Schematic File Version 4\n'
                'Text Notes 0 0 0 60 ~ 0\n'
                'DCDC-5VÊä³ö\n'
                'F 1 "°×É«" H 0 0 60 0000 L BNN\n',
                encoding="utf-8",
            )
            (cwd / "via2-SchDoc-cache.lib").write_text(
                '# 4PINÁ¬½ÓÆ÷\nDEF 4PINÁ¬½ÓÆ÷ IC 0 40 Y Y 1 F N\n',
                encoding="utf-8",
            )
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr(third_party, "_run_command", fake_run)

    artifacts = service.convert_file(input_file, output_dir, strategy="third-party")

    schematic = artifacts["schematic"].read_text(encoding="utf-8")

    assert "DCDC-5V输出" in schematic
    assert '白色' in schematic
    assert "cache_lib" not in artifacts
    assert not list(artifacts["job_dir"].glob("*-cache.lib"))


def test_third_party_strategy_imports_native_pcbdoc_to_kicad_pcb(
    tmp_path: Path,
    monkeypatch,
) -> None:
    from eda2kicad.strategies import third_party

    repo_root = Path(__file__).resolve().parents[1]
    input_file = ALTIUM2KICAD_TESTS / "via2.PcbDoc"
    output_dir = tmp_path / "third-party-pcb"
    service = ConversionService(repo_root / "libraries" / "local_symbol_map.json")

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

    artifacts = service.convert_file(input_file, output_dir, strategy="third-party")

    assert "board" in artifacts
    assert artifacts["board"].suffix == ".kicad_pcb"
    assert artifacts["board"].exists()


def test_third_party_strategy_rejects_ascii_pcbdoc_with_clear_error(
    tmp_path: Path,
    monkeypatch,
) -> None:
    from eda2kicad.strategies import third_party

    repo_root = Path(__file__).resolve().parents[1]
    input_file = tmp_path / "ascii_board.PcbDoc"
    input_file.write_text("|RECORD=Board|LAYER=TOP|\n", encoding="utf-8")
    output_dir = tmp_path / "third-party-pcb-ascii"
    service = ConversionService(repo_root / "libraries" / "local_symbol_map.json")

    called = False

    def fake_run(command: list[str], cwd: Path, env: dict[str, str]) -> subprocess.CompletedProcess[str]:
        del command, cwd, env
        nonlocal called
        called = True
        return subprocess.CompletedProcess([], 0, "", "")

    monkeypatch.setattr(third_party, "_run_command", fake_run)

    try:
        service.convert_file(input_file, output_dir, strategy="third-party")
    except ValueError as exc:
        assert "ASCII .PcbDoc" in str(exc)
    else:
        raise AssertionError("expected third-party strategy to reject ASCII .PcbDoc input")

    assert called is False


def test_third_party_strategy_overrides_kicad_board_from_native_rules(
    tmp_path: Path,
    monkeypatch,
) -> None:
    from eda2kicad.strategies import third_party

    repo_root = Path(__file__).resolve().parents[1]
    input_file = ALTIUM2KICAD_TESTS / "via2.PcbDoc"
    output_dir = tmp_path / "third-party-pcb-overrides"
    service = ConversionService(repo_root / "libraries" / "local_symbol_map.json")

    def fake_run(command: list[str], cwd: Path, env: dict[str, str]) -> subprocess.CompletedProcess[str]:
        del env
        if command[1] == "unpack.pl":
            source_root = cwd / "via2-PcbDoc" / "Root Entry"
            (source_root / "Rules6").mkdir(parents=True, exist_ok=True)
            (source_root / "Classes6").mkdir(parents=True, exist_ok=True)
            (source_root / "Board6").mkdir(parents=True, exist_ok=True)
            (source_root / "Rules6" / "Data.dat.txt").write_text(
                "Pos: 0|LINENO=0||RULEKIND=Clearance|NAME=Clearance|GAP=11.811mil|"
                "PRIORITY=1\n"
                "Pos: 1|LINENO=1||RULEKIND=Width|NAME=Width|MINLIMIT=3.937mil|"
                "PREFEREDWIDTH=9.8425mil|PRIORITY=1\n"
                "Pos: 2|LINENO=2||RULEKIND=RoutingVias|NAME=RoutingVias|HOLEWIDTH=11.811mil|"
                "WIDTH=19.685mil|PRIORITY=1\n"
                "Model:\n",
                encoding="utf-8",
            )
            (source_root / "Classes6" / "Data.dat.txt").write_text(
                "Pos: 0|LINENO=0||NAME=Default|KIND=0|SUPERCLASS=FALSE|M0=NET1|M1=NET2\n"
                "Model:\n",
                encoding="utf-8",
            )
            (source_root / "Board6" / "Data.dat.txt").write_text("Model:\n", encoding="utf-8")
            (cwd / "via2-PcbDoc").mkdir(parents=True, exist_ok=True)
        elif command[1] == "convertpcb.pl":
            (cwd / "via2-PcbDoc.kicad_pcb").write_text(
                "(kicad_pcb (version 20231120) (generator pcbnew)\n"
                "  (setup\n"
                "    (trace_clearance 0.127)\n"
                "    (trace_min 0.127)\n"
                "    (via_size 0.889)\n"
                "    (via_drill 0.635)\n"
                "  )\n"
                "  (net_class Default \"Default\"\n"
                "    (clearance 0.127)\n"
                "    (trace_width 0.127)\n"
                "    (via_dia 0.889)\n"
                "    (via_drill 0.635)\n"
                "    (add_net \"NET1\")\n"
                "  )\n"
                ")\n",
                encoding="utf-8",
            )
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr(third_party, "_run_command", fake_run)

    artifacts = service.convert_file(input_file, output_dir, strategy="third-party")

    board_text = artifacts["board"].read_text(encoding="utf-8")
    report = json.loads(artifacts["report"].read_text(encoding="utf-8"))

    assert "trace_clearance 0.3" in board_text
    assert "trace_min 0.1" in board_text
    assert "via_size 0.5" in board_text
    assert "via_drill 0.3" in board_text
    assert artifacts["project"].suffix == ".kicad_pro"
    assert artifacts["project"].exists()
    assert report["design_rule_overrides"]["source"] == "third-party-native-rules"
    assert report["design_rule_overrides"]["board"]["trace_clearance"] == 0.3
    assert report["design_rule_overrides"]["net_classes"][0]["name"] == "Default"
    assert report["design_rule_overrides"]["net_classes"][0]["nets"] == ["NET1", "NET2"]


def test_third_party_strategy_rewrites_zone_and_edge_rules_from_native_board_rules(
    tmp_path: Path,
    monkeypatch,
) -> None:
    from eda2kicad.strategies import third_party

    repo_root = Path(__file__).resolve().parents[1]
    input_file = ALTIUM2KICAD_TESTS / "via2.PcbDoc"
    output_dir = tmp_path / "third-party-pcb-zone-rules"
    service = ConversionService(repo_root / "libraries" / "local_symbol_map.json")

    def fake_run(command: list[str], cwd: Path, env: dict[str, str]) -> subprocess.CompletedProcess[str]:
        del env
        if command[1] == "unpack.pl":
            source_root = cwd / "via2-PcbDoc" / "Root Entry"
            (source_root / "Rules6").mkdir(parents=True, exist_ok=True)
            (source_root / "Classes6").mkdir(parents=True, exist_ok=True)
            (source_root / "Board6").mkdir(parents=True, exist_ok=True)
            (source_root / "Rules6" / "Data.dat.txt").write_text(
                "Pos: 0|LINENO=0||RULEKIND=BoardOutlineClearance|NAME=BoardOutlineClearance|"
                "GAP=11.811mil|GENERICCLEARANCE=11.811mil|PRIORITY=1\n"
                "Pos: 1|LINENO=1||RULEKIND=PlaneClearance|NAME=PlaneClearance|"
                "CLEARANCE=20mil|PRIORITY=1\n"
                "Pos: 2|LINENO=2||RULEKIND=PolygonConnect|NAME=PolygonConnect|"
                "CONNECTSTYLE=Direct|RELIEFCONDUCTORWIDTH=10mil|RELIEFENTRIES=4|"
                "POLYGONRELIEFANGLE=90 Angle|AIRGAPWIDTH=10mil|PRIORITY=1\n"
                "Pos: 3|LINENO=3||RULEKIND=PlaneConnect|NAME=PlaneConnect|"
                "PLANECONNECTSTYLE=Direct|RELIEFEXPANSION=20mil|RELIEFENTRIES=4|"
                "RELIEFCONDUCTORWIDTH=10mil|RELIEFAIRGAP=10mil|PRIORITY=1\n"
                "Pos: 4|LINENO=4||RULEKIND=Clearance|NAME=Clearance|GAP=9.8425mil|PRIORITY=1\n"
                "Pos: 5|LINENO=5||RULEKIND=Width|NAME=Width|MINLIMIT=3.937mil|"
                "PREFEREDWIDTH=9.8425mil|PRIORITY=1\n"
                "Pos: 6|LINENO=6||RULEKIND=RoutingVias|NAME=RoutingVias|HOLEWIDTH=11.811mil|"
                "WIDTH=19.685mil|PRIORITY=1\n"
                "Model:\n",
                encoding="utf-8",
            )
            (source_root / "Classes6" / "Data.dat.txt").write_text("Model:\n", encoding="utf-8")
            (source_root / "Board6" / "Data.dat.txt").write_text("Model:\n", encoding="utf-8")
            (cwd / "via2-PcbDoc").mkdir(parents=True, exist_ok=True)
        elif command[1] == "convertpcb.pl":
            (cwd / "via2-PcbDoc.kicad_pcb").write_text(
                "(kicad_pcb (version 20231120) (generator pcbnew)\n"
                "  (setup\n"
                "    (trace_clearance 0.127)\n"
                "    (zone_clearance 0.127)\n"
                "    (trace_min 0.127)\n"
                "    (via_size 0.889)\n"
                "    (via_drill 0.635)\n"
                "  )\n"
                "  (zone (net 1) (net_name \"GND\") (layer F.Cu) (tstamp 1)\n"
                "    (connect_pads (clearance 0.127))\n"
                "    (min_thickness 0.254)\n"
                "    (fill (arc_segments 16) (thermal_gap 0.127) (thermal_bridge_width 0.127))\n"
                "  )\n"
                ")\n",
                encoding="utf-8",
            )
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr(third_party, "_run_command", fake_run)

    artifacts = service.convert_file(input_file, output_dir, strategy="third-party")

    board_text = artifacts["board"].read_text(encoding="utf-8")
    project_text = artifacts["project"].read_text(encoding="utf-8")
    report = json.loads(artifacts["report"].read_text(encoding="utf-8"))

    assert "zone_clearance 0.508" in board_text
    assert "(connect_pads (clearance 0.508))" in board_text
    assert "(thermal_gap 0.508)" in board_text
    assert "(thermal_bridge_width 0.254)" in board_text
    assert '"min_copper_edge_clearance": 0.3' in project_text
    assert report["design_rule_overrides"]["board"]["board_outline_clearance"] == 0.3
    assert report["design_rule_overrides"]["board"]["zone_clearance"] == 0.508
    assert report["design_rule_overrides"]["board"]["zone_thermal_gap"] == 0.508
    assert report["design_rule_overrides"]["board"]["zone_thermal_bridge_width"] == 0.254
    assert report["design_rule_overrides"]["board"]["zone_connection_style"] == "direct"


def test_third_party_strategy_exports_board_rule_overrides(
    tmp_path: Path,
    monkeypatch,
) -> None:
    from eda2kicad.strategies import third_party

    repo_root = Path(__file__).resolve().parents[1]
    input_file = ALTIUM2KICAD_TESTS / "via2.PcbDoc"
    output_dir = tmp_path / "third-party-pcb-rules"
    service = ConversionService(repo_root / "libraries" / "local_symbol_map.json")

    def fake_run(command: list[str], cwd: Path, env: dict[str, str]) -> subprocess.CompletedProcess[str]:
        del env
        if command[1] == "unpack.pl":
            (cwd / "via2.PcbDoc").write_bytes(input_file.read_bytes())
            (cwd / "via2-PcbDoc").mkdir(parents=True, exist_ok=True)
        elif command[1] == "convertpcb.pl":
            (cwd / "via2-PcbDoc.kicad_pcb").write_text(
                "(kicad_pcb (version 20231120) (generator pcbnew)\n"
                "  (setup\n"
                "    (trace_clearance 0.3)\n"
                "    (trace_min 0.2)\n"
                "    (via_size 0.9)\n"
                "    (via_drill 0.4)\n"
                "  )\n"
                "  (net_class Default \"Default\"\n"
                "    (clearance 0.3)\n"
                "    (trace_width 0.25)\n"
                "    (via_dia 0.9)\n"
                "    (via_drill 0.4)\n"
                "    (add_net \"NET1\")\n"
                "  )\n"
                ")\n",
                encoding="utf-8",
            )
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr(third_party, "_run_command", fake_run)

    artifacts = service.convert_file(input_file, output_dir, strategy="third-party")

    report = json.loads(artifacts["report"].read_text(encoding="utf-8"))

    assert artifacts["board"].exists()
    assert artifacts["project"].suffix == ".kicad_pro"
    assert artifacts["project"].exists()
    assert report["design_rule_overrides"]["source"] == "third-party-board-postprocess"
    assert report["design_rule_overrides"]["board"]["trace_clearance"] == 0.3
    assert report["design_rule_overrides"]["net_classes"][0]["name"] == "Default"


def test_custom_strategy_supports_native_schdoc_input(
    tmp_path: Path,
    monkeypatch,
) -> None:
    from eda2kicad import altium_native

    repo_root = Path(__file__).resolve().parents[1]
    input_file = ALTIUM2KICAD_TESTS / "via2.SchDoc"
    output_dir = tmp_path / "custom-native-sch"
    service = ConversionService(repo_root / "libraries" / "local_symbol_map.json")

    monkeypatch.setattr(
        altium_native,
        "unpack_native_file",
        lambda _input_path, _output_root: Path("C:/dev/EDA2KiCad/outputs/a2k-smoke-escalated/via2-SchDoc"),
    )

    artifacts = service.convert_file(input_file, output_dir, strategy="custom")

    schematic = artifacts["schematic"].read_text(encoding="utf-8")
    assert 'Q1' in schematic
    assert 'CompanyLib:RES_0603' not in schematic
    assert 'Generated:2N3904' in schematic

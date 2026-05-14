# EDA2KiCad

[中文说明 / Chinese documentation](README.zh-CN.md)

EDA2KiCad is an experimental toolkit for converting Altium design data into KiCad deliverables.
The repository currently contains multiple conversion strategies with different trade-offs in quality,
automation stability, and external tool requirements.

This project is suitable for internal evaluation, conversion experiments, and workflow prototyping.
It is not yet a zero-configuration, cross-platform production converter.

## Current Scope

- Schematic inputs:
  - Native Altium `.SchDoc`
- PCB inputs:
  - Native Altium `.PcbDoc`
- Bundle inputs:
  - `.PrjPcb`
  - `.zip` packages containing `.PrjPcb`, `.SchDoc`, and/or `.PcbDoc`
- Main outputs:
  - `.kicad_sch`
  - `.kicad_pcb`
  - `.kicad_pro`
  - `report.json`

## Strategy Status

| Strategy ID | Input support | Current output quality | Notes |
| --- | --- | --- | --- |
| `pcbnew-api` | PCB only | Good | Uses KiCad `pcbnew` Python API. Useful for unattended PCB conversion, but long-term upstream support is uncertain. |
| `kicad-gui-official` | Schematic + PCB | Good | Best practical quality in this repository, but depends on Windows desktop GUI automation and is not a stable long-term strategy. |
| `kicad-official` | PCB only | Currently unusable in practice | Theoretically the best future path if KiCad CLI import improves. |
| `third-party` | Schematic + PCB | Schematic poor, PCB good | Based on `altium2kicad`. Requires vendored third-party source and Perl. |
| `custom` | Schematic only | Very poor | In-house schematic path, not production-ready. |

## Third-Party Components and Licensing

This repository vendors the upstream `altium2kicad` project under [`vendor/altium2kicad`](vendor/altium2kicad)
for the `third-party` conversion strategy.

- Upstream project: `thesourcerer8/altium2kicad`
- Upstream repository: <https://github.com/thesourcerer8/altium2kicad>
- Local path: `vendor/altium2kicad`
- Upstream license: GPL-2.0
- Upstream license file: `vendor/altium2kicad/LICENSE`

Please review [`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md) before redistributing this repository.
The vendored third-party component remains subject to its original license terms.

## Runtime Requirements

### Required Python environment

- Python `3.11` or newer
- `pip`

### Required external tools

This repository is currently Windows-first in real-world usage because some tool paths are hard-coded in source.

- KiCad `10.0.x`
  - Expected paths in current code:
    - `C:\Program Files\KiCad\10.0\bin\kicad-cli.exe`
    - `C:\Program Files\KiCad\10.0\bin\python.exe`
    - `C:\Program Files\KiCad\10.0\bin\kicad.exe`
    - `C:\Program Files\KiCad\10.0\share\kicad\template\kicad.kicad_pro`
- Git for Windows Perl if you want to use `third-party`
  - Expected path:
    - `C:\Program Files\Git\usr\bin\perl.exe`
- Vendored `altium2kicad` source if you want to use `third-party`
  - Expected path:
    - `vendor/altium2kicad`

### Strategy-specific requirements

- `pcbnew-api`
  - Requires KiCad Python runtime
  - PCB only
- `kicad-gui-official`
  - Requires Windows
  - Requires an unlocked desktop session
  - Not suitable for headless server usage
- `kicad-official`
  - Requires KiCad CLI
  - PCB only
- `third-party`
  - Requires `vendor/altium2kicad`
  - Requires Perl
- `custom`
  - No extra external executable requirement beyond Python
  - Schematic only

## Installation

### Runtime installation

```bash
python -m pip install -r requirements.txt
```

### Development / test installation

```bash
python -m pip install -r requirements-dev.txt
```

On Windows, replace `python` with `py` if needed.

## Run the CLI

### PCB example

```bash
python -m eda2kicad.cli convert "C:\path\board.PcbDoc" --output "C:\path\output" --strategy pcbnew-api
```

### Schematic example

```bash
python -m eda2kicad.cli convert "C:\path\design.SchDoc" --output "C:\path\output" --strategy kicad-gui-official
```

### Bundle example

```bash
python -m eda2kicad.cli convert "C:\path\bundle.zip" --output "C:\path\output" --strategy kicad-gui-official
```

## Run the Local Web UI

```bash
python -m uvicorn eda2kicad.web.app:app --host 127.0.0.1 --port 8000
```

Then open [http://127.0.0.1:8000](http://127.0.0.1:8000).

## Run Tests

```bash
python -m pytest tests -q
```

## Recommended Strategy Usage

- For PCB conversion experiments:
  - Try `pcbnew-api` first for unattended execution
  - Try `kicad-gui-official` if you need better practical output quality and can accept GUI automation
- For schematic conversion:
  - `kicad-gui-official` currently gives the best practical output in this repository
  - `third-party` and `custom` should be treated as fallback or research-only paths

## Known Limitations

- Tool paths are still hard-coded to expected Windows locations in source.
- `kicad-gui-official` requires a real Windows desktop session and can be disturbed by GUI environment issues.
- `kicad-official` is still blocked by current KiCad CLI import limitations for practical usage.
- `pcbnew-api` may produce a valid `.kicad_pcb` while still exiting with warnings or abnormal return codes.
- `third-party` depends on the vendored `altium2kicad` repository and Perl.
- `custom` is not suitable for production schematic conversion.
- Converted outputs must still be reviewed in KiCad before engineering release or manufacturing use.

## Project Documentation

Additional release-oriented documentation is available in [`project_docs`](project_docs):

- [`GitHub_Runtime_Requirements_and_Reuse_Guide_EN.md`](project_docs/GitHub_Runtime_Requirements_and_Reuse_Guide_EN.md)
- [`GitHub_运行要求与复用说明.md`](project_docs/GitHub_%E8%BF%90%E8%A1%8C%E8%A6%81%E6%B1%82%E4%B8%8E%E5%A4%8D%E7%94%A8%E8%AF%B4%E6%98%8E.md)

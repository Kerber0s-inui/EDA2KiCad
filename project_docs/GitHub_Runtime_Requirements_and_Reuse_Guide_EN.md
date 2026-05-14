# GitHub Runtime Requirements and Reuse Guide

## Purpose

This document is a release-oriented companion to `README.md`.
It explains what someone must prepare before trying to reuse this repository.

## Required Local Assets

### 1. Repository contents

- This repository itself
- `vendor/altium2kicad` if you plan to use the `third-party` strategy

### 2. Required software

- Python 3.11+
- KiCad 10.0.x
- Git for Windows with Perl if you plan to use `third-party`

### 3. Current expected paths in source

The current codebase still assumes these Windows paths:

- `C:\Program Files\KiCad\10.0\bin\kicad-cli.exe`
- `C:\Program Files\KiCad\10.0\bin\python.exe`
- `C:\Program Files\KiCad\10.0\bin\kicad.exe`
- `C:\Program Files\KiCad\10.0\share\kicad\template\kicad.kicad_pro`
- `C:\Program Files\Git\usr\bin\perl.exe`

If your local installation differs, you currently need to update the source code manually.

## Reuse Checklist

- Install runtime dependencies:
  - `python -m pip install -r requirements.txt`
- For tests:
  - `python -m pip install -r requirements-dev.txt`
- Prepare supported native Altium inputs only:
  - `.SchDoc`
  - `.PcbDoc`
  - `.PrjPcb`
  - `.zip` bundles containing the files above
- Confirm KiCad is installed in the expected location
- Confirm `vendor/altium2kicad` exists if you want `third-party`
- Use `kicad-gui-official` only on an unlocked Windows desktop session

## Strategy-by-Strategy Notes

### `pcbnew-api`

- Best for unattended PCB conversion attempts
- Requires KiCad Python runtime
- Can produce a valid `.kicad_pcb` even when the import process exits with warnings

### `kicad-gui-official`

- Best practical quality for both schematic and PCB in this repository
- Requires Windows desktop automation
- Not suitable for headless CI or long-running server deployment

### `kicad-official`

- Depends on KiCad CLI
- PCB only
- Included mainly as an official reference path

### `third-party`

- Based on `altium2kicad`
- Requires `vendor/altium2kicad`
- Requires Perl
- PCB quality is usually better than schematic quality

### `custom`

- In-house schematic-only path
- Not production-grade

## Recommended Commands

### CLI

```bash
python -m eda2kicad.cli convert "C:\path\board.PcbDoc" --output "C:\path\out" --strategy pcbnew-api
```

### Web

```bash
python -m uvicorn eda2kicad.web.app:app --host 127.0.0.1 --port 8000
```

### Tests

```bash
python -m pytest tests -q
```

## Practical Release Message

If you publish this repository on GitHub, the most accurate description is:

- Windows-first
- Multi-strategy experimental converter
- Useful for evaluation and workflow prototyping
- Not yet a polished, universal conversion product

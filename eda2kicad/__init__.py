from __future__ import annotations

from pathlib import Path

__version__ = "0.1.0"

_PACKAGE_DIR = Path(__file__).resolve().parent
_SRC_PACKAGE_DIR = _PACKAGE_DIR.parent / "src" / "eda2kicad"

__path__ = [str(_PACKAGE_DIR)]
if _SRC_PACKAGE_DIR.is_dir():
    __path__.append(str(_SRC_PACKAGE_DIR))

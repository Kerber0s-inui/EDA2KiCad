from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Iterable


@dataclass(slots=True)
class WindowSnapshot:
    title: str
    class_name: str | None = None
    control_type: str | None = None
    automation_id: str | None = None
    children: list["WindowSnapshot"] = field(default_factory=list)


def dump_window_snapshot(snapshot: WindowSnapshot) -> dict[str, Any]:
    return asdict(snapshot)


def dump_windows(path: Path, windows: Iterable[WindowSnapshot | dict[str, Any]]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload: list[dict[str, Any]] = []
    for window in windows:
        payload.append(dump_window_snapshot(window) if isinstance(window, WindowSnapshot) else dict(window))
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return path

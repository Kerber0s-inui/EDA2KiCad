from __future__ import annotations

import json
from contextlib import suppress
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(slots=True)
class GuiAutomationRuntime:
    artifacts_dir: Path
    phase: str = "init"
    last_action: str | None = None
    log: list[str] = field(default_factory=list)
    debug: dict[str, Any] = field(default_factory=dict)
    log_path: Path | None = None
    screenshot_path: Path | None = None
    window_dump_path: Path | None = None
    failure_metadata: dict[str, Any] | None = None

    def set_phase(self, phase: str) -> None:
        self.phase = phase

    def log_step(self, action: str) -> None:
        self.last_action = action
        self.log.append(action)

    def record_debug_value(self, key: str, value: Any) -> None:
        self.debug[key] = value
        self.log.append(f"{key}={value}")

    def capture_screenshot(self, filename: str = "failure-screenshot.png", content: bytes | None = None) -> Path:
        self.artifacts_dir.mkdir(parents=True, exist_ok=True)
        screenshot_path = self.artifacts_dir / filename
        screenshot_path.write_bytes(content if content is not None else b"")
        self.screenshot_path = screenshot_path
        return screenshot_path

    def dump_windows(self, windows: list[dict[str, Any]] | None = None, filename: str = "window-dump.json") -> Path:
        self.artifacts_dir.mkdir(parents=True, exist_ok=True)
        window_dump_path = self.artifacts_dir / filename
        window_dump_path.write_text(json.dumps(windows or [], indent=2), encoding="utf-8")
        self.window_dump_path = window_dump_path
        return window_dump_path

    def record_failure(
        self,
        message: str,
        *,
        screenshot_path: Path | None = None,
        window_dump_path: Path | None = None,
        error_code: str | None = None,
        extra: dict[str, Any] | None = None,
    ) -> None:
        self.failure_metadata = {
            "message": message,
            "error_code": error_code,
            "extra": extra or {},
        }
        if screenshot_path is not None:
            self.screenshot_path = screenshot_path
        if window_dump_path is not None:
            self.window_dump_path = window_dump_path

    def write_log_file(self, filename: str = "automation.log") -> Path:
        self.artifacts_dir.mkdir(parents=True, exist_ok=True)
        log_path = self.artifacts_dir / filename
        log_path.write_text("\n".join(self.log), encoding="utf-8")
        self.log_path = log_path
        return log_path

    def to_report(self) -> dict[str, Any]:
        automation: dict[str, Any] = {
            "phase": self.phase,
            "last_action": self.last_action,
            "artifacts_dir": str(self.artifacts_dir),
            "steps": list(self.log),
        }
        if self.debug:
            automation["debug"] = dict(self.debug)
        if self.log_path is not None:
            automation["log"] = str(self.log_path)
        if self.screenshot_path is not None:
            automation["screenshot"] = str(self.screenshot_path)
        if self.window_dump_path is not None:
            automation["window_dump"] = str(self.window_dump_path)
        if self.failure_metadata is not None:
            automation["failure"] = dict(self.failure_metadata)
        return {"automation": automation}


def capture_gui_failure_diagnostics(runtime: GuiAutomationRuntime, driver: Any) -> None:
    with suppress(Exception):
        get_debug_snapshot = getattr(driver, "get_debug_snapshot", None)
        if callable(get_debug_snapshot):
            for key, value in dict(get_debug_snapshot()).items():
                runtime.record_debug_value(f"driver_{key}", value)

    with suppress(Exception):
        list_windows = getattr(driver, "list_desktop_windows", None)
        if callable(list_windows):
            runtime.dump_windows(list_windows())

    with suppress(Exception):
        from io import BytesIO

        from PIL import ImageGrab

        image = ImageGrab.grab(all_screens=True)
        buffer = BytesIO()
        image.save(buffer, format="PNG")
        content = buffer.getvalue()
        if content:
            runtime.capture_screenshot(content=content)

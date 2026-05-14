from __future__ import annotations

from pathlib import Path


def cleanup_intermediate_artifacts(
    workspace_root: Path,
    *,
    extra_paths: list[Path] | tuple[Path, ...] = (),
) -> list[str]:
    warnings: list[str] = []

    default_paths = [
        workspace_root / "input",
        workspace_root / "temp",
    ]

    for path in workspace_root.rglob("*-cache.lib"):
        if path.is_file():
            try:
                path.unlink(missing_ok=True)
            except PermissionError as exc:
                warnings.append(f"{path}: {exc}")

    for extra_path in [*default_paths, *extra_paths]:
        try:
            _remove_path(extra_path)
        except PermissionError as exc:
            warnings.append(f"{extra_path}: {exc}")

    return warnings


def _remove_path(path: Path) -> None:
    if not path.exists():
        return
    if path.is_file():
        path.unlink(missing_ok=True)
        return

    for child in path.iterdir():
        _remove_path(child)
    path.rmdir()

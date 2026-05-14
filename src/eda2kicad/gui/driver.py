from __future__ import annotations

import contextlib
import os
import shutil
import sys
import time
import types
from pathlib import Path
from typing import Protocol, runtime_checkable

from eda2kicad.gui.windows import WindowSnapshot


@runtime_checkable
class DriverBackend(Protocol):
    def launch_kicad(self, kicad_exe: Path | None, project_path: Path | None = None) -> None: ...

    def wait_main_window(self, timeout_seconds: int) -> None: ...

    def open_pcb_import(self, input_path: Path) -> None: ...

    def open_pcb_editor(self) -> None: ...

    def open_schematic_editor(self) -> None: ...

    def confirm_editor_creation(self) -> None: ...

    def open_pcb_editor_import(self) -> None: ...

    def open_schematic_editor_import(self) -> None: ...

    def select_input_file(self, input_path: Path) -> None: ...

    def confirm_import(self, output_path: Path) -> None: ...

    def wait_import_complete(self, timeout_seconds: int) -> None: ...

    def save_output(self, output_path: Path) -> None: ...

    def save_schematic_output(self, output_path: Path) -> None: ...

    def close_kicad(self) -> None: ...


def _prepare_uia_environment(artifacts_dir: Path | None) -> Path | None:
    if artifacts_dir is None:
        return None
    cache_dir = artifacts_dir / "comtypes_cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    os.environ["COMTYPES_CACHE"] = str(cache_dir)
    try:
        import comtypes
    except ImportError:
        return cache_dir

    gen_module = sys.modules.get("comtypes.gen")
    if gen_module is None:
        gen_module = types.ModuleType("comtypes.gen")
        gen_module.__path__ = [str(cache_dir)]  # type: ignore[attr-defined]
        sys.modules["comtypes.gen"] = gen_module
        comtypes.gen = gen_module  # type: ignore[attr-defined]
    else:
        path = list(getattr(gen_module, "__path__", []))
        if str(cache_dir) not in path:
            path.append(str(cache_dir))
            gen_module.__path__ = path  # type: ignore[attr-defined]
    return cache_dir


class KiCadGuiDriver:
    FILE_DIALOG_DIRECTORY_COMBO_IDS = (0x0471,)
    FILE_DIALOG_FILENAME_COMBO_IDS = (0x047C,)
    FILE_DIALOG_FILENAME_EDIT_IDS = (0x0480,)
    ALTIUM_IMPORT_COMMAND_ID = 6266
    MAIN_WINDOW_OPEN_SCHEMATIC_EDITOR_COMMAND_ID = 20010
    MAIN_WINDOW_OPEN_PCB_EDITOR_COMMAND_ID = 20012
    PCB_EDITOR_SAVE_COMMAND_ID = 20412
    PCB_EDITOR_NON_KICAD_IMPORT_COMMAND_ID = 20185
    SCHEMATIC_EDITOR_SAVE_COMMAND_ID = 20232
    SCHEMATIC_EDITOR_NON_KICAD_IMPORT_COMMAND_ID = 20149

    def __init__(
        self,
        *,
        backend: DriverBackend | None = None,
        artifacts_dir: Path | None = None,
        runtime=None,
    ) -> None:
        self.backend = backend
        self.artifacts_dir = artifacts_dir
        self.runtime = runtime
        self._application = None
        self._main_window = None
        self._win32_application = None
        self._kicad_pid: int | None = None
        self._kicad_exe: Path | None = None
        self._selected_input_path: Path | None = None
        self._output_dir: Path | None = None
        self._workflow_mode: str | None = None
        self._active_dialog = None
        self._last_import_dialog = None
        self._selected_confirm_button_title: str | None = None
        self._selected_confirm_button_handle: int | None = None
        self._last_button_activation_method: str | None = None
        self._last_dialog_key_sequence: str | None = None
        self._last_dialog_key_result: str | None = None
        self._last_dialog_hotkey_sequence: str | None = None
        self._last_dialog_hotkey_result: str | None = None
        self._last_dialog_accept_result: str | None = None
        self._layer_mapping_auto_match_attempted = False
        self._layer_mapping_unmatched_acknowledged = False
        self._pcb_mapping_sequence_completed = False

    def _runtime_debug(self, key: str, value) -> None:
        runtime = self.runtime
        if runtime is None:
            return
        with contextlib.suppress(Exception):
            runtime.record_debug_value(key, value)

    def _record_interaction_method(self, label: str, method: str) -> None:
        self._runtime_debug(label, method)
        runtime = self.runtime
        if runtime is None:
            return
        with contextlib.suppress(Exception):
            runtime.log_step(f"{label}={method}")

    def _call_backend(self, method_name: str, *args, **kwargs) -> None:
        if self.backend is not None:
            method = getattr(self.backend, method_name)
            method(*args, **kwargs)
            return
        raise NotImplementedError(f"{method_name} requires a backend or mock driver")

    def launch_kicad(self, kicad_exe: Path | None, project_path: Path | None = None) -> None:
        if self.backend is not None:
            self.backend.launch_kicad(kicad_exe, project_path)
            return
        if kicad_exe is None:
            raise ValueError("launch_kicad requires kicad_exe when no backend is injected")
        self._kicad_exe = kicad_exe
        _prepare_uia_environment(self.artifacts_dir)
        from pywinauto.application import Application  # type: ignore[import-not-found]

        command = f'"{kicad_exe}"'
        if project_path is not None:
            command = f'{command} "{project_path}"'
        self._application = Application(backend="uia").start(command)
        with contextlib.suppress(Exception):
            self._kicad_pid = int(self._application.process)

    def wait_main_window(self, timeout_seconds: int) -> None:
        if self.backend is not None and isinstance(self.backend, DriverBackend):
            self._call_backend("wait_main_window", timeout_seconds)
            return
        if self._application is None:
            raise NotImplementedError("wait_main_window requires a launched application or mock driver")
        main_window = self._application.window(title_re=".*KiCad.*")
        main_window.wait("visible", timeout=timeout_seconds)
        self._main_window = main_window

    def open_pcb_import(self, input_path: Path) -> None:
        if self.backend is not None:
            self._call_backend("open_pcb_import", input_path)
            return
        self._workflow_mode = "project_import"
        self._selected_input_path = Path(input_path)
        self._dismiss_startup_error_dialog_if_present()
        import win32con  # type: ignore[import-not-found]
        import win32gui  # type: ignore[import-not-found]

        main_window = self._get_win32_main_window()
        command_id = self._find_altium_import_command_id(main_window) or self.ALTIUM_IMPORT_COMMAND_ID
        win32gui.PostMessage(main_window.handle, win32con.WM_COMMAND, command_id, 0)
        self._active_dialog = self._wait_for_window(
            self._find_import_dialog,
            timeout_seconds=15,
            error_message="altium import dialog not found",
        )

    def open_pcb_editor(self) -> None:
        if self.backend is not None:
            self._call_backend("open_pcb_editor")
            return
        import win32con  # type: ignore[import-not-found]
        import win32gui  # type: ignore[import-not-found]

        main_window = self._get_win32_main_window()
        win32gui.PostMessage(
            main_window.handle,
            win32con.WM_COMMAND,
            self.MAIN_WINDOW_OPEN_PCB_EDITOR_COMMAND_ID,
            0,
        )
        if not self._wait_for_editor_launch_response(editor_kind="pcb", timeout_seconds=3):
            self._invoke_welcome_editor_tile(["PCB 编辑器", "PCB Editor"])

    def open_schematic_editor(self) -> None:
        if self.backend is not None:
            self._call_backend("open_schematic_editor")
            return
        import win32con  # type: ignore[import-not-found]
        import win32gui  # type: ignore[import-not-found]

        main_window = self._get_win32_main_window()
        win32gui.PostMessage(
            main_window.handle,
            win32con.WM_COMMAND,
            self.MAIN_WINDOW_OPEN_SCHEMATIC_EDITOR_COMMAND_ID,
            0,
        )
        if not self._wait_for_editor_launch_response(editor_kind="schematic", timeout_seconds=3):
            self._invoke_welcome_editor_tile(["原理图编辑器", "Schematic Editor"])

    def confirm_editor_creation(self) -> None:
        if self.backend is not None:
            self._call_backend("confirm_editor_creation")
            return
        dialog = self._wait_for_window(
            self._find_confirmation_dialog,
            timeout_seconds=15,
            error_message="editor creation confirmation dialog not found",
        )
        buttons = dialog.children(class_name="Button")
        if len(buttons) < 2:
            raise ValueError("editor creation confirmation dialog does not expose yes/no buttons")
        self._post_button_click(buttons[0].handle)
        self._wait_until_dialog_closes(dialog, timeout_seconds=10)

    def open_pcb_editor_import(self) -> None:
        if self.backend is not None:
            self._call_backend("open_pcb_editor_import")
            return
        self._workflow_mode = "pcb_standalone_import"
        self._layer_mapping_auto_match_attempted = False
        self._layer_mapping_unmatched_acknowledged = False
        self._pcb_mapping_sequence_completed = False
        import win32con  # type: ignore[import-not-found]
        import win32gui  # type: ignore[import-not-found]

        pcb_editor = self._wait_for_window(
            self._find_pcb_editor_window,
            timeout_seconds=15,
            error_message="pcb editor window not found before import",
        )
        self._wait_for_pcb_editor_ready(timeout_seconds=15)
        win32gui.PostMessage(
            pcb_editor.handle,
            win32con.WM_COMMAND,
            self.PCB_EDITOR_NON_KICAD_IMPORT_COMMAND_ID,
            0,
        )
        self._active_dialog = self._wait_for_import_dialog_with_prerequisites(
            timeout_seconds=15,
            error_message="non-kicad pcb import dialog not found",
        )

    def open_schematic_editor_import(self) -> None:
        if self.backend is not None:
            self._call_backend("open_schematic_editor_import")
            return
        self._workflow_mode = "schematic_standalone_import"
        import win32con  # type: ignore[import-not-found]
        import win32gui  # type: ignore[import-not-found]

        schematic_editor = self._wait_for_window(
            self._find_schematic_editor_window,
            timeout_seconds=15,
            error_message="schematic editor window not found before import",
        )
        win32gui.PostMessage(
            schematic_editor.handle,
            win32con.WM_COMMAND,
            self.SCHEMATIC_EDITOR_NON_KICAD_IMPORT_COMMAND_ID,
            0,
        )
        self._active_dialog = self._wait_for_import_dialog_with_prerequisites(
            timeout_seconds=15,
            error_message="non-kicad schematic import dialog not found",
        )

    def select_input_file(self, input_path: Path) -> None:
        if self.backend is not None:
            self._call_backend("select_input_file", input_path)
            return
        input_path = Path(input_path)
        dialog = self._get_active_dialog(
            timeout_seconds=15,
            error_message="altium import file dialog not found",
        )
        self._populate_file_dialog_path(dialog, input_path)
        self._selected_input_path = input_path

    def confirm_import(self, output_path: Path) -> None:
        if self.backend is not None:
            self._call_backend("confirm_import", output_path)
            return
        if self._selected_input_path is None:
            raise ValueError("confirm_import requires a selected input file")
        output_path = Path(output_path)
        self._output_dir = output_path.parent
        dialog = self._get_active_dialog(
            timeout_seconds=15,
            error_message="altium import file dialog not found before confirmation",
        )
        self._last_import_dialog = dialog
        self._populate_file_dialog_path(dialog, self._selected_input_path)
        buttons = dialog.children(class_name="Button")
        if not buttons:
            raise ValueError("altium import file dialog does not expose an open button")
        self._runtime_debug(
            "confirm_dialog_button_candidates",
            [self._describe_control(button) for button in buttons],
        )
        confirm_button = self._pick_standard_file_dialog_confirm_button(buttons)
        confirm_title = (self._safe_attr(confirm_button, "window_text") or "").strip()
        confirm_handle = getattr(confirm_button, "handle", None)
        self._selected_confirm_button_title = confirm_title
        self._selected_confirm_button_handle = confirm_handle
        for key, value in self._describe_control(confirm_button).items():
            self._runtime_debug(f"confirm_button_{key}", value)
        self._last_button_activation_method = self._activate_button(
            confirm_button,
            dialog=dialog,
            action_label="confirm_dialog_activate_method",
        )
        self._runtime_debug("confirm_button_activation_method", self._last_button_activation_method)
        self._runtime_debug("confirm_button_activate_attempted", True)
        self._wait_until_dialog_closes(dialog, timeout_seconds=10)
        dialog_still_visible = self._retry_confirm_if_dialog_still_visible()
        stale_dialog_exists = self._control_exists(dialog)
        self._runtime_debug("confirm_dialog_exists_after_wait", stale_dialog_exists)
        self._runtime_debug("confirm_dialog_visible_after_rescan", dialog_still_visible)
        if stale_dialog_exists or dialog_still_visible:
            raise ValueError("altium import file dialog did not close after confirmation")
        if self._workflow_mode in {"pcb_standalone_import", "schematic_standalone_import"}:
            return

        if self._selected_input_path.suffix.lower() == ".prjpcb":
            target_dialog = self._wait_for_window(
                self._find_target_dialog,
                timeout_seconds=15,
                error_message="kicad target dialog not found",
            )
            target_edits = target_dialog.children(class_name="Edit")
            target_buttons = target_dialog.children(class_name="Button")
            if not target_edits or not target_buttons:
                raise ValueError("kicad target dialog is missing required controls")
            target_edits[0].set_edit_text(str(self._output_dir))
            self._post_button_click(target_buttons[0].handle)
            return

        time.sleep(1)
        if self._find_target_dialog() is not None:
            target_dialog = self._find_target_dialog()
            if target_dialog is None:
                raise ValueError("kicad target dialog vanished before it could be completed")
            target_dialog.children(class_name="Edit")[0].set_edit_text(str(self._output_dir))
            self._post_button_click(target_dialog.children(class_name="Button")[0].handle)
            return
        helper_dialog = self._find_acknowledgement_dialog()
        if helper_dialog is not None:
            helper_buttons = helper_dialog.children(class_name="Button")
            if helper_buttons:
                self._post_button_click(helper_buttons[0].handle)
                time.sleep(0.5)
        raise ValueError(
            "current KiCad GUI import requires an Altium .PrjPcb project input; "
            "direct .PcbDoc did not advance past the import file dialog"
        )

    def wait_import_complete(self, timeout_seconds: int) -> None:
        if self.backend is not None:
            self._call_backend("wait_import_complete", timeout_seconds)
            return
        if self._output_dir is None:
            raise ValueError("wait_import_complete requires an output directory from confirm_import")

        deadline = time.monotonic() + timeout_seconds
        if self._workflow_mode == "pcb_standalone_import" and not self._pcb_mapping_sequence_completed:
            self._complete_pcb_standalone_mapping_sequence(deadline=deadline)
            self._pcb_mapping_sequence_completed = True
        quiet_since: float | None = None
        while time.monotonic() < deadline:
            self._dismiss_startup_error_dialog_if_present()
            if self._handle_modal_import_dialog():
                quiet_since = None
                time.sleep(1)
                continue
            progress_dialog = self._find_progress_dialog()
            layer_mapping_dialog = self._find_layer_mapping_dialog()
            project_window = self._find_project_window()
            expected_editor_window = self._find_expected_editor_window()
            self._runtime_debug("wait_import_progress_visible", progress_dialog is not None)
            self._runtime_debug("wait_import_layer_mapping_visible", layer_mapping_dialog is not None)
            self._runtime_debug("wait_import_project_visible", project_window is not None)
            self._runtime_debug("wait_import_expected_editor_visible", expected_editor_window is not None)
            if self._control_exists(self._active_dialog) or self._control_exists(self._last_import_dialog):
                quiet_since = None
                time.sleep(0.5)
                continue
            if self._find_import_dialog() is not None:
                quiet_since = None
                time.sleep(0.5)
                continue
            if self._editor_window_looks_stably_loaded(expected_editor_window):
                if quiet_since is None:
                    quiet_since = time.monotonic()
                elif time.monotonic() - quiet_since >= 2:
                    self._active_dialog = None
                    self._last_import_dialog = None
                    return
                time.sleep(0.5)
                continue
            if progress_dialog is None and layer_mapping_dialog is None:
                if project_window is not None and expected_editor_window is not None:
                    if quiet_since is None:
                        quiet_since = time.monotonic()
                    elif time.monotonic() - quiet_since >= 2:
                        self._active_dialog = None
                        self._last_import_dialog = None
                        return
                else:
                    quiet_since = None
            else:
                quiet_since = None
            time.sleep(0.5)
        raise ValueError("gui import did not reach a stable post-import state")

    def save_output(self, output_path: Path) -> None:
        if self.backend is not None:
            self._call_backend("save_output", output_path)
            return
        output_path = Path(output_path)
        import win32con  # type: ignore[import-not-found]
        import win32gui  # type: ignore[import-not-found]

        pcb_editor = self._wait_for_window(
            self._find_pcb_editor_window,
            timeout_seconds=15,
            error_message="pcb editor window not found after import",
        )
        win32gui.PostMessage(pcb_editor.handle, win32con.WM_COMMAND, self.PCB_EDITOR_SAVE_COMMAND_ID, 0)
        saved_board = self._wait_for_file(
            lambda: self._find_saved_board(output_path.parent),
            timeout_seconds=30,
            error_message="saved .kicad_pcb file not found after pcb editor save",
        )
        self._record_interaction_method("save_pcb_dispatch_method", "wm_command")
        self._wait_for_clean_editor_title(
            self._find_pcb_editor_window,
            timeout_seconds=15,
            error_message="pcb editor title still indicates unsaved changes after save",
        )
        if saved_board.resolve() != output_path.resolve():
            shutil.copy2(saved_board, output_path)

    def save_schematic_output(self, output_path: Path) -> None:
        if self.backend is not None:
            self._call_backend("save_schematic_output", output_path)
            return
        output_path = Path(output_path)
        import win32con  # type: ignore[import-not-found]
        import win32gui  # type: ignore[import-not-found]

        schematic_editor = self._wait_for_window(
            self._find_schematic_editor_window,
            timeout_seconds=15,
            error_message="schematic editor window not found after import",
        )
        win32gui.PostMessage(schematic_editor.handle, win32con.WM_COMMAND, self.SCHEMATIC_EDITOR_SAVE_COMMAND_ID, 0)
        saved_schematic = self._wait_for_file(
            lambda: self._find_saved_schematic(output_path.parent),
            timeout_seconds=30,
            error_message="saved .kicad_sch file not found after schematic editor save",
        )
        self._record_interaction_method("save_schematic_dispatch_method", "wm_command")
        self._wait_for_clean_editor_title(
            self._find_schematic_editor_window,
            timeout_seconds=15,
            error_message="schematic editor title still indicates unsaved changes after save",
        )
        if saved_schematic.resolve() != output_path.resolve():
            shutil.copy2(saved_schematic, output_path)

    def dump_current_windows(self, *, max_depth: int = 2) -> list[dict[str, object]]:
        if self.backend is not None and isinstance(self.backend, DriverBackend):
            raise NotImplementedError("dump_current_windows is only available for the real UIA driver")
        if self._main_window is None:
            raise NotImplementedError("dump_current_windows requires a connected main window")
        snapshot = self._snapshot_window(self._main_window, depth=0, max_depth=max_depth)
        return [self._snapshot_to_dict(snapshot)]

    def send_main_window_keys(self, keys: str) -> None:
        if self._main_window is None:
            raise NotImplementedError("send_main_window_keys requires a connected main window")
        _prepare_uia_environment(self.artifacts_dir)
        from pywinauto.keyboard import send_keys  # type: ignore[import-not-found]

        self._main_window.set_focus()
        send_keys(keys)

    def menu_select(self, menu_path: str) -> None:
        if self._main_window is None:
            raise NotImplementedError("menu_select requires a connected main window")
        self._main_window.menu_select(menu_path)

    def try_menu_paths(self, menu_paths: list[str]) -> bool:
        for menu_path in menu_paths:
            with contextlib.suppress(Exception):
                self.menu_select(menu_path)
                return True
        return False

    def list_desktop_windows(self) -> list[dict[str, object]]:
        _prepare_uia_environment(self.artifacts_dir)
        from pywinauto import Desktop  # type: ignore[import-not-found]

        windows: list[dict[str, object]] = []
        for win in Desktop(backend="uia").windows():
            windows.append(
                {
                    "source": "desktop",
                    "title": self._safe_attr(win, "window_text"),
                    "class_name": self._safe_attr(win, "class_name"),
                    "control_type": self._safe_element_info_attr(win, "control_type"),
                    "automation_id": self._safe_element_info_attr(win, "automation_id"),
                }
            )
        active_dialog = self._find_import_dialog()
        if active_dialog is None:
            active_dialog = self._active_dialog
        if active_dialog is None:
            active_dialog = self._last_import_dialog
        if active_dialog is not None:
            with contextlib.suppress(Exception):
                windows.append(
                    {
                        "source": "active_dialog",
                        "snapshot": self._snapshot_to_dict(
                            self._snapshot_window(active_dialog, depth=0, max_depth=3)
                        ),
                    }
                )
        return windows

    def get_debug_snapshot(self) -> dict[str, object]:
        return {
            "workflow_mode": self._workflow_mode,
            "selected_input_path": str(self._selected_input_path) if self._selected_input_path is not None else None,
            "output_dir": str(self._output_dir) if self._output_dir is not None else None,
            "selected_confirm_button_title": self._selected_confirm_button_title,
            "selected_confirm_button_handle": self._selected_confirm_button_handle,
            "last_button_activation_method": self._last_button_activation_method,
            "last_dialog_key_sequence": self._last_dialog_key_sequence,
            "last_dialog_key_result": self._last_dialog_key_result,
            "last_dialog_hotkey_sequence": self._last_dialog_hotkey_sequence,
            "last_dialog_hotkey_result": self._last_dialog_hotkey_result,
            "last_dialog_accept_result": self._last_dialog_accept_result,
            "active_dialog_exists": self._control_exists(self._active_dialog) if self._active_dialog is not None else None,
            "last_import_dialog_exists": self._control_exists(self._last_import_dialog)
            if self._last_import_dialog is not None
            else None,
            "active_import_dialog_visible": self._find_import_dialog() is not None,
        }

    def find_modal_error_dialog(self):
        if self._main_window is None:
            return None
        with contextlib.suppress(Exception):
            for child in self._get_main_wrapper().children():
                title = self._safe_attr(child, "window_text")
                if title and "KiCad 错误" in title:
                    return child
        return None

    def _find_expected_editor_window(self):
        suffix = (self._selected_input_path.suffix.lower() if self._selected_input_path is not None else "")
        if self._workflow_mode == "schematic_standalone_import" or suffix == ".schdoc":
            return self._find_schematic_editor_window()
        return self._find_pcb_editor_window()

    def _wait_for_editor_launch_response(self, *, editor_kind: str, timeout_seconds: int) -> bool:
        deadline = time.monotonic() + timeout_seconds
        while time.monotonic() < deadline:
            if editor_kind == "pcb":
                if self._find_pcb_editor_window() is not None or self._find_confirmation_dialog() is not None:
                    return True
            elif editor_kind == "schematic":
                if self._find_schematic_editor_window() is not None or self._find_confirmation_dialog() is not None:
                    return True
            time.sleep(0.2)
        return False

    def _invoke_welcome_editor_tile(self, titles: list[str]) -> bool:
        wrapper = self._get_main_wrapper()
        queue = [wrapper]
        seen: set[int] = set()
        while queue:
            node = queue.pop(0)
            node_handle = getattr(node, "handle", None)
            if node_handle is not None and node_handle in seen:
                continue
            if node_handle is not None:
                seen.add(node_handle)

            title = (self._safe_attr(node, "window_text") or "").strip()
            if title and any(candidate.lower() in title.lower() for candidate in titles):
                if self._press_dialog_button(node) or self._press_menu_item(node):
                    return True

            queue.extend(self._child_controls(node))
        return False

    def click_main_menu_item(self, title: str) -> bool:
        wrapper = self._get_main_wrapper()
        with contextlib.suppress(Exception):
            for child in wrapper.children():
                friendly = self._safe_attr(child, "friendly_class_name")
                if friendly != "Menu":
                    continue
                for menu_item in child.children():
                    if self._safe_attr(menu_item, "window_text") == title:
                        return self._press_menu_item(menu_item)
        return False

    def dismiss_modal_error_dialog(self, dialog) -> bool:
        with contextlib.suppress(Exception):
            confirm = dialog.child_window(title="确定", control_type="Button")
            if self._press_dialog_button(confirm):
                return True
        with contextlib.suppress(Exception):
            confirm = dialog.child_window(automation_id="5100", control_type="Button")
            if self._press_dialog_button(confirm):
                return True
        with contextlib.suppress(Exception):
            confirm = dialog.child_window(title="OK")
            if self._press_dialog_button(confirm):
                return True
        with contextlib.suppress(Exception):
            for child in dialog.children():
                title = self._safe_attr(child, "window_text")
                friendly = self._safe_attr(child, "friendly_class_name")
                if title in {"确定", "OK"} and friendly == "Button":
                    if self._press_dialog_button(child):
                        return True
        return False

    def _press_dialog_button(self, button) -> bool:
        for method_name in ("invoke", "click", "click_input"):
            with contextlib.suppress(Exception):
                method = getattr(button, method_name)
                method()
                return True
        return False

    def _press_menu_item(self, menu_item) -> bool:
        for method_name in ("expand", "select", "invoke", "click", "click_input"):
            with contextlib.suppress(Exception):
                method = getattr(menu_item, method_name)
                method()
                return True
        return False

    def close_kicad(self) -> None:
        if self.backend is not None and isinstance(self.backend, DriverBackend):
            self._call_backend("close_kicad")
            return
        if self._application is None:
            raise NotImplementedError("close_kicad requires a launched application or mock driver")
        with contextlib.suppress(Exception):
            self._application.kill()
        self._application = None
        self._win32_application = None
        self._main_window = None
        self._kicad_pid = None

    def _dismiss_startup_error_dialog_if_present(self) -> bool:
        dialog = self.find_modal_error_dialog()
        if dialog is None:
            return False
        return self.dismiss_modal_error_dialog(dialog)

    def _get_win32_application(self):
        if self._win32_application is not None:
            return self._win32_application
        if self._kicad_pid is None:
            raise ValueError("win32 automation requires a launched KiCad process")
        _prepare_uia_environment(self.artifacts_dir)
        from pywinauto.application import Application  # type: ignore[import-not-found]

        self._win32_application = Application(backend="win32").connect(process=self._kicad_pid)
        return self._win32_application

    def _iter_win32_windows(self):
        for window in self._get_win32_application().windows():
            yield window

    def _get_win32_main_window(self):
        for window in self._iter_win32_windows():
            if self._safe_attr(window, "class_name") != "wxWindowNR":
                continue
            with contextlib.suppress(Exception):
                menu = window.menu()
                if menu is not None and len(menu.items()) >= 6 and "KiCad" in (self._safe_attr(window, "window_text") or ""):
                    return window
        raise ValueError("kicad main window with menu was not found")

    def _find_altium_import_command_id(self, main_window) -> int | None:
        with contextlib.suppress(Exception):
            file_menu = main_window.menu().items()[0].sub_menu()
            for item in file_menu.items():
                with contextlib.suppress(Exception):
                    sub_menu = item.sub_menu()
                    if sub_menu is None:
                        continue
                    for sub_item in sub_menu.items():
                        text = sub_item.text() or ""
                        if "Altium" in text:
                            return sub_item.item_id()
        return None

    def _find_import_dialog(self):
        try:
            if self._workflow_mode in {"pcb_standalone_import", "schematic_standalone_import"}:
                for dialog in self._iter_dialogs():
                    if not self._is_visible_window(dialog):
                        continue
                    if dialog.children(class_name="Edit") and dialog.children(class_name="ComboBox"):
                        return dialog
                return None
            for dialog in self._iter_dialogs():
                if not self._is_visible_window(dialog):
                    continue
                title = self._safe_attr(dialog, "window_text") or ""
                if "Altium" not in title:
                    continue
                if dialog.children(class_name="Edit") and dialog.children(class_name="ComboBox"):
                    return dialog
        except Exception:
            return None
        return None

    def _find_confirmation_dialog(self):
        for dialog in self._iter_dialogs():
            buttons = dialog.children(class_name="Button")
            if len(buttons) != 2:
                continue
            if dialog.children(class_name="Edit"):
                continue
            return dialog
        return None

    def _find_target_dialog(self):
        for dialog in self._iter_dialogs():
            title = self._safe_attr(dialog, "window_text") or ""
            if "KiCad" not in title:
                continue
            if dialog.children(class_name="Edit") and len(dialog.children(class_name="Button")) >= 2:
                return dialog
        return None

    def _find_report_dialog(self):
        for dialog in self._iter_dialogs():
            buttons = dialog.children(class_name="Button")
            if len(buttons) != 1:
                continue
            child_classes = self._dialog_child_classes(dialog)
            if "wxWindowNR" in child_classes:
                return dialog
        return None

    def _find_unmatched_layers_dialog(self):
        for dialog in self._iter_modal_candidates():
            if not self._is_visible_window(dialog):
                continue
            buttons = dialog.children(class_name="Button")
            if len(buttons) != 1:
                continue
            title = (self._safe_attr(dialog, "window_text") or "").strip().lower()
            child_classes = self._dialog_child_classes(dialog)
            if "wxWindowNR" in child_classes:
                continue
            if any(token in title for token in ("未匹配层", "unmatched")):
                return dialog
        return None

    def _find_layer_mapping_dialog(self):
        for dialog in self._iter_modal_candidates():
            if not self._is_visible_window(dialog):
                continue
            buttons = dialog.children(class_name="Button")
            button_texts = {self._safe_attr(button, "window_text") or "" for button in buttons}
            title = (self._safe_attr(dialog, "window_text") or "").strip().lower()
            if any(token in title for token in ("映射", "mapping")):
                return dialog
            if len(buttons) >= 2 and {">", "<", "<<"}.intersection(button_texts):
                return dialog
        return None

    def _find_progress_dialog(self):
        try:
            for dialog in self._iter_dialogs():
                if not self._is_visible_window(dialog):
                    continue
                if dialog.children(class_name="msctls_progress32"):
                    if (
                        dialog.children(class_name="Edit")
                        and dialog.children(class_name="ComboBox")
                        and len(dialog.children(class_name="Button")) >= 2
                    ):
                        continue
                    return dialog
        except Exception:
            pass
        try:
            for window in self._iter_win32_windows():
                with contextlib.suppress(Exception):
                    if not self._is_visible_window(window):
                        continue
                    if self._looks_like_primary_kicad_window(window):
                        continue
                    if window.children(class_name="msctls_progress32"):
                        if (
                            window.children(class_name="Edit")
                            and window.children(class_name="ComboBox")
                            and len(window.children(class_name="Button")) >= 2
                        ):
                            continue
                        return window
        except Exception:
            pass
        return None

    def _find_acknowledgement_dialog(self):
        for dialog in self._iter_dialogs():
            buttons = dialog.children(class_name="Button")
            if len(buttons) != 1:
                continue
            child_classes = self._dialog_child_classes(dialog)
            if "msctls_progress32" in child_classes:
                continue
            return dialog
        return None

    def _find_standalone_editor_replace_confirmation_dialog(self):
        if self._workflow_mode not in {"pcb_standalone_import", "schematic_standalone_import"}:
            return None
        for dialog in self._iter_modal_candidates():
            if not self._is_visible_window(dialog):
                continue
            if dialog.children(class_name="Edit") or dialog.children(class_name="ComboBox"):
                continue
            buttons = dialog.children(class_name="Button")
            if len(buttons) < 2:
                continue
            button_titles = {
                (self._safe_attr(button, "window_text") or "").strip().lower()
                for button in buttons
            }
            if len(buttons) >= 3 and any(
                token in " ".join(button_titles)
                for token in ("放弃变更", "discard", "don't save", "don’t save")
            ):
                return dialog
        return self._find_confirmation_dialog()

    def _find_project_window(self):
        for window in self._iter_win32_windows():
            title = self._safe_attr(window, "window_text") or ""
            if self._safe_attr(window, "class_name") != "wxWindowNR":
                continue
            with contextlib.suppress(Exception):
                menu = window.menu()
                if menu is None or len(menu.items()) < 6:
                    continue
            if "KiCad 10.0" in title and "PCB" not in title and "原理图" not in title:
                return window
        return None

    def _find_pcb_editor_window(self):
        for window in self._iter_win32_windows():
            title = self._safe_attr(window, "window_text") or ""
            if self._safe_attr(window, "class_name") != "wxWindowNR" or "PCB" not in title:
                continue
            with contextlib.suppress(Exception):
                menu = window.menu()
                if menu is not None and len(menu.items()) >= 9:
                    return window
        return None

    def _find_schematic_editor_window(self):
        for window in self._iter_win32_windows():
            if self._safe_attr(window, "class_name") != "wxWindowNR":
                continue
            with contextlib.suppress(Exception):
                menu = window.menu()
                if menu is None or len(menu.items()) != 8:
                    continue
                file_menu = menu.items()[0].sub_menu()
                if file_menu is None:
                    continue
                for item in file_menu.items():
                    with contextlib.suppress(Exception):
                        text = item.text() or ""
                        if "Ctrl+S" in text and item.item_id() == self.SCHEMATIC_EDITOR_SAVE_COMMAND_ID:
                            return window
        return None

    def _find_saved_board(self, output_dir: Path) -> Path | None:
        boards = sorted(output_dir.glob("*.kicad_pcb"))
        return boards[0] if boards else None

    def _find_saved_schematic(self, output_dir: Path) -> Path | None:
        schematics = sorted(output_dir.glob("*.kicad_sch"))
        return schematics[0] if schematics else None

    def _handle_modal_import_dialog(self) -> bool:
        report_dialog = self._find_report_dialog()
        if report_dialog is not None:
            buttons = report_dialog.children(class_name="Button")
            if buttons:
                self._post_button_click(buttons[0].handle)
                return True

        unmatched_layers_dialog = self._find_unmatched_layers_dialog()
        if unmatched_layers_dialog is not None:
            buttons = unmatched_layers_dialog.children(class_name="Button")
            if buttons:
                self._runtime_debug(
                    "unmatched_layers_dialog_title",
                    self._safe_attr(unmatched_layers_dialog, "window_text"),
                )
                self._runtime_debug(
                    "unmatched_layers_button_title",
                    self._safe_attr(buttons[0], "window_text"),
                )
                if self._layer_mapping_auto_match_attempted:
                    self._layer_mapping_unmatched_acknowledged = True
                    self._runtime_debug("layer_mapping_action", "ack_unmatched_layers")
                self._activate_button(buttons[0], dialog=unmatched_layers_dialog)
                return True

        layer_mapping_dialog = self._find_layer_mapping_dialog()
        if layer_mapping_dialog is not None:
            buttons = layer_mapping_dialog.children(class_name="Button")
            auto_match_button = self._pick_layer_mapping_auto_match_button(buttons)
            confirm_button = self._pick_layer_mapping_confirm_button(buttons)
            self._runtime_debug(
                "layer_mapping_dialog_title",
                self._safe_attr(layer_mapping_dialog, "window_text"),
            )
            self._runtime_debug(
                "layer_mapping_button_titles",
                [self._safe_attr(button, "window_text") for button in buttons],
            )
            self._runtime_debug(
                "layer_mapping_auto_match_attempted",
                self._layer_mapping_auto_match_attempted,
            )
            self._runtime_debug(
                "layer_mapping_unmatched_acknowledged",
                self._layer_mapping_unmatched_acknowledged,
            )
            if not self._layer_mapping_auto_match_attempted and auto_match_button is not None:
                self._activate_button(auto_match_button, dialog=layer_mapping_dialog)
                self._layer_mapping_auto_match_attempted = True
                self._layer_mapping_unmatched_acknowledged = False
                self._runtime_debug("layer_mapping_action", "auto_match")
                time.sleep(0.5)
                return True
            if (
                self._layer_mapping_auto_match_attempted
                and not self._layer_mapping_unmatched_acknowledged
                and unmatched_layers_dialog is None
                and confirm_button is not None
            ):
                self._runtime_debug("layer_mapping_action", "confirm_without_unmatched_prompt")
                self._activate_button(confirm_button, dialog=layer_mapping_dialog)
                self._layer_mapping_unmatched_acknowledged = True
                return True
            if (
                self._layer_mapping_auto_match_attempted
                and self._layer_mapping_unmatched_acknowledged
                and confirm_button is not None
            ):
                self._runtime_debug("layer_mapping_action", "confirm")
                self._activate_button(confirm_button, dialog=layer_mapping_dialog)
                return True

        replace_confirmation_dialog = self._find_standalone_editor_replace_confirmation_dialog()
        if replace_confirmation_dialog is not None:
            buttons = replace_confirmation_dialog.children(class_name="Button")
            if buttons:
                self._post_button_click(self._pick_discard_changes_button(buttons).handle)
                time.sleep(0.5)
                return True

        acknowledgement_dialog = self._find_acknowledgement_dialog()
        if acknowledgement_dialog is not None:
            buttons = acknowledgement_dialog.children(class_name="Button")
            if buttons:
                self._post_button_click(buttons[0].handle)
                return True
        return False

    def _iter_dialogs(self):
        _prepare_uia_environment(self.artifacts_dir)
        from pywinauto import Desktop  # type: ignore[import-not-found]

        for dialog in Desktop(backend="win32").windows(class_name="#32770"):
            yield dialog

    def _iter_modal_candidates(self):
        seen: set[int] = set()
        with contextlib.suppress(Exception):
            for dialog in self._iter_dialogs():
                handle = getattr(dialog, "handle", None)
                if handle is not None and handle in seen:
                    continue
                if handle is not None:
                    seen.add(handle)
                yield dialog
        with contextlib.suppress(Exception):
            for window in self._iter_win32_windows():
                handle = getattr(window, "handle", None)
                if handle is not None and handle in seen:
                    continue
                title = (self._safe_attr(window, "window_text") or "").strip()
                class_name = self._safe_attr(window, "class_name") or ""
                if class_name != "wxWindowNR":
                    continue
                if "KiCad 10.0" in title or "PCB" in title or "Schematic" in title:
                    continue
                buttons = self._child_controls(window, class_name="Button")
                if not buttons:
                    continue
                if handle is not None:
                    seen.add(handle)
                yield window

    @staticmethod
    def _dialog_child_classes(dialog) -> list[str]:
        classes: list[str] = []
        with contextlib.suppress(Exception):
            for child in dialog.children():
                class_name = getattr(child, "class_name")()
                classes.append(class_name)
        return classes

    def _find_edit_controls(self, root) -> list:
        edits: list = []
        seen: set[int] = set()

        def visit(node) -> None:
            for child in self._child_controls(node, class_name="Edit"):
                handle = getattr(child, "handle", None)
                if handle is not None and handle in seen:
                    continue
                if handle is not None:
                    seen.add(handle)
                edits.append(child)

            for child in self._child_controls(node):
                visit(child)

        visit(root)
        return edits

    @staticmethod
    def _child_controls(node, class_name: str | None = None) -> list:
        with contextlib.suppress(Exception):
            if class_name is not None:
                return list(node.children(class_name=class_name))
        with contextlib.suppress(Exception):
            return list(node.children())
        return []

    def _is_preferred_file_dialog_edit(self, edit) -> bool:
        current = edit
        for _ in range(4):
            with contextlib.suppress(Exception):
                current = current.parent()
                if current is None:
                    return False
                class_name = self._safe_attr(current, "class_name")
                if class_name in {"ComboBox", "ComboBoxEx32"}:
                    return True
        return False

    def _get_preferred_file_dialog_edit(self, dialog):
        preferred_edits = self._find_preferred_file_dialog_edits(dialog)
        if not preferred_edits:
            return None
        return preferred_edits[-1]

    def _populate_file_dialog_path(self, dialog, input_path: Path) -> None:
        standard_filename_edit = self._find_standard_file_dialog_edit(
            dialog,
            combo_ids=self.FILE_DIALOG_FILENAME_COMBO_IDS,
            edit_ids=self.FILE_DIALOG_FILENAME_EDIT_IDS,
        )
        if standard_filename_edit is not None:
            self._set_edit_if_needed(standard_filename_edit, str(input_path))
            return

        preferred_edits = self._find_preferred_file_dialog_edits(dialog)
        if preferred_edits:
            filename_edit = preferred_edits[-1]
            self._set_edit_if_needed(filename_edit, str(input_path))
            return

        edits = self._find_edit_controls(dialog)
        if not edits:
            raise ValueError("altium import file dialog does not expose an editable path field")
        ordered_edits = self._order_file_dialog_edits(edits)
        last_error: Exception | None = None
        for edit in ordered_edits:
            try:
                self._set_edit_if_needed(edit, str(input_path))
                return
            except Exception as exc:
                last_error = exc
        if last_error is not None:
            raise last_error

    def _find_preferred_file_dialog_edits(self, dialog) -> list:
        edits = self._find_edit_controls(dialog)
        preferred = [edit for edit in edits if self._is_preferred_file_dialog_edit(edit)]
        preferred.sort(key=self._preferred_file_dialog_edit_sort_key)
        return preferred

    def _find_standard_file_dialog_edit(self, dialog, *, combo_ids: tuple[int, ...], edit_ids: tuple[int, ...]):
        for control in self._walk_controls(dialog):
            class_name = self._safe_attr(control, "class_name")
            control_id = self._safe_control_id(control)
            if class_name in {"ComboBox", "ComboBoxEx32"} and control_id in combo_ids:
                child_edit = self._first_child_edit(control)
                if child_edit is not None:
                    return child_edit
            if class_name == "Edit" and control_id in edit_ids:
                return control
        return None

    def _walk_controls(self, root):
        yield root
        for child in self._child_controls(root):
            yield from self._walk_controls(child)

    def _first_child_edit(self, control):
        for child in self._child_controls(control, class_name="Edit"):
            return child
        return None

    def _preferred_file_dialog_edit_sort_key(self, edit) -> tuple[int, int, int]:
        with contextlib.suppress(Exception):
            rect = edit.rectangle()
            return (int(rect.top), int(rect.left), 0)
        return (0, 0, 1)

    def _order_file_dialog_edits(self, edits: list) -> list:
        indexed_edits = list(enumerate(edits))
        indexed_edits.sort(
            key=lambda pair: (
                not self._is_preferred_file_dialog_edit(pair[1]),
                not self._wrapper_bool(pair[1], "is_visible"),
                not self._wrapper_bool(pair[1], "is_enabled"),
                -pair[0],
            )
        )
        return [edit for _index, edit in indexed_edits]

    def _set_edit_if_needed(self, edit, value: str) -> None:
        current_text = (self._safe_attr(edit, "window_text") or "").strip()
        if current_text == value:
            return
        self._set_edit_text(edit, value)

    def _pick_import_confirm_button(self, buttons):
        preferred_titles = ("打开", "open", "导入", "import")
        for button in buttons:
            title = (self._safe_attr(button, "window_text") or "").strip().lower()
            if any(token in title for token in preferred_titles):
                return button
        return buttons[0]

    def _pick_discard_changes_button(self, buttons):
        preferred_titles = (
            "放弃更改",
            "不保存",
            "discard",
            "don't save",
            "don’t save",
        )
        for button in buttons:
            title = (self._safe_attr(button, "window_text") or "").strip().lower()
            if any(token in title for token in preferred_titles):
                return button
        if len(buttons) == 3:
            return buttons[1]
        return buttons[0]

    @staticmethod
    def _post_button_click(handle: int) -> None:
        import win32con  # type: ignore[import-not-found]
        import win32gui  # type: ignore[import-not-found]

        win32gui.PostMessage(handle, win32con.BM_CLICK, 0, 0)

    def _activate_button(self, button, *, dialog=None, action_label: str | None = None) -> str:
        with contextlib.suppress(Exception):
            if dialog is not None:
                dialog.set_focus()
        with contextlib.suppress(Exception):
            button.set_focus()
        with contextlib.suppress(Exception):
            invoke = getattr(button, "invoke")
            invoke()
            if action_label is not None:
                self._record_interaction_method(action_label, "invoke")
            return "invoke"
        with contextlib.suppress(Exception):
            click = getattr(button, "click")
            click()
            if action_label is not None:
                self._record_interaction_method(action_label, "click")
            return "click"
        handle = getattr(button, "handle", None)
        if handle is not None:
            self._post_button_click(handle)
            if action_label is not None:
                self._record_interaction_method(action_label, "bm_click")
            return "bm_click"
        with contextlib.suppress(Exception):
            click_input = getattr(button, "click_input")
            click_input()
            if action_label is not None:
                self._record_interaction_method(action_label, "click_input")
            return "click_input"
        if self._click_button_center(button):
            if action_label is not None:
                self._record_interaction_method(action_label, "center_click")
            return "center_click"
        raise ValueError("button does not expose an actionable method for activation")

    def _pick_standard_file_dialog_confirm_button(self, buttons):
        ranked_buttons = sorted(buttons, key=self._standard_file_dialog_button_sort_key)
        for button in ranked_buttons:
            if self._safe_control_id(button) == 1:
                return button
        for button in ranked_buttons:
            title = ((self._safe_attr(button, "window_text") or "").strip()).lower()
            if any(token in title for token in ("打开", "open", "导入", "import", "鎵撳紑", "瀵煎叆")):
                return button
        for button in ranked_buttons:
            if self._safe_control_id(button) == 2:
                continue
            return button
        return ranked_buttons[0]

    def _standard_file_dialog_button_sort_key(self, button) -> tuple[int, int, int, int, int]:
        is_visible = self._wrapper_bool(button, "is_visible")
        is_enabled = self._wrapper_bool(button, "is_enabled")
        control_id = self._safe_control_id(button)
        rect = self._safe_rectangle(button)
        bottom = rect["bottom"] if rect is not None else -1
        right = rect["right"] if rect is not None else -1
        return (
            0 if is_visible else 1,
            0 if is_enabled else 1,
            0 if control_id == 1 else 1,
            -bottom,
            -right,
        )

    def _pick_layer_mapping_auto_match_button(self, buttons):
        for button in buttons:
            title = ((self._safe_attr(button, "window_text") or "").strip()).lower()
            if any(token in title for token in ("auto-match", "match", "自动匹配", "匹配")):
                return button
        if len(buttons) >= 2:
            return buttons[-2]
        return buttons[0] if buttons else None

    def _pick_layer_mapping_confirm_button(self, buttons):
        for button in buttons:
            if self._safe_control_id(button) == 1:
                return button
        for button in buttons:
            title = ((self._safe_attr(button, "window_text") or "").strip()).lower()
            if any(token in title for token in ("ok", "确定", "完成", "continue", "继续")):
                return button
        return buttons[-1] if buttons else None

    def _click_button_center(self, button) -> bool:
        with contextlib.suppress(Exception):
            rect = button.rectangle()
            x = int((rect.left + rect.right) / 2)
            y = int((rect.top + rect.bottom) / 2)
            _prepare_uia_environment(self.artifacts_dir)
            from pywinauto import mouse  # type: ignore[import-not-found]

            mouse.click(button="left", coords=(x, y))
            return True
        return False

    def _retry_confirm_if_dialog_still_visible(self) -> bool:
        dialog = self._find_import_dialog()
        if dialog is None:
            return False
        if not self._is_visible_window(dialog):
            return False
        self._runtime_debug("confirm_dialog_retry_required", True)
        buttons = self._child_controls(dialog, class_name="Button")
        if not buttons:
            return True
        visible_enabled_buttons = [
            button
            for button in buttons
            if self._wrapper_bool(button, "is_visible") and self._wrapper_bool(button, "is_enabled")
        ]
        if not visible_enabled_buttons:
            self._runtime_debug("confirm_retry_skipped_reason", "no_visible_enabled_buttons")
            return False
        self._runtime_debug(
            "confirm_retry_dialog_button_candidates",
            [self._describe_control(button) for button in buttons],
        )
        confirm_button = self._pick_standard_file_dialog_confirm_button(visible_enabled_buttons)
        for key, value in self._describe_control(confirm_button).items():
            self._runtime_debug(f"confirm_retry_button_{key}", value)
        self._last_button_activation_method = self._activate_button(
            confirm_button,
            dialog=dialog,
            action_label="confirm_retry_activate_method",
        )
        self._runtime_debug("confirm_retry_activation_method", self._last_button_activation_method)
        self._wait_until_dialog_closes(dialog, timeout_seconds=5)
        return self._find_import_dialog() is not None

    def _describe_control(self, control) -> dict[str, object]:
        description: dict[str, object] = {
            "title": self._safe_attr(control, "window_text"),
            "class_name": self._safe_attr(control, "class_name"),
            "friendly_class_name": self._safe_attr(control, "friendly_class_name"),
            "control_type": self._safe_element_info_attr(control, "control_type"),
            "automation_id": self._safe_element_info_attr(control, "automation_id"),
            "handle": getattr(control, "handle", None),
            "control_id": self._safe_control_id(control),
            "is_enabled": self._wrapper_bool(control, "is_enabled"),
            "is_visible": self._wrapper_bool(control, "is_visible"),
        }
        rect = self._safe_rectangle(control)
        if rect is not None:
            description["rectangle"] = rect
        return description

    def _safe_rectangle(self, control) -> dict[str, int] | None:
        with contextlib.suppress(Exception):
            rect = control.rectangle()
            return {
                "left": int(rect.left),
                "top": int(rect.top),
                "right": int(rect.right),
                "bottom": int(rect.bottom),
            }
        return None

    def _send_dialog_keys(self, dialog, keys: str) -> None:
        self._last_dialog_key_sequence = keys
        try:
            _prepare_uia_environment(self.artifacts_dir)
            from pywinauto.keyboard import send_keys  # type: ignore[import-not-found]
        except Exception:
            self._last_dialog_key_result = "keyboard_unavailable"
            return
        with contextlib.suppress(Exception):
            send_keys(keys)
            self._last_dialog_key_result = "sent"
            return
        self._last_dialog_key_result = "send_failed"

    def _send_dialog_hotkey(self, dialog, keys: str) -> None:
        self._last_dialog_hotkey_sequence = keys
        try:
            _prepare_uia_environment(self.artifacts_dir)
            from pywinauto.keyboard import send_keys  # type: ignore[import-not-found]
        except Exception:
            self._last_dialog_hotkey_result = "keyboard_unavailable"
            return
        with contextlib.suppress(Exception):
            dialog.set_focus()
        with contextlib.suppress(Exception):
            send_keys(keys)
            self._last_dialog_hotkey_result = "sent"
            return
        self._last_dialog_hotkey_result = "send_failed"

    def _post_dialog_accept_command(self, dialog) -> None:
        import win32con  # type: ignore[import-not-found]
        import win32gui  # type: ignore[import-not-found]

        handle = getattr(dialog, "handle", None)
        if handle is None:
            self._last_dialog_accept_result = "missing_handle"
            return
        with contextlib.suppress(Exception):
            win32gui.PostMessage(handle, win32con.WM_COMMAND, 1, 0)
            self._last_dialog_accept_result = "sent"
            return
        self._last_dialog_accept_result = "send_failed"

    def _wait_for_window(self, finder, *, timeout_seconds: int, error_message: str):
        deadline = time.monotonic() + timeout_seconds
        while time.monotonic() < deadline:
            window = finder()
            if window is not None:
                return window
            time.sleep(0.5)
        raise ValueError(error_message)

    def _wait_for_import_dialog_with_prerequisites(self, *, timeout_seconds: int, error_message: str):
        deadline = time.monotonic() + timeout_seconds
        while time.monotonic() < deadline:
            import_dialog = self._find_import_dialog()
            if import_dialog is not None:
                return import_dialog

            if self._find_progress_dialog() is not None:
                time.sleep(0.5)
                continue

            acknowledgement_dialog = self._find_acknowledgement_dialog()
            if acknowledgement_dialog is not None:
                buttons = acknowledgement_dialog.children(class_name="Button")
                if buttons:
                    self._post_button_click(buttons[0].handle)
                    time.sleep(0.5)
                    continue

            confirmation_dialog = self._find_standalone_editor_replace_confirmation_dialog()
            if confirmation_dialog is not None:
                buttons = confirmation_dialog.children(class_name="Button")
                if buttons:
                    self._post_button_click(self._pick_discard_changes_button(buttons).handle)
                    time.sleep(0.5)
                    continue

            time.sleep(0.5)
        raise ValueError(error_message)

    def _wait_for_pcb_editor_ready(self, *, timeout_seconds: int) -> None:
        deadline = time.monotonic() + timeout_seconds
        while time.monotonic() < deadline:
            progress_dialog = self._find_progress_dialog()
            editor_window = self._find_pcb_editor_window()
            self._runtime_debug("pcb_editor_ready_progress_visible", progress_dialog is not None)
            self._runtime_debug("pcb_editor_ready_editor_visible", editor_window is not None)
            if progress_dialog is None:
                return
            confirmation_dialog = None
            if editor_window is not None:
                with contextlib.suppress(Exception):
                    confirmation_dialog = self._find_confirmation_dialog()
                self._runtime_debug("pcb_editor_ready_confirmation_visible", confirmation_dialog is not None)
            if editor_window is not None and confirmation_dialog is None:
                return
            time.sleep(0.5)
        raise ValueError("pcb editor creation did not reach a stable ready state before import")

    def _wait_for_file(self, finder, *, timeout_seconds: int, error_message: str) -> Path:
        deadline = time.monotonic() + timeout_seconds
        while time.monotonic() < deadline:
            file_path = finder()
            if file_path is not None and file_path.exists():
                return file_path
            time.sleep(0.5)
        raise ValueError(error_message)

    @staticmethod
    def _wait_until_dialog_closes(dialog, *, timeout_seconds: int) -> None:
        deadline = time.monotonic() + timeout_seconds
        while time.monotonic() < deadline:
            if not KiCadGuiDriver._control_exists(dialog):
                return
            time.sleep(0.2)

    @staticmethod
    def _control_exists(control) -> bool:
        with contextlib.suppress(Exception):
            return bool(control.exists())
        return False

    def _get_active_dialog(self, *, timeout_seconds: int, error_message: str):
        dialog = self._active_dialog
        if dialog is not None:
            if not hasattr(dialog, "exists"):
                return dialog
            with contextlib.suppress(Exception):
                if dialog.exists():
                    return dialog
        dialog = self._wait_for_window(
            self._find_import_dialog,
            timeout_seconds=timeout_seconds,
            error_message=error_message,
        )
        self._active_dialog = dialog
        return dialog

    def _get_main_wrapper(self):
        if self._main_window is None:
            raise NotImplementedError("main window is not connected")
        with contextlib.suppress(Exception):
            return self._main_window.wrapper_object()
        return self._main_window

    def _acknowledge_unmatched_layers_dialog(self, dialog) -> None:
        buttons = dialog.children(class_name="Button")
        if not buttons:
            raise ValueError("unmatched layers dialog does not expose a confirmation button")
        self._runtime_debug(
            "unmatched_layers_dialog_title",
            self._safe_attr(dialog, "window_text"),
        )
        self._runtime_debug(
            "unmatched_layers_button_title",
            self._safe_attr(buttons[0], "window_text"),
        )
        self._activate_button(
            buttons[0],
            dialog=dialog,
            action_label="pcb_mapping_unmatched_ack_method",
        )
        self._layer_mapping_unmatched_acknowledged = True

    def _complete_pcb_standalone_mapping_sequence(self, *, deadline: float) -> None:
        self._runtime_debug("pcb_mapping_mode", "dedicated_sequence")

        mapping_dialog = None
        while time.monotonic() < deadline:
            self._dismiss_startup_error_dialog_if_present()
            report_dialog = self._find_report_dialog()
            if report_dialog is not None:
                buttons = report_dialog.children(class_name="Button")
                if buttons:
                    self._post_button_click(buttons[0].handle)
                    time.sleep(0.5)
                    continue

            mapping_dialog = self._find_layer_mapping_dialog()
            if mapping_dialog is not None:
                self._runtime_debug("pcb_mapping_step", "wait_mapping_dialog")
                break

            unmatched_layers_dialog = self._find_unmatched_layers_dialog()
            if unmatched_layers_dialog is not None:
                self._runtime_debug("pcb_mapping_step", "ack_pre_mapping_unmatched_layers")
                self._acknowledge_unmatched_layers_dialog(unmatched_layers_dialog)
                time.sleep(0.5)
                continue
            if self._find_progress_dialog() is None and self._find_pcb_editor_window() is not None:
                self._runtime_debug("pcb_mapping_step", "mapping_not_shown_but_editor_ready")
                return
            time.sleep(0.5)
        if mapping_dialog is None:
            raise ValueError("pcb layer mapping dialog not found after file selection")

        mapping_buttons = mapping_dialog.children(class_name="Button")
        self._runtime_debug(
            "pcb_mapping_button_titles",
            [self._safe_attr(button, "window_text") for button in mapping_buttons],
        )
        auto_match_button = self._pick_layer_mapping_auto_match_button(mapping_buttons)
        if auto_match_button is None:
            raise ValueError("pcb layer mapping dialog is missing the auto-match button")
        self._runtime_debug("pcb_mapping_step", "click_auto_match")
        self._activate_button(
            auto_match_button,
            dialog=mapping_dialog,
            action_label="pcb_mapping_auto_match_method",
        )
        self._layer_mapping_auto_match_attempted = True
        self._layer_mapping_unmatched_acknowledged = False
        time.sleep(0.5)

        unmatched_grace_deadline = min(deadline, time.monotonic() + 3)
        while time.monotonic() < deadline:
            self._dismiss_startup_error_dialog_if_present()
            unmatched_layers_dialog = self._find_unmatched_layers_dialog()
            if unmatched_layers_dialog is not None:
                self._runtime_debug("pcb_mapping_step", "ack_unmatched_layers")
                self._acknowledge_unmatched_layers_dialog(unmatched_layers_dialog)
                time.sleep(0.5)
                break

            mapping_dialog = self._find_layer_mapping_dialog()
            if mapping_dialog is not None and time.monotonic() >= unmatched_grace_deadline:
                break

            if mapping_dialog is None and self._find_progress_dialog() is not None:
                self._runtime_debug("pcb_mapping_step", "wait_load_progress")
                return
            time.sleep(0.5)

        while time.monotonic() < deadline:
            self._dismiss_startup_error_dialog_if_present()
            unmatched_layers_dialog = self._find_unmatched_layers_dialog()
            if unmatched_layers_dialog is not None:
                self._runtime_debug("pcb_mapping_step", "ack_unmatched_layers")
                self._acknowledge_unmatched_layers_dialog(unmatched_layers_dialog)
                time.sleep(0.5)
                continue

            mapping_dialog = self._find_layer_mapping_dialog()
            if mapping_dialog is None:
                if self._find_progress_dialog() is not None:
                    self._runtime_debug("pcb_mapping_step", "wait_load_progress")
                    return
                time.sleep(0.5)
                continue

            mapping_buttons = mapping_dialog.children(class_name="Button")
            confirm_button = self._pick_layer_mapping_confirm_button(mapping_buttons)
            if confirm_button is None:
                raise ValueError("pcb layer mapping dialog is missing the confirm button")
            self._runtime_debug("pcb_mapping_step", "confirm_mapping")
            self._activate_button(
                confirm_button,
                dialog=mapping_dialog,
                action_label="pcb_mapping_confirm_method",
            )
            time.sleep(0.5)
            break
        else:
            raise ValueError("pcb layer mapping dialog did not return to a confirmable state")

        self._runtime_debug("pcb_mapping_step", "wait_load_progress")

    def validate_post_import_editor_state(self) -> None:
        if self._workflow_mode == "schematic_standalone_import":
            editor = self._wait_for_window(
                self._find_schematic_editor_window,
                timeout_seconds=10,
                error_message="schematic editor window not found after import",
            )
            title = (self._safe_attr(editor, "window_text") or "").strip()
            self._runtime_debug("schematic_editor_title_after_import", title)
            if "untitled" in title.lower():
                raise ValueError("schematic editor remained untitled after import; import likely failed")
            return
        if self._workflow_mode == "pcb_standalone_import":
            editor = self._wait_for_window(
                self._find_pcb_editor_window,
                timeout_seconds=10,
                error_message="pcb editor window not found after import",
            )
            title = (self._safe_attr(editor, "window_text") or "").strip()
            self._runtime_debug("pcb_editor_title_after_import", title)
            if "untitled" in title.lower():
                raise ValueError("pcb editor remained untitled after import; import likely failed")

    def _editor_window_looks_stably_loaded(self, editor) -> bool:
        if editor is None:
            return False
        title = (self._safe_attr(editor, "window_text") or "").strip()
        if not title:
            return False
        lowered = title.lower()
        if "untitled" in lowered:
            return False
        return not title.startswith("*")

    def _wait_for_clean_editor_title(self, finder, *, timeout_seconds: int, error_message: str) -> None:
        deadline = time.monotonic() + timeout_seconds
        while time.monotonic() < deadline:
            editor = finder()
            if editor is None:
                time.sleep(0.5)
                continue
            title = (self._safe_attr(editor, "window_text") or "").strip()
            if title and not title.startswith("*"):
                return
            time.sleep(0.5)
        raise ValueError(error_message)

    def _pick_layer_mapping_auto_match_button(self, buttons):
        exact_tokens = (
            "auto-match layers",
            "auto-match layer",
            "auto-match",
            "自动匹配的层",
            "自动匹配层",
            "自动匹配",
        )
        for button in buttons:
            title = ((self._safe_attr(button, "window_text") or "").strip()).lower()
            if any(token in title for token in exact_tokens):
                return button
        if len(buttons) >= 2:
            return buttons[-2]
        return buttons[0] if buttons else None

    def _snapshot_window(self, wrapper, *, depth: int, max_depth: int) -> WindowSnapshot:
        children = []
        if depth < max_depth:
            with contextlib.suppress(Exception):
                for child in wrapper.children():
                    children.append(self._snapshot_window(child, depth=depth + 1, max_depth=max_depth))
        return WindowSnapshot(
            title=self._safe_attr(wrapper, "window_text"),
            class_name=self._safe_attr(wrapper, "class_name"),
            control_type=self._safe_element_info_attr(wrapper, "control_type"),
            automation_id=self._safe_element_info_attr(wrapper, "automation_id"),
            children=children,
        )

    @staticmethod
    def _snapshot_to_dict(snapshot: WindowSnapshot) -> dict[str, object]:
        return {
            "title": snapshot.title,
            "class_name": snapshot.class_name,
            "control_type": snapshot.control_type,
            "automation_id": snapshot.automation_id,
            "children": [KiCadGuiDriver._snapshot_to_dict(child) for child in snapshot.children],
        }

    @staticmethod
    def _safe_attr(wrapper, attr_name: str) -> str | None:
        with contextlib.suppress(Exception):
            value = getattr(wrapper, attr_name)()
            return value if value != "" else None
        return None

    @staticmethod
    def _safe_element_info_attr(wrapper, attr_name: str) -> str | None:
        with contextlib.suppress(Exception):
            value = getattr(wrapper.element_info, attr_name)
            return value if value != "" else None
        return None

    @staticmethod
    def _safe_control_id(wrapper) -> int | None:
        with contextlib.suppress(Exception):
            return int(wrapper.control_id())
        return None

    @staticmethod
    def _wrapper_bool(wrapper, method_name: str) -> bool:
        with contextlib.suppress(Exception):
            return bool(getattr(wrapper, method_name)())
        return False

    @staticmethod
    def _is_visible_window(wrapper) -> bool:
        with contextlib.suppress(Exception):
            return bool(wrapper.is_visible())
        return True

    def _looks_like_primary_kicad_window(self, wrapper) -> bool:
        class_name = self._safe_attr(wrapper, "class_name") or ""
        title = (self._safe_attr(wrapper, "window_text") or "").strip()
        if class_name != "wxWindowNR":
            return False
        lowered = title.lower()
        if "kicad 10.0" in lowered or "pcb" in lowered or "schematic" in lowered:
            return True
        if "原理图" in title or "编辑器" in title:
            return True
        with contextlib.suppress(Exception):
            menu = wrapper.menu()
            if menu is not None and len(menu.items()) >= 6:
                return True
        return False

    @staticmethod
    def _set_edit_text(edit, value: str) -> None:
        with contextlib.suppress(Exception):
            edit.set_edit_text(value)
            return
        with contextlib.suppress(Exception):
            edit.set_window_text(value)
            return
        import win32con  # type: ignore[import-not-found]
        import win32gui  # type: ignore[import-not-found]

        handle = getattr(edit, "handle", None)
        if handle is None:
            raise ValueError("edit control does not expose a handle for WM_SETTEXT fallback")
        win32gui.SendMessage(handle, win32con.WM_SETTEXT, 0, value)

from pathlib import Path

import pytest

from eda2kicad.gui.driver import (
    KiCadGuiDriver,
    _prepare_uia_environment,
)


def test_prepare_uia_environment_sets_workspace_scoped_comtypes_cache(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("COMTYPES_CACHE", raising=False)

    cache_dir = _prepare_uia_environment(tmp_path / "artifacts")

    assert cache_dir == tmp_path / "artifacts" / "comtypes_cache"
    assert cache_dir.is_dir()
    assert cache_dir == Path(__import__("os").environ["COMTYPES_CACHE"])


def test_launch_kicad_requires_executable_when_no_backend() -> None:
    driver = KiCadGuiDriver()

    with pytest.raises(ValueError, match="kicad_exe"):
        driver.launch_kicad(None)


def test_dump_current_windows_requires_real_main_window() -> None:
    driver = KiCadGuiDriver()

    with pytest.raises(NotImplementedError, match="main window"):
        driver.dump_current_windows()


def test_find_modal_error_prefers_kicad_error_dialog() -> None:
    class FakeDialog:
        def __init__(self, title: str) -> None:
            self._title = title

        def window_text(self) -> str:
            return self._title

    class FakeMainWindow:
        def children(self):
            return [FakeDialog("其他窗口"), FakeDialog("KiCad 错误")]

    driver = KiCadGuiDriver()
    driver._main_window = FakeMainWindow()

    dialog = driver.find_modal_error_dialog()

    assert dialog is not None
    assert dialog.window_text() == "KiCad 错误"


def test_dismiss_modal_error_dialog_clicks_confirm_button() -> None:
    class FakeButton:
        def __init__(self) -> None:
            self.clicked = False

        def click_input(self) -> None:
            self.clicked = True

    class FakeDialog:
        def __init__(self) -> None:
            self.button = FakeButton()

        def child_window(self, **kwargs):
            if kwargs.get("title") == "确定":
                return self.button
            if kwargs.get("automation_id") == "5100":
                return self.button
            return self.button

    driver = KiCadGuiDriver()

    dismissed = driver.dismiss_modal_error_dialog(FakeDialog())

    assert dismissed is True
    assert driver is not None


def test_dismiss_modal_error_dialog_falls_back_to_children_iteration() -> None:
    class FakeButton:
        def __init__(self) -> None:
            self.invoked = False

        def window_text(self) -> str:
            return "确定"

        def friendly_class_name(self) -> str:
            return "Button"

        def invoke(self) -> None:
            self.invoked = True

    class FakeDialog:
        def __init__(self) -> None:
            self.button = FakeButton()

        def child_window(self, **kwargs):
            raise RuntimeError(f"unsupported lookup: {kwargs}")

        def children(self):
            return [self.button]

    driver = KiCadGuiDriver()

    dismissed = driver.dismiss_modal_error_dialog(FakeDialog())

    assert dismissed is True


def test_prepare_uia_environment_injects_comtypes_gen_module(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import sys

    monkeypatch.delitem(sys.modules, "comtypes.gen", raising=False)

    class FakeComtypes:
        pass

    fake_comtypes = FakeComtypes()
    monkeypatch.setitem(sys.modules, "comtypes", fake_comtypes)

    cache_dir = _prepare_uia_environment(tmp_path / "artifacts")

    assert cache_dir is not None
    assert "comtypes.gen" in sys.modules


def test_menu_select_requires_real_main_window() -> None:
    driver = KiCadGuiDriver()

    with pytest.raises(NotImplementedError, match="main window"):
        driver.menu_select("文件(F)->导入")


def test_try_menu_paths_returns_false_when_paths_do_not_match() -> None:
    class FakeMainWindow:
        def menu_select(self, menu_path: str) -> None:
            raise RuntimeError(menu_path)

    driver = KiCadGuiDriver()
    driver._main_window = FakeMainWindow()

    ok = driver.try_menu_paths(["A", "B"])

    assert ok is False


def test_click_main_menu_item_falls_back_to_child_iteration() -> None:
    class FakeMenuItem:
        def __init__(self, title: str) -> None:
            self._title = title
            self.invoked = False

        def window_text(self) -> str:
            return self._title

        def friendly_class_name(self) -> str:
            return "MenuItem"

        def invoke(self) -> None:
            self.invoked = True

    class FakeMenuBar:
        def __init__(self) -> None:
            self.file_item = FakeMenuItem("文件 (F)")

        def friendly_class_name(self) -> str:
            return "Menu"

        def children(self):
            return [self.file_item]

    class FakeMainWrapper:
        def __init__(self) -> None:
            self.menu_bar = FakeMenuBar()

        def children(self):
            return [self.menu_bar]

    driver = KiCadGuiDriver()
    driver._main_window = object()
    driver._get_main_wrapper = lambda: FakeMainWrapper()

    ok = driver.click_main_menu_item("文件 (F)")

    assert ok is True


def test_press_dialog_button_prefers_invoke_then_click_methods() -> None:
    pass


def test_open_pcb_editor_uses_welcome_tile_fallback_when_command_has_no_response() -> None:
    class FakeMainWindow:
        handle = 99

    driver = KiCadGuiDriver()
    driver._get_win32_main_window = lambda: FakeMainWindow()
    response_checks = {"count": 0}
    fallback_calls: list[tuple[str, ...]] = []

    def fake_wait_for_response(*, editor_kind: str, timeout_seconds: int) -> bool:
        assert editor_kind == "pcb"
        assert timeout_seconds == 3
        response_checks["count"] += 1
        return False

    driver._wait_for_editor_launch_response = fake_wait_for_response
    driver._invoke_welcome_editor_tile = lambda titles: fallback_calls.append(tuple(titles)) or True

    import types
    import sys

    post_calls: list[tuple[int, int, int, int]] = []
    fake_win32con = types.SimpleNamespace(WM_COMMAND=273)
    fake_win32gui = types.SimpleNamespace(PostMessage=lambda *args: post_calls.append(args))
    sys.modules["win32con"] = fake_win32con
    sys.modules["win32gui"] = fake_win32gui

    driver.open_pcb_editor()

    assert response_checks["count"] == 1
    assert post_calls == [(99, 273, driver.MAIN_WINDOW_OPEN_PCB_EDITOR_COMMAND_ID, 0)]
    assert fallback_calls == [("PCB 编辑器", "PCB Editor")]


def test_press_dialog_button_prefers_invoke_then_click_methods() -> None:
    class FakeButton:
        def __init__(self) -> None:
            self.invoked = False

        def invoke(self) -> None:
            self.invoked = True

    driver = KiCadGuiDriver()

    ok = driver._press_dialog_button(FakeButton())

    assert ok is True


def test_activate_button_prefers_invoke_before_other_strategies() -> None:
    class FakeDialog:
        def set_focus(self) -> None:
            return None

    class FakeButton:
        def __init__(self) -> None:
            self.handle = 42
            self.invoked = False
            self.clicked = False
            self.click_input_called = False

        def set_focus(self) -> None:
            return None

        def invoke(self) -> None:
            self.invoked = True

        def click(self) -> None:
            self.clicked = True

        def click_input(self) -> None:
            self.click_input_called = True

    driver = KiCadGuiDriver()
    posted: list[int] = []
    driver._post_button_click = posted.append

    button = FakeButton()
    method = driver._activate_button(button, dialog=FakeDialog())

    assert method == "invoke"
    assert button.invoked is True
    assert button.clicked is False
    assert button.click_input_called is False
    assert posted == []


def test_activate_button_prefers_click_before_bm_click() -> None:
    class FakeDialog:
        def set_focus(self) -> None:
            return None

    class FakeButton:
        def __init__(self) -> None:
            self.handle = 42
            self.clicked = False
            self.click_input_called = False

        def set_focus(self) -> None:
            return None

        def click(self) -> None:
            self.clicked = True

        def click_input(self) -> None:
            self.click_input_called = True

    driver = KiCadGuiDriver()
    posted: list[int] = []
    driver._post_button_click = posted.append

    button = FakeButton()
    method = driver._activate_button(button, dialog=FakeDialog())

    assert method == "click"
    assert button.clicked is True
    assert button.click_input_called is False
    assert posted == []


def test_activate_button_prefers_bm_click_before_click_input_when_handle_exists() -> None:
    class FakeDialog:
        def set_focus(self) -> None:
            return None

    class FakeButton:
        def __init__(self) -> None:
            self.handle = 42
            self.click_input_called = False

        def set_focus(self) -> None:
            return None

        def click_input(self) -> None:
            self.click_input_called = True

    driver = KiCadGuiDriver()
    posted: list[int] = []
    driver._post_button_click = posted.append

    button = FakeButton()
    method = driver._activate_button(button, dialog=FakeDialog())

    assert method == "bm_click"
    assert button.click_input_called is False
    assert posted == [42]


def test_press_menu_item_methods_tries_expand_and_select_variants() -> None:
    class FakeMenuItem:
        def __init__(self) -> None:
            self.selected = False

        def expand(self) -> None:
            raise RuntimeError("expand failed")

        def select(self) -> None:
            self.selected = True

    driver = KiCadGuiDriver()

    ok = driver._press_menu_item(FakeMenuItem())

    assert ok is True


def test_select_input_file_falls_back_to_next_edit_when_first_is_not_actionable(tmp_path: Path) -> None:
    class FakeEdit:
        def __init__(self, *, should_fail: bool) -> None:
            self.should_fail = should_fail
            self.value: str | None = None

        def set_edit_text(self, value: str) -> None:
            if self.should_fail:
                raise RuntimeError("not actionable")
            self.value = value

    class FakeDialog:
        def __init__(self) -> None:
            self.edits = [FakeEdit(should_fail=True), FakeEdit(should_fail=False)]

        def children(self, *, class_name: str):
            if class_name == "Edit":
                return self.edits
            return []

    dialog = FakeDialog()
    driver = KiCadGuiDriver()
    driver._wait_for_window = lambda *args, **kwargs: dialog

    input_path = tmp_path / "demo.PrjPcb"
    driver.select_input_file(input_path)

    assert dialog.edits[1].value == str(input_path)
    assert driver._selected_input_path == input_path


def test_select_input_file_prefers_visible_edit_for_standalone_import(tmp_path: Path) -> None:
    class FakeEdit:
        def __init__(self, *, visible: bool) -> None:
            self.visible = visible
            self.value: str | None = None

        def is_visible(self) -> bool:
            return self.visible

        def is_enabled(self) -> bool:
            return True

        def set_edit_text(self, value: str) -> None:
            if not self.visible:
                raise RuntimeError("hidden edit should not be used first")
            self.value = value

    class FakeDialog:
        def __init__(self) -> None:
            self.edits = [FakeEdit(visible=False), FakeEdit(visible=True)]

        def children(self, *, class_name: str):
            if class_name == "Edit":
                return self.edits
            return []

    dialog = FakeDialog()
    driver = KiCadGuiDriver()
    driver._workflow_mode = "pcb_standalone_import"
    driver._active_dialog = dialog

    input_path = tmp_path / "demo.PcbDoc"
    driver.select_input_file(input_path)

    assert dialog.edits[1].value == str(input_path)


def test_select_input_file_uses_nested_edit_inside_file_dialog(tmp_path: Path) -> None:
    class FakeEdit:
        def __init__(self) -> None:
            self.value: str | None = None

        def is_visible(self) -> bool:
            return True

        def is_enabled(self) -> bool:
            return True

        def set_edit_text(self, value: str) -> None:
            self.value = value

        def window_text(self) -> str:
            return self.value or ""

        def children(self):
            return []

    class FakeComboBox:
        def __init__(self, edit: FakeEdit) -> None:
            self.edit = edit

        def children(self):
            return [self.edit]

    class FakeDialog:
        def __init__(self) -> None:
            self.edit = FakeEdit()
            self.combo = FakeComboBox(self.edit)

        def children(self, *, class_name: str | None = None):
            if class_name == "Edit":
                return []
            if class_name == "ComboBox":
                return [self.combo]
            if class_name is None:
                return [self.combo]
            return []

    dialog = FakeDialog()
    driver = KiCadGuiDriver()
    driver._workflow_mode = "schematic_standalone_import"
    driver._active_dialog = dialog

    input_path = tmp_path / "demo.SchDoc"
    driver.select_input_file(input_path)

    assert dialog.edit.value == str(input_path)
    assert driver._selected_input_path == input_path


def test_select_input_file_prefers_combobox_edit_over_generic_visible_edit(tmp_path: Path) -> None:
    class FakeRootEdit:
        def __init__(self) -> None:
            self.value: str | None = None

        def is_visible(self) -> bool:
            return True

        def is_enabled(self) -> bool:
            return True

        def set_edit_text(self, value: str) -> None:
            self.value = value

        def children(self):
            return []

    class FakeComboEdit(FakeRootEdit):
        def __init__(self, parent) -> None:
            super().__init__()
            self._parent = parent

        def parent(self):
            return self._parent

    class FakeComboBox:
        def __init__(self) -> None:
            self.edit = FakeComboEdit(self)

        def class_name(self) -> str:
            return "ComboBox"

        def children(self):
            return [self.edit]

    class FakeDialog:
        def __init__(self) -> None:
            self.root_edit = FakeRootEdit()
            self.combo = FakeComboBox()

        def children(self, *, class_name: str | None = None):
            if class_name == "Edit":
                return [self.root_edit]
            if class_name == "ComboBox":
                return [self.combo]
            if class_name is None:
                return [self.root_edit, self.combo]
            return []

    dialog = FakeDialog()
    driver = KiCadGuiDriver()
    driver._workflow_mode = "schematic_standalone_import"
    driver._active_dialog = dialog

    input_path = tmp_path / "demo.SchDoc"
    driver.select_input_file(input_path)

    assert dialog.combo.edit.value == str(input_path)
    assert dialog.root_edit.value is None
    assert driver._selected_input_path == input_path


def test_select_input_file_prefers_last_visible_combobox_edit_when_multiple_exist(tmp_path: Path) -> None:
    class FakeComboEdit:
        def __init__(self, parent, name: str) -> None:
            self._parent = parent
            self.name = name
            self.value: str | None = None

        def parent(self):
            return self._parent

        def is_visible(self) -> bool:
            return True

        def is_enabled(self) -> bool:
            return True

        def set_edit_text(self, value: str) -> None:
            self.value = value

        def children(self):
            return []

    class FakeComboBox:
        def __init__(self, name: str) -> None:
            self.edit = FakeComboEdit(self, name)

        def class_name(self) -> str:
            return "ComboBox"

        def children(self):
            return [self.edit]

    class FakeDialog:
        def __init__(self) -> None:
            self.address_combo = FakeComboBox("address")
            self.filename_combo = FakeComboBox("filename")

        def children(self, *, class_name: str | None = None):
            if class_name == "Edit":
                return []
            if class_name == "ComboBox":
                return [self.address_combo, self.filename_combo]
            if class_name is None:
                return [self.address_combo, self.filename_combo]
            return []

    dialog = FakeDialog()
    driver = KiCadGuiDriver()
    driver._workflow_mode = "schematic_standalone_import"
    driver._active_dialog = dialog

    input_path = tmp_path / "demo.SchDoc"
    driver.select_input_file(input_path)

    assert dialog.filename_combo.edit.value == str(input_path)
    assert dialog.address_combo.edit.value is None


def test_select_input_file_uses_bottom_combobox_edit_as_filename_when_discovery_order_is_reversed(
    tmp_path: Path,
) -> None:
    class FakeRect:
        def __init__(self, top: int, left: int) -> None:
            self.top = top
            self.left = left

    class FakeComboEdit:
        def __init__(self, parent, name: str, *, top: int) -> None:
            self._parent = parent
            self.name = name
            self.value: str | None = None
            self._rect = FakeRect(top=top, left=10)

        def parent(self):
            return self._parent

        def is_visible(self) -> bool:
            return True

        def is_enabled(self) -> bool:
            return True

        def set_edit_text(self, value: str) -> None:
            self.value = value

        def rectangle(self):
            return self._rect

        def children(self):
            return []

    class FakeComboBox:
        def __init__(self, name: str, *, top: int) -> None:
            self.edit = FakeComboEdit(self, name, top=top)

        def class_name(self) -> str:
            return "ComboBox"

        def children(self):
            return [self.edit]

    class FakeDialog:
        def __init__(self) -> None:
            self.address_combo = FakeComboBox("address", top=20)
            self.filename_combo = FakeComboBox("filename", top=400)

        def children(self, *, class_name: str | None = None):
            if class_name == "Edit":
                return []
            if class_name == "ComboBox":
                return [self.filename_combo, self.address_combo]
            if class_name is None:
                return [self.filename_combo, self.address_combo]
            return []

    dialog = FakeDialog()
    driver = KiCadGuiDriver()
    driver._workflow_mode = "pcb_standalone_import"
    driver._active_dialog = dialog

    input_path = tmp_path / "demo.PcbDoc"
    driver.select_input_file(input_path)

    assert dialog.filename_combo.edit.value == str(input_path)
    assert dialog.address_combo.edit.value is None


def test_select_input_file_prefers_standard_dialog_control_ids_over_discovery_order(
    tmp_path: Path,
) -> None:
    class FakeEdit:
        def __init__(self, parent, *, control_id: int) -> None:
            self._parent = parent
            self._control_id = control_id
            self.value: str | None = None

        def parent(self):
            return self._parent

        def control_id(self) -> int:
            return self._control_id

        def is_visible(self) -> bool:
            return True

        def is_enabled(self) -> bool:
            return True

        def set_edit_text(self, value: str) -> None:
            self.value = value

        def children(self):
            return []

    class FakeComboBox:
        def __init__(self, *, control_id: int) -> None:
            self._control_id = control_id
            self.edit = FakeEdit(self, control_id=control_id)

        def class_name(self) -> str:
            return "ComboBox"

        def control_id(self) -> int:
            return self._control_id

        def children(self):
            return [self.edit]

    class FakeDialog:
        def __init__(self) -> None:
            self.filename_combo = FakeComboBox(control_id=0x047C)
            self.address_combo = FakeComboBox(control_id=0x0471)

        def children(self, *, class_name: str | None = None):
            if class_name == "Edit":
                return []
            if class_name == "ComboBox":
                return [self.filename_combo, self.address_combo]
            if class_name is None:
                return [self.filename_combo, self.address_combo]
            return []

    dialog = FakeDialog()
    driver = KiCadGuiDriver()
    driver._workflow_mode = "pcb_standalone_import"
    driver._active_dialog = dialog

    input_path = tmp_path / "demo.PcbDoc"
    driver.select_input_file(input_path)

    assert dialog.filename_combo.edit.value == str(input_path)
    assert dialog.address_combo.edit.value is None


def test_set_edit_text_falls_back_to_set_window_text() -> None:
    class FakeEdit:
        def __init__(self) -> None:
            self.value: str | None = None

        def set_edit_text(self, value: str) -> None:
            raise RuntimeError("verify_actionable failed")

        def set_window_text(self, value: str) -> None:
            self.value = value

    edit = FakeEdit()

    KiCadGuiDriver._set_edit_text(edit, "demo")

    assert edit.value == "demo"


def test_wait_import_complete_accepts_standalone_schematic_editor_state(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    timeline = iter([0.0, 0.5, 0.6, 2.7, 2.8])
    monkeypatch.setattr("eda2kicad.gui.driver.time.monotonic", lambda: next(timeline))
    monkeypatch.setattr("eda2kicad.gui.driver.time.sleep", lambda _seconds: None)

    driver = KiCadGuiDriver()
    driver._workflow_mode = "schematic_standalone_import"
    driver._selected_input_path = tmp_path / "demo.SchDoc"
    driver._output_dir = tmp_path
    driver._dismiss_startup_error_dialog_if_present = lambda: False
    driver._handle_modal_import_dialog = lambda: False
    driver._find_progress_dialog = lambda: None
    driver._find_layer_mapping_dialog = lambda: None
    driver._find_project_window = lambda: object()
    driver._find_schematic_editor_window = lambda: object()
    driver._find_pcb_editor_window = lambda: None
    driver._editor_window_looks_stably_loaded = lambda editor: bool(editor)

    driver.wait_import_complete(timeout_seconds=5)


def test_wait_import_complete_requires_stable_editor_state_for_standalone_mode(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    timeline = iter([0.0, 0.5, 0.6, 2.7, 2.8, 5.2])
    monkeypatch.setattr("eda2kicad.gui.driver.time.monotonic", lambda: next(timeline))
    monkeypatch.setattr("eda2kicad.gui.driver.time.sleep", lambda _seconds: None)

    driver = KiCadGuiDriver()
    driver._workflow_mode = "schematic_standalone_import"
    driver._selected_input_path = tmp_path / "demo.SchDoc"
    driver._output_dir = tmp_path
    driver._dismiss_startup_error_dialog_if_present = lambda: False
    driver._handle_modal_import_dialog = lambda: False
    driver._find_progress_dialog = lambda: None
    driver._find_layer_mapping_dialog = lambda: None
    driver._find_project_window = lambda: None
    driver._find_schematic_editor_window = lambda: None
    driver._find_pcb_editor_window = lambda: None
    driver._editor_window_looks_stably_loaded = lambda editor: False

    with pytest.raises(ValueError, match="gui import did not reach a stable post-import state"):
        driver.wait_import_complete(timeout_seconds=5)


def test_wait_import_complete_does_not_finish_while_import_dialog_remains_open(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    timeline = iter([0.0, 0.5, 0.6, 2.7, 2.8, 5.2])
    monkeypatch.setattr("eda2kicad.gui.driver.time.monotonic", lambda: next(timeline))
    monkeypatch.setattr("eda2kicad.gui.driver.time.sleep", lambda _seconds: None)

    driver = KiCadGuiDriver()
    driver._workflow_mode = "schematic_standalone_import"
    driver._selected_input_path = tmp_path / "demo.SchDoc"
    driver._output_dir = tmp_path
    driver._dismiss_startup_error_dialog_if_present = lambda: False
    driver._handle_modal_import_dialog = lambda: False
    driver._find_progress_dialog = lambda: None
    driver._find_layer_mapping_dialog = lambda: None
    driver._find_project_window = lambda: object()
    driver._find_schematic_editor_window = lambda: object()
    driver._find_pcb_editor_window = lambda: None
    driver._find_import_dialog = lambda: object()
    driver._editor_window_looks_stably_loaded = lambda editor: bool(editor)

    with pytest.raises(ValueError, match="gui import did not reach a stable post-import state"):
        driver.wait_import_complete(timeout_seconds=5)


def test_validate_post_import_editor_state_rejects_untitled_schematic_editor() -> None:
    class FakeEditor:
        def window_text(self) -> str:
            return "untitled — 原理图编辑器"

    driver = KiCadGuiDriver()
    driver._workflow_mode = "schematic_standalone_import"
    driver._wait_for_window = lambda finder, timeout_seconds, error_message: finder()
    driver._find_schematic_editor_window = lambda: FakeEditor()

    with pytest.raises(ValueError, match="remained untitled"):
        driver.validate_post_import_editor_state()


def test_validate_post_import_editor_state_rejects_untitled_pcb_editor() -> None:
    class FakeEditor:
        def window_text(self) -> str:
            return "untitled — PCB Editor"

    driver = KiCadGuiDriver()
    driver._workflow_mode = "pcb_standalone_import"
    driver._wait_for_window = lambda finder, timeout_seconds, error_message: finder()
    driver._find_pcb_editor_window = lambda: FakeEditor()

    with pytest.raises(ValueError, match="remained untitled"):
        driver.validate_post_import_editor_state()


def test_editor_window_looks_stably_loaded_requires_named_clean_title() -> None:
    class FakeEditor:
        def __init__(self, title: str) -> None:
            self._title = title

        def window_text(self) -> str:
            return self._title

    driver = KiCadGuiDriver()

    assert driver._editor_window_looks_stably_loaded(FakeEditor("Demo — PCB 编辑器")) is True
    assert driver._editor_window_looks_stably_loaded(FakeEditor("*Demo [未保存] — PCB 编辑器")) is False
    assert driver._editor_window_looks_stably_loaded(FakeEditor("untitled — PCB 编辑器")) is False


def test_wait_import_complete_runs_dedicated_pcb_mapping_sequence_before_stability_check(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    timeline = iter([0.0, 0.5, 0.6, 2.7, 2.8])
    monkeypatch.setattr("eda2kicad.gui.driver.time.monotonic", lambda: next(timeline))
    monkeypatch.setattr("eda2kicad.gui.driver.time.sleep", lambda _seconds: None)

    driver = KiCadGuiDriver()
    driver._workflow_mode = "pcb_standalone_import"
    driver._selected_input_path = tmp_path / "demo.PcbDoc"
    driver._output_dir = tmp_path
    driver._dismiss_startup_error_dialog_if_present = lambda: False
    driver._handle_modal_import_dialog = lambda: False
    driver._find_progress_dialog = lambda: None
    driver._find_layer_mapping_dialog = lambda: None
    driver._find_project_window = lambda: object()
    driver._find_pcb_editor_window = lambda: object()
    driver._find_import_dialog = lambda: None

    calls: list[str] = []
    driver._complete_pcb_standalone_mapping_sequence = lambda *, deadline: calls.append("mapping")

    driver.wait_import_complete(timeout_seconds=5)

    assert calls == ["mapping"]
    assert driver._pcb_mapping_sequence_completed is True


def test_find_progress_dialog_ignores_standard_file_dialogs() -> None:
    class FakeDialog:
        def children(self, *, class_name: str):
            mapping = {
                "msctls_progress32": [object()],
                "Edit": [object()],
                "ComboBox": [object()],
                "Button": [object(), object()],
            }
            return mapping.get(class_name, [])

    driver = KiCadGuiDriver()
    driver._iter_dialogs = lambda: iter([FakeDialog()])

    assert driver._find_progress_dialog() is None


def test_find_progress_dialog_detects_top_level_progress_window() -> None:
    class FakeProgressWindow:
        def children(self, *, class_name: str):
            mapping = {
                "msctls_progress32": [object()],
                "Edit": [],
                "ComboBox": [],
                "Button": [object()],
            }
            return mapping.get(class_name, [])

    driver = KiCadGuiDriver()
    driver._iter_dialogs = lambda: iter([])
    driver._iter_win32_windows = lambda: iter([FakeProgressWindow()])

    assert driver._find_progress_dialog() is not None


def test_find_progress_dialog_ignores_hidden_progress_window() -> None:
    class FakeProgressWindow:
        def is_visible(self) -> bool:
            return False

        def children(self, *, class_name: str):
            mapping = {
                "msctls_progress32": [object()],
                "Edit": [],
                "ComboBox": [],
                "Button": [object()],
            }
            return mapping.get(class_name, [])

    driver = KiCadGuiDriver()
    driver._iter_dialogs = lambda: iter([])
    driver._iter_win32_windows = lambda: iter([FakeProgressWindow()])

    assert driver._find_progress_dialog() is None


def test_find_progress_dialog_ignores_primary_pcb_editor_window_even_if_it_has_progress_control() -> None:
    class FakeMenu:
        def items(self):
            return [object()] * 9

    class FakeEditorWindow:
        def is_visible(self) -> bool:
            return True

        def class_name(self) -> str:
            return "wxWindowNR"

        def window_text(self) -> str:
            return "*demo — PCB 编辑器"

        def menu(self):
            return FakeMenu()

        def children(self, *, class_name: str):
            mapping = {
                "msctls_progress32": [object()],
                "Edit": [],
                "ComboBox": [],
                "Button": [object()],
            }
            return mapping.get(class_name, [])

    driver = KiCadGuiDriver()
    driver._iter_dialogs = lambda: iter([])
    driver._iter_win32_windows = lambda: iter([FakeEditorWindow()])

    assert driver._find_progress_dialog() is None


def test_handle_modal_import_dialog_accepts_modified_board_confirmation() -> None:
    class FakeButton:
        def __init__(self, handle: int, title: str) -> None:
            self.handle = handle
            self._title = title

        def window_text(self) -> str:
            return self._title

    class FakeDialog:
        def __init__(self) -> None:
            self.buttons = [
                FakeButton(11, "保存"),
                FakeButton(22, "放弃更改"),
                FakeButton(33, "取消"),
            ]

        def children(self, *, class_name: str):
            if class_name == "Button":
                return self.buttons
            return []

    driver = KiCadGuiDriver()
    driver._find_unmatched_layers_dialog = lambda: None
    driver._workflow_mode = "pcb_standalone_import"
    driver._find_report_dialog = lambda: None
    driver._find_layer_mapping_dialog = lambda: None
    driver._find_acknowledgement_dialog = lambda: None
    driver._find_confirmation_dialog = lambda: FakeDialog()
    clicked: list[int] = []
    driver._post_button_click = clicked.append

    handled = driver._handle_modal_import_dialog()

    assert handled is True
    assert clicked == [22]


def test_handle_modal_import_dialog_auto_matches_layers_before_confirm() -> None:
    class FakeButton:
        def __init__(self, handle: int, title: str, control_id: int | None = None) -> None:
            self.handle = handle
            self._title = title
            self._control_id = control_id

        def window_text(self) -> str:
            return self._title

        def control_id(self) -> int:
            if self._control_id is None:
                raise RuntimeError("missing control id")
            return self._control_id

    class FakeDialog:
        def __init__(self) -> None:
            self.buttons = [
                FakeButton(11, "Cancel", 2),
                FakeButton(22, "Auto-Match Layers"),
                FakeButton(33, "OK", 1),
            ]

        def children(self, *, class_name: str):
            if class_name == "Button":
                return self.buttons
            return []

    driver = KiCadGuiDriver()
    driver._find_unmatched_layers_dialog = lambda: None
    driver._find_report_dialog = lambda: None
    driver._find_layer_mapping_dialog = lambda: FakeDialog()
    driver._find_acknowledgement_dialog = lambda: None
    driver._find_standalone_editor_replace_confirmation_dialog = lambda: None
    clicked: list[int] = []
    driver._post_button_click = clicked.append

    handled = driver._handle_modal_import_dialog()

    assert handled is True
    assert clicked == [22]
    assert driver._layer_mapping_auto_match_attempted is True


def test_handle_modal_import_dialog_confirms_layer_mapping_after_auto_match() -> None:
    class FakeButton:
        def __init__(self, handle: int, title: str, control_id: int | None = None) -> None:
            self.handle = handle
            self._title = title
            self._control_id = control_id

        def window_text(self) -> str:
            return self._title

        def control_id(self) -> int:
            if self._control_id is None:
                raise RuntimeError("missing control id")
            return self._control_id

    class FakeDialog:
        def __init__(self) -> None:
            self.buttons = [
                FakeButton(11, "Cancel", 2),
                FakeButton(22, "Auto-Match Layers"),
                FakeButton(33, "OK", 1),
            ]

        def children(self, *, class_name: str):
            if class_name == "Button":
                return self.buttons
            return []

    driver = KiCadGuiDriver()
    driver._layer_mapping_auto_match_attempted = True
    driver._layer_mapping_unmatched_acknowledged = True
    driver._find_unmatched_layers_dialog = lambda: None
    driver._find_report_dialog = lambda: None
    driver._find_layer_mapping_dialog = lambda: FakeDialog()
    driver._find_acknowledgement_dialog = lambda: None
    driver._find_standalone_editor_replace_confirmation_dialog = lambda: None
    clicked: list[int] = []
    driver._post_button_click = clicked.append

    handled = driver._handle_modal_import_dialog()

    assert handled is True
    assert clicked == [33]


def test_handle_modal_import_dialog_confirms_layer_mapping_when_unmatched_prompt_is_absent() -> None:
    class FakeButton:
        def __init__(self, handle: int, title: str, control_id: int | None = None) -> None:
            self.handle = handle
            self._title = title
            self._control_id = control_id

        def window_text(self) -> str:
            return self._title

        def control_id(self) -> int:
            if self._control_id is None:
                raise RuntimeError("missing control id")
            return self._control_id

    class FakeDialog:
        def __init__(self) -> None:
            self.buttons = [
                FakeButton(11, "未匹配层"),
                FakeButton(22, ">"),
                FakeButton(23, "<"),
                FakeButton(24, "<<"),
                FakeButton(25, "匹配的层"),
                FakeButton(26, "自动匹配的层"),
                FakeButton(33, "确定 (&O)", 1),
            ]

        def children(self, *, class_name: str):
            if class_name == "Button":
                return self.buttons
            return []

        def window_text(self) -> str:
            return "编辑已导入层的映射"

    driver = KiCadGuiDriver()
    driver._layer_mapping_auto_match_attempted = True
    driver._layer_mapping_unmatched_acknowledged = False
    driver._find_unmatched_layers_dialog = lambda: None
    driver._find_report_dialog = lambda: None
    driver._find_layer_mapping_dialog = lambda: FakeDialog()
    driver._find_acknowledgement_dialog = lambda: None
    driver._find_standalone_editor_replace_confirmation_dialog = lambda: None
    clicked: list[int] = []
    driver._activate_button = (
        lambda button, dialog=None, action_label=None: clicked.append(button.handle) or "click_input"
    )

    handled = driver._handle_modal_import_dialog()

    assert handled is True
    assert clicked == [33]
    assert driver._layer_mapping_unmatched_acknowledged is True


def test_handle_modal_import_dialog_prioritizes_unmatched_layers_error_before_layer_mapping() -> None:
    class FakeButton:
        def __init__(self, handle: int, title: str, control_id: int | None = None) -> None:
            self.handle = handle
            self._title = title
            self._control_id = control_id

        def window_text(self) -> str:
            return self._title

        def control_id(self) -> int:
            if self._control_id is None:
                raise RuntimeError("missing control id")
            return self._control_id

    class FakeErrorDialog:
        def __init__(self) -> None:
            self.button = FakeButton(11, "确定", 1)

        def children(self, *, class_name: str):
            if class_name == "Button":
                return [self.button]
            return []

        def window_text(self) -> str:
            return "未匹配层"

    class FakeMappingDialog:
        def __init__(self) -> None:
            self.buttons = [
                FakeButton(22, "自动匹配的层"),
                FakeButton(33, "确定", 1),
            ]

        def children(self, *, class_name: str):
            if class_name == "Button":
                return self.buttons
            return []

    driver = KiCadGuiDriver()
    driver._find_unmatched_layers_dialog = lambda: FakeErrorDialog()
    driver._find_report_dialog = lambda: None
    driver._find_layer_mapping_dialog = lambda: FakeMappingDialog()
    driver._find_acknowledgement_dialog = lambda: None
    driver._find_standalone_editor_replace_confirmation_dialog = lambda: None
    clicked: list[int] = []
    driver._post_button_click = clicked.append

    handled = driver._handle_modal_import_dialog()

    assert handled is True
    assert clicked == [11]


def test_complete_pcb_standalone_mapping_sequence_follows_manual_order(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("eda2kicad.gui.driver.time.sleep", lambda _seconds: None)
    timeline = iter([0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0])
    monkeypatch.setattr("eda2kicad.gui.driver.time.monotonic", lambda: next(timeline))

    class FakeButton:
        def __init__(self, handle: int, title: str, control_id: int | None = None) -> None:
            self.handle = handle
            self._title = title
            self._control_id = control_id

        def window_text(self) -> str:
            return self._title

        def control_id(self) -> int:
            if self._control_id is None:
                raise RuntimeError("missing control id")
            return self._control_id

    class FakeMappingDialog:
        def __init__(self) -> None:
            self.buttons = [
                FakeButton(11, "未匹配层"),
                FakeButton(12, ">"),
                FakeButton(13, "<"),
                FakeButton(14, "<<"),
                FakeButton(15, "匹配的层"),
                FakeButton(16, "自动匹配的层"),
                FakeButton(17, "确定 (&O)", 1),
            ]

        def children(self, *, class_name: str):
            if class_name == "Button":
                return self.buttons
            return []

        def window_text(self) -> str:
            return "编辑已导入层的映射"

    class FakeUnmatchedDialog:
        def __init__(self) -> None:
            self.buttons = [FakeButton(21, "确定", 1)]

        def children(self, *, class_name: str):
            if class_name == "Button":
                return self.buttons
            return []

        def window_text(self) -> str:
            return "未匹配层"

    driver = KiCadGuiDriver()
    state = {"value": "mapping"}
    clicks: list[int] = []

    def fake_find_mapping():
        return FakeMappingDialog() if state["value"] in {"mapping", "mapping_confirm"} else None

    def fake_find_unmatched():
        return FakeUnmatchedDialog() if state["value"] == "unmatched" else None

    def fake_activate(button, *, dialog=None, action_label=None):
        assert action_label in {
            "pcb_mapping_auto_match_method",
            "pcb_mapping_unmatched_ack_method",
            "pcb_mapping_confirm_method",
        }
        clicks.append(button.handle)
        if button.handle == 16:
            state["value"] = "unmatched"
        elif button.handle == 21:
            state["value"] = "mapping_confirm"
        elif button.handle == 17:
            state["value"] = "progress"
        return "click_input"

    driver._find_layer_mapping_dialog = fake_find_mapping
    driver._find_unmatched_layers_dialog = fake_find_unmatched
    driver._find_report_dialog = lambda: None
    driver._dismiss_startup_error_dialog_if_present = lambda: False
    driver._find_progress_dialog = lambda: object() if state["value"] == "progress" else None
    driver._activate_button = fake_activate

    driver._complete_pcb_standalone_mapping_sequence(deadline=1.0)

    assert clicks == [16, 21, 17]
    assert driver._layer_mapping_auto_match_attempted is True
    assert driver._layer_mapping_unmatched_acknowledged is True


def test_complete_pcb_standalone_mapping_sequence_allows_editor_ready_without_mapping_dialog(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("eda2kicad.gui.driver.time.sleep", lambda _seconds: None)
    timeline = iter([0.0, 0.1, 0.2, 0.3])
    monkeypatch.setattr("eda2kicad.gui.driver.time.monotonic", lambda: next(timeline))

    driver = KiCadGuiDriver()
    driver._find_layer_mapping_dialog = lambda: None
    driver._find_unmatched_layers_dialog = lambda: None
    driver._find_report_dialog = lambda: None
    driver._dismiss_startup_error_dialog_if_present = lambda: False
    driver._find_progress_dialog = lambda: None
    driver._find_pcb_editor_window = lambda: object()

    driver._complete_pcb_standalone_mapping_sequence(deadline=1.0)


def test_pick_layer_mapping_auto_match_button_prefers_auto_match_over_matched_layers() -> None:
    class FakeButton:
        def __init__(self, handle: int, title: str) -> None:
            self.handle = handle
            self._title = title

        def window_text(self) -> str:
            return self._title

    driver = KiCadGuiDriver()
    buttons = [
        FakeButton(11, "Matched Layers"),
        FakeButton(12, "Auto-Match Layers"),
        FakeButton(13, "OK"),
    ]

    chosen = driver._pick_layer_mapping_auto_match_button(buttons)

    assert chosen is buttons[1]


def test_find_layer_mapping_dialog_accepts_wxwindownr_modal_candidate() -> None:
    class FakeButton:
        def __init__(self, title: str) -> None:
            self._title = title

        def window_text(self) -> str:
            return self._title

    class FakeWindow:
        handle = 123

        def window_text(self) -> str:
            return "编辑已导入层的映射"

        def class_name(self) -> str:
            return "wxWindowNR"

        def children(self, *, class_name: str | None = None):
            if class_name == "Button":
                return [FakeButton("自动匹配的层"), FakeButton("确定")]
            return []

    driver = KiCadGuiDriver()
    driver._iter_dialogs = lambda: iter([])
    driver._iter_win32_windows = lambda: iter([FakeWindow()])

    dialog = driver._find_layer_mapping_dialog()

    assert dialog is not None


def test_find_layer_mapping_dialog_ignores_hidden_modal_candidate() -> None:
    class FakeButton:
        def __init__(self, title: str) -> None:
            self._title = title

        def window_text(self) -> str:
            return self._title

    class FakeWindow:
        handle = 123

        def is_visible(self) -> bool:
            return False

        def window_text(self) -> str:
            return "编辑已导入层的映射"

        def class_name(self) -> str:
            return "wxWindowNR"

        def children(self, *, class_name: str | None = None):
            if class_name == "Button":
                return [FakeButton("自动匹配的层"), FakeButton("确定")]
            return []

    driver = KiCadGuiDriver()
    driver._iter_dialogs = lambda: iter([])
    driver._iter_win32_windows = lambda: iter([FakeWindow()])

    dialog = driver._find_layer_mapping_dialog()

    assert dialog is None


def test_confirm_import_prefers_open_button_for_standalone_schematic_import(tmp_path: Path) -> None:
    class FakeButton:
        def __init__(self, handle: int, title: str) -> None:
            self.handle = handle
            self._title = title

        def window_text(self) -> str:
            return self._title

    class FakeDialog:
        def __init__(self) -> None:
            self.buttons = [
                FakeButton(11, "取消"),
                FakeButton(22, "打开"),
            ]

        def children(self, *, class_name: str):
            if class_name == "Button":
                return self.buttons
            return []

    driver = KiCadGuiDriver()
    driver._workflow_mode = "schematic_standalone_import"
    driver._selected_input_path = tmp_path / "demo.SchDoc"
    driver._active_dialog = FakeDialog()
    clicked: list[int] = []
    driver._post_button_click = clicked.append
    driver._wait_until_dialog_closes = lambda _dialog, timeout_seconds: None
    driver._control_exists = lambda _dialog: False
    driver._populate_file_dialog_path = lambda _dialog, _input_path: None

    driver.confirm_import(tmp_path / "out" / "demo.kicad_sch")

    assert clicked == [22]


def test_confirm_import_does_not_send_keyboard_fallback_for_standalone_schematic_import(
    tmp_path: Path,
) -> None:
    class FakeButton:
        def __init__(self, handle: int, title: str) -> None:
            self.handle = handle
            self._title = title
            self.clicked = False

        def window_text(self) -> str:
            return self._title

        def click_input(self) -> None:
            self.clicked = True

    class FakeDialog:
        def __init__(self) -> None:
            self.handle = 77
            self.buttons = [FakeButton(22, "打开")]
            self.focused = False

        def children(self, *, class_name: str):
            if class_name == "Button":
                return self.buttons
            return []

        def set_focus(self) -> None:
            self.focused = True

    dialog = FakeDialog()
    driver = KiCadGuiDriver()
    driver._workflow_mode = "schematic_standalone_import"
    driver._selected_input_path = tmp_path / "demo.SchDoc"
    driver._active_dialog = dialog
    driver._populate_file_dialog_path = lambda _dialog, _input_path: None
    posted: list[int] = []
    driver._post_button_click = posted.append
    keys: list[str] = []
    hotkeys: list[str] = []
    accepts: list[int] = []
    driver._send_dialog_keys = lambda _dialog, seq: keys.append(seq)
    driver._send_dialog_hotkey = lambda _dialog, seq: hotkeys.append(seq)
    driver._post_dialog_accept_command = lambda _dialog: accepts.append(_dialog.handle)
    driver._wait_until_dialog_closes = lambda _dialog, timeout_seconds: None
    driver._control_exists = lambda _dialog: False

    driver.confirm_import(tmp_path / "out" / "demo.kicad_sch")

    assert dialog.buttons[0].clicked is False
    assert posted == [22]
    assert keys == []
    assert hotkeys == []
    assert accepts == []


def test_confirm_import_prefers_idok_button_for_standard_file_dialog(tmp_path: Path) -> None:
    class FakeButton:
        def __init__(self, handle: int, title: str, control_id: int) -> None:
            self.handle = handle
            self._title = title
            self._control_id = control_id

        def window_text(self) -> str:
            return self._title

        def control_id(self) -> int:
            return self._control_id

    class FakeDialog:
        def __init__(self) -> None:
            self.buttons = [
                FakeButton(11, "取消", 2),
                FakeButton(22, "", 1),
                FakeButton(33, "帮助", 9),
            ]

        def children(self, *, class_name: str):
            if class_name == "Button":
                return self.buttons
            return []

    driver = KiCadGuiDriver()
    driver._workflow_mode = "pcb_standalone_import"
    driver._selected_input_path = tmp_path / "demo.PcbDoc"
    driver._active_dialog = FakeDialog()
    clicked: list[int] = []
    driver._post_button_click = clicked.append
    driver._wait_until_dialog_closes = lambda _dialog, timeout_seconds: None
    driver._control_exists = lambda _dialog: False
    driver._populate_file_dialog_path = lambda _dialog, _input_path: None

    driver.confirm_import(tmp_path / "out" / "demo.kicad_pcb")

    assert clicked == [22]


def test_confirm_import_prefers_visible_idok_button_when_hidden_duplicate_exists(tmp_path: Path) -> None:
    class FakeRect:
        def __init__(self, left: int, top: int, right: int, bottom: int) -> None:
            self.left = left
            self.top = top
            self.right = right
            self.bottom = bottom

    class FakeButton:
        def __init__(self, handle: int, title: str, control_id: int, *, visible: bool, rect: FakeRect) -> None:
            self.handle = handle
            self._title = title
            self._control_id = control_id
            self._visible = visible
            self._rect = rect

        def window_text(self) -> str:
            return self._title

        def control_id(self) -> int:
            return self._control_id

        def is_visible(self) -> bool:
            return self._visible

        def is_enabled(self) -> bool:
            return True

        def rectangle(self):
            return self._rect

    class FakeDialog:
        def __init__(self) -> None:
            self.handle = 77
            self.buttons = [
                FakeButton(11, "打开(&O)", 1, visible=False, rect=FakeRect(468, 565, 556, 595)),
                FakeButton(22, "打开(&O)", 1, visible=True, rect=FakeRect(451, 564, 539, 590)),
            ]

        def children(self, *, class_name: str):
            if class_name == "Button":
                return self.buttons
            return []

        def set_focus(self) -> None:
            return None

    dialog = FakeDialog()
    driver = KiCadGuiDriver()
    driver._workflow_mode = "pcb_standalone_import"
    driver._selected_input_path = tmp_path / "demo.PcbDoc"
    driver._active_dialog = dialog
    driver._populate_file_dialog_path = lambda _dialog, _input_path: None
    clicked_handles: list[int] = []
    driver._activate_button = (
        lambda button, dialog=None, action_label=None: clicked_handles.append(button.handle) or "click_input"
    )
    driver._wait_until_dialog_closes = lambda _dialog, timeout_seconds: None
    driver._control_exists = lambda _dialog: False

    driver.confirm_import(tmp_path / "out" / "demo.kicad_pcb")

    assert clicked_handles[0] == 22


def test_confirm_import_prefers_bm_click_before_click_input_for_standalone_import(tmp_path: Path) -> None:
    class FakeButton:
        def __init__(self, handle: int, title: str) -> None:
            self.handle = handle
            self._title = title
            self.clicked = False

        def window_text(self) -> str:
            return self._title

        def click_input(self) -> None:
            self.clicked = True

    class FakeDialog:
        def __init__(self) -> None:
            self.handle = 77
            self.buttons = [FakeButton(22, "鎵撳紑")]
            self.focused = False

        def children(self, *, class_name: str):
            if class_name == "Button":
                return self.buttons
            return []

        def set_focus(self) -> None:
            self.focused = True

    dialog = FakeDialog()
    driver = KiCadGuiDriver()
    driver._workflow_mode = "pcb_standalone_import"
    driver._selected_input_path = tmp_path / "demo.PcbDoc"
    driver._active_dialog = dialog
    driver._populate_file_dialog_path = lambda _dialog, _input_path: None
    posted: list[int] = []
    driver._post_button_click = posted.append
    keys: list[str] = []
    driver._send_dialog_keys = lambda _dialog, seq: keys.append(seq)
    hotkeys: list[str] = []
    driver._send_dialog_hotkey = lambda _dialog, seq: hotkeys.append(seq)
    accepts: list[int] = []
    driver._post_dialog_accept_command = lambda _dialog: accepts.append(_dialog.handle)
    driver._wait_until_dialog_closes = lambda _dialog, timeout_seconds: None
    driver._control_exists = lambda _dialog: False

    driver.confirm_import(tmp_path / "out" / "demo.kicad_pcb")

    assert dialog.buttons[0].clicked is False
    assert posted == [22]
    assert keys == []
    assert hotkeys == []
    assert accepts == []


def test_confirm_import_uses_bm_click_without_keyboard_fallback_for_standalone_import(
    tmp_path: Path,
) -> None:
    class FakeButton:
        def __init__(self, handle: int, title: str) -> None:
            self.handle = handle
            self._title = title

        def window_text(self) -> str:
            return self._title

    class FakeDialog:
        def __init__(self) -> None:
            self.handle = 77
            self.buttons = [FakeButton(22, "打开")]
            self.focused = False

        def children(self, *, class_name: str):
            if class_name == "Button":
                return self.buttons
            return []

        def set_focus(self) -> None:
            self.focused = True

    dialog = FakeDialog()
    driver = KiCadGuiDriver()
    driver._workflow_mode = "pcb_standalone_import"
    driver._selected_input_path = tmp_path / "demo.PcbDoc"
    driver._active_dialog = dialog
    driver._populate_file_dialog_path = lambda _dialog, _input_path: None
    posted: list[int] = []
    driver._post_button_click = posted.append
    keys: list[str] = []
    driver._send_dialog_keys = lambda _dialog, seq: keys.append(seq)
    hotkeys: list[str] = []
    driver._send_dialog_hotkey = lambda _dialog, seq: hotkeys.append(seq)
    accepts: list[int] = []
    driver._post_dialog_accept_command = lambda _dialog: accepts.append(_dialog.handle)
    driver._wait_until_dialog_closes = lambda _dialog, timeout_seconds: None
    driver._control_exists = lambda _dialog: False

    driver.confirm_import(tmp_path / "out" / "demo.kicad_pcb")

    assert dialog.focused is True
    assert posted == [22]
    assert keys == []
    assert hotkeys == []
    assert accepts == []


def test_confirm_import_reapplies_selected_path_when_filename_edit_is_empty(tmp_path: Path) -> None:
    class FakeEdit:
        def __init__(self) -> None:
            self.value = ""

        def window_text(self) -> str:
            return self.value

        def set_edit_text(self, value: str) -> None:
            self.value = value

        def parent(self):
            return FakeComboBox(self)

        def is_visible(self) -> bool:
            return True

        def is_enabled(self) -> bool:
            return True

        def children(self):
            return []

    class FakeComboBox:
        def __init__(self, edit: FakeEdit) -> None:
            self.edit = edit

        def class_name(self) -> str:
            return "ComboBox"

        def children(self):
            return [self.edit]

    class FakeButton:
        def __init__(self, handle: int, title: str) -> None:
            self.handle = handle
            self._title = title

        def window_text(self) -> str:
            return self._title

    class FakeDialog:
        def __init__(self) -> None:
            self.edit = FakeEdit()
            self.buttons = [FakeButton(22, "打开")]
            self.combo = FakeComboBox(self.edit)

        def children(self, *, class_name: str | None = None):
            if class_name == "Button":
                return self.buttons
            if class_name == "Edit":
                return []
            if class_name == "ComboBox":
                return [self.combo]
            if class_name is None:
                return [self.combo]
            return []

    dialog = FakeDialog()
    driver = KiCadGuiDriver()
    driver._workflow_mode = "schematic_standalone_import"
    driver._selected_input_path = tmp_path / "demo.SchDoc"
    driver._active_dialog = dialog
    clicked: list[int] = []
    driver._post_button_click = clicked.append
    driver._wait_until_dialog_closes = lambda _dialog, timeout_seconds: None
    driver._control_exists = lambda _dialog: False

    driver.confirm_import(tmp_path / "out" / "demo.kicad_sch")

    assert dialog.edit.value == str(tmp_path / "demo.SchDoc")
    assert clicked == [22]


def test_confirm_import_requires_file_dialog_to_close_for_standalone_import(tmp_path: Path) -> None:
    class FakeButton:
        def __init__(self, handle: int, title: str) -> None:
            self.handle = handle
            self._title = title

        def window_text(self) -> str:
            return self._title

    class FakeDialog:
        def __init__(self) -> None:
            self.buttons = [FakeButton(22, "打开")]

        def children(self, *, class_name: str):
            if class_name == "Button":
                return self.buttons
            return []

        def exists(self) -> bool:
            return True

    dialog = FakeDialog()
    driver = KiCadGuiDriver()
    driver._workflow_mode = "schematic_standalone_import"
    driver._selected_input_path = tmp_path / "demo.SchDoc"
    driver._active_dialog = dialog
    driver._wait_until_dialog_closes = lambda _dialog, timeout_seconds: None
    driver._post_button_click = lambda _handle: None
    driver._populate_file_dialog_path = lambda _dialog, _input_path: None

    with pytest.raises(ValueError, match="did not close after confirmation"):
        driver.confirm_import(tmp_path / "out" / "demo.kicad_sch")


def test_confirm_import_reapplies_directory_and_filename_when_multiple_combobox_edits_exist(
    tmp_path: Path,
) -> None:
    class FakeComboEdit:
        def __init__(self, parent, initial: str = "") -> None:
            self._parent = parent
            self.value = initial

        def window_text(self) -> str:
            return self.value

        def set_edit_text(self, value: str) -> None:
            self.value = value

        def parent(self):
            return self._parent

        def is_visible(self) -> bool:
            return True

        def is_enabled(self) -> bool:
            return True

        def children(self):
            return []

    class FakeComboBox:
        def __init__(self, initial: str = "") -> None:
            self.edit = FakeComboEdit(self, initial)

        def class_name(self) -> str:
            return "ComboBox"

        def children(self):
            return [self.edit]

    class FakeButton:
        def __init__(self, handle: int, title: str) -> None:
            self.handle = handle
            self._title = title

        def window_text(self) -> str:
            return self._title

    class FakeDialog:
        def __init__(self) -> None:
            self.address_combo = FakeComboBox("")
            self.filename_combo = FakeComboBox("")
            self.buttons = [FakeButton(22, "打开")]

        def children(self, *, class_name: str | None = None):
            if class_name == "Button":
                return self.buttons
            if class_name == "Edit":
                return []
            if class_name == "ComboBox":
                return [self.address_combo, self.filename_combo]
            if class_name is None:
                return [self.address_combo, self.filename_combo]
            return []

    dialog = FakeDialog()
    input_path = tmp_path / "nested" / "demo.SchDoc"
    driver = KiCadGuiDriver()
    driver._workflow_mode = "schematic_standalone_import"
    driver._selected_input_path = input_path
    driver._active_dialog = dialog
    clicked: list[int] = []
    driver._post_button_click = clicked.append
    driver._wait_until_dialog_closes = lambda _dialog, timeout_seconds: None
    driver._control_exists = lambda _dialog: False

    driver.confirm_import(tmp_path / "out" / "demo.kicad_sch")

    assert dialog.address_combo.edit.value == ""
    assert dialog.filename_combo.edit.value == str(input_path)
    assert clicked == [22]


def test_confirm_import_uses_bottom_combobox_edit_as_filename_when_discovery_order_is_reversed(
    tmp_path: Path,
) -> None:
    class FakeRect:
        def __init__(self, top: int, left: int) -> None:
            self.top = top
            self.left = left

    class FakeComboEdit:
        def __init__(self, parent, *, top: int, initial: str = "") -> None:
            self._parent = parent
            self.value = initial
            self._rect = FakeRect(top=top, left=10)

        def window_text(self) -> str:
            return self.value

        def set_edit_text(self, value: str) -> None:
            self.value = value

        def parent(self):
            return self._parent

        def is_visible(self) -> bool:
            return True

        def is_enabled(self) -> bool:
            return True

        def rectangle(self):
            return self._rect

        def children(self):
            return []

    class FakeComboBox:
        def __init__(self, *, top: int, initial: str = "") -> None:
            self.edit = FakeComboEdit(self, top=top, initial=initial)

        def class_name(self) -> str:
            return "ComboBox"

        def children(self):
            return [self.edit]

    class FakeButton:
        def __init__(self, handle: int, title: str) -> None:
            self.handle = handle
            self._title = title

        def window_text(self) -> str:
            return self._title

    class FakeDialog:
        def __init__(self) -> None:
            self.address_combo = FakeComboBox(top=20, initial="")
            self.filename_combo = FakeComboBox(top=400, initial="")
            self.buttons = [FakeButton(22, "打开")]

        def children(self, *, class_name: str | None = None):
            if class_name == "Button":
                return self.buttons
            if class_name == "Edit":
                return []
            if class_name == "ComboBox":
                return [self.filename_combo, self.address_combo]
            if class_name is None:
                return [self.filename_combo, self.address_combo]
            return []

    dialog = FakeDialog()
    input_path = tmp_path / "nested" / "demo.PcbDoc"
    driver = KiCadGuiDriver()
    driver._workflow_mode = "pcb_standalone_import"
    driver._selected_input_path = input_path
    driver._active_dialog = dialog
    clicked: list[int] = []
    driver._post_button_click = clicked.append
    driver._wait_until_dialog_closes = lambda _dialog, timeout_seconds: None
    driver._control_exists = lambda _dialog: False

    driver.confirm_import(tmp_path / "out" / "demo.kicad_pcb")

    assert dialog.address_combo.edit.value == ""
    assert dialog.filename_combo.edit.value == str(input_path)
    assert clicked == [22]


def test_confirm_import_prefers_standard_dialog_control_ids_over_discovery_order(
    tmp_path: Path,
) -> None:
    class FakeEdit:
        def __init__(self, parent, *, control_id: int, initial: str = "") -> None:
            self._parent = parent
            self._control_id = control_id
            self.value = initial

        def window_text(self) -> str:
            return self.value

        def set_edit_text(self, value: str) -> None:
            self.value = value

        def parent(self):
            return self._parent

        def control_id(self) -> int:
            return self._control_id

        def is_visible(self) -> bool:
            return True

        def is_enabled(self) -> bool:
            return True

        def children(self):
            return []

    class FakeComboBox:
        def __init__(self, *, control_id: int, initial: str = "") -> None:
            self._control_id = control_id
            self.edit = FakeEdit(self, control_id=control_id, initial=initial)

        def class_name(self) -> str:
            return "ComboBox"

        def control_id(self) -> int:
            return self._control_id

        def children(self):
            return [self.edit]

    class FakeButton:
        def __init__(self, handle: int, title: str) -> None:
            self.handle = handle
            self._title = title

        def window_text(self) -> str:
            return self._title

    class FakeDialog:
        def __init__(self) -> None:
            self.filename_combo = FakeComboBox(control_id=0x047C, initial="")
            self.address_combo = FakeComboBox(control_id=0x0471, initial="")
            self.buttons = [FakeButton(22, "打开")]

        def children(self, *, class_name: str | None = None):
            if class_name == "Button":
                return self.buttons
            if class_name == "Edit":
                return []
            if class_name == "ComboBox":
                return [self.filename_combo, self.address_combo]
            if class_name is None:
                return [self.filename_combo, self.address_combo]
            return []

    dialog = FakeDialog()
    input_path = tmp_path / "nested" / "demo.PcbDoc"
    driver = KiCadGuiDriver()
    driver._workflow_mode = "pcb_standalone_import"
    driver._selected_input_path = input_path
    driver._active_dialog = dialog
    clicked: list[int] = []
    driver._post_button_click = clicked.append
    driver._wait_until_dialog_closes = lambda _dialog, timeout_seconds: None
    driver._control_exists = lambda _dialog: False

    driver.confirm_import(tmp_path / "out" / "demo.kicad_pcb")

    assert dialog.filename_combo.edit.value == str(input_path)
    assert dialog.address_combo.edit.value == ""
    assert clicked == [22]


def test_open_schematic_editor_import_handles_intermediate_acknowledgement_before_file_dialog() -> None:
    class FakeWindow:
        def __init__(self, handle: int) -> None:
            self.handle = handle

    class FakeAckDialog:
        def __init__(self) -> None:
            self.buttons = [FakeWindow(33)]

        def children(self, *, class_name: str):
            if class_name == "Button":
                return self.buttons
            return []

    driver = KiCadGuiDriver()
    driver._find_schematic_editor_window = lambda: FakeWindow(11)
    ack_dialog = FakeAckDialog()
    calls = {"ack_checks": 0, "import_checks": 0}

    def fake_find_import_dialog():
        calls["import_checks"] += 1
        return FakeWindow(44) if calls["ack_checks"] >= 1 else None

    driver._find_import_dialog = fake_find_import_dialog

    def fake_find_ack():
        calls["ack_checks"] += 1
        return ack_dialog if calls["ack_checks"] == 1 else None

    driver._find_acknowledgement_dialog = fake_find_ack
    clicked: list[int] = []
    driver._post_button_click = clicked.append

    import types
    import sys

    fake_win32con = types.SimpleNamespace(WM_COMMAND=273)
    fake_win32gui = types.SimpleNamespace(PostMessage=lambda *args: None)
    sys.modules["win32con"] = fake_win32con
    sys.modules["win32gui"] = fake_win32gui

    driver.open_schematic_editor_import()

    assert clicked == [33]
    assert driver._active_dialog.handle == 44


def test_open_pcb_editor_import_discards_modified_board_before_file_dialog() -> None:
    class FakeWindow:
        def __init__(self, handle: int) -> None:
            self.handle = handle

    class FakeButton:
        def __init__(self, handle: int, title: str) -> None:
            self.handle = handle
            self._title = title

        def window_text(self) -> str:
            return self._title

    class FakeConfirmationDialog:
        def __init__(self) -> None:
            self.buttons = [
                FakeButton(11, "保存"),
                FakeButton(22, "放弃更改"),
                FakeButton(33, "取消"),
            ]

        def children(self, *, class_name: str):
            if class_name == "Button":
                return self.buttons
            return []

    driver = KiCadGuiDriver()
    driver._find_pcb_editor_window = lambda: FakeWindow(55)
    confirmation_dialog = FakeConfirmationDialog()
    calls = {"confirm_checks": 0, "import_checks": 0}

    def fake_find_import_dialog():
        calls["import_checks"] += 1
        return FakeWindow(66) if calls["confirm_checks"] >= 1 else None

    driver._find_import_dialog = fake_find_import_dialog

    def fake_find_confirmation():
        calls["confirm_checks"] += 1
        return confirmation_dialog if calls["confirm_checks"] == 1 else None

    driver._find_standalone_editor_replace_confirmation_dialog = fake_find_confirmation
    driver._find_acknowledgement_dialog = lambda: None
    clicked: list[int] = []
    driver._post_button_click = clicked.append

    import types
    import sys

    fake_win32con = types.SimpleNamespace(WM_COMMAND=273)
    fake_win32gui = types.SimpleNamespace(PostMessage=lambda *args: None)
    sys.modules["win32con"] = fake_win32con
    sys.modules["win32gui"] = fake_win32gui

    driver.open_pcb_editor_import()

    assert clicked == [22]
    assert driver._active_dialog.handle == 66


def test_find_standalone_editor_replace_confirmation_dialog_matches_three_button_discard_prompt() -> None:
    class FakeButton:
        def __init__(self, title: str) -> None:
            self._title = title

        def window_text(self) -> str:
            return self._title

    class FakeDialog:
        def __init__(self) -> None:
            self.buttons = [
                FakeButton("保存"),
                FakeButton("放弃变更"),
                FakeButton("取消"),
            ]

        def is_visible(self) -> bool:
            return True

        def children(self, *, class_name: str | None = None):
            if class_name == "Edit":
                return []
            if class_name == "ComboBox":
                return []
            if class_name == "Button":
                return self.buttons
            return self.buttons

    driver = KiCadGuiDriver()
    driver._workflow_mode = "pcb_standalone_import"
    driver._iter_modal_candidates = lambda: iter([FakeDialog()])

    dialog = driver._find_standalone_editor_replace_confirmation_dialog()

    assert dialog is not None


def test_open_pcb_editor_import_waits_for_create_pcb_progress_to_finish_before_import() -> None:
    class FakeWindow:
        def __init__(self, handle: int) -> None:
            self.handle = handle

    driver = KiCadGuiDriver()
    driver._find_pcb_editor_window = lambda: FakeWindow(55)
    progress_checks = {"count": 0}

    def fake_find_progress_dialog():
        progress_checks["count"] += 1
        return object() if progress_checks["count"] == 1 else None

    driver._find_progress_dialog = fake_find_progress_dialog
    driver._find_standalone_editor_replace_confirmation_dialog = lambda: None
    driver._find_acknowledgement_dialog = lambda: None
    driver._find_import_dialog = lambda: FakeWindow(66) if progress_checks["count"] >= 2 else None

    import types
    import sys

    post_calls: list[tuple[int, int, int, int]] = []
    fake_win32con = types.SimpleNamespace(WM_COMMAND=273)
    fake_win32gui = types.SimpleNamespace(PostMessage=lambda *args: post_calls.append(args))
    sys.modules["win32con"] = fake_win32con
    sys.modules["win32gui"] = fake_win32gui

    original_sleep = __import__("eda2kicad.gui.driver", fromlist=["time"]).time.sleep
    __import__("eda2kicad.gui.driver", fromlist=["time"]).time.sleep = lambda _seconds: None
    try:
        driver.open_pcb_editor_import()
    finally:
        __import__("eda2kicad.gui.driver", fromlist=["time"]).time.sleep = original_sleep

    assert progress_checks["count"] >= 2
    assert post_calls == [(55, 273, driver.PCB_EDITOR_NON_KICAD_IMPORT_COMMAND_ID, 0)]
    assert driver._active_dialog.handle == 66


def test_open_pcb_editor_import_allows_import_when_editor_is_visible_even_if_progress_probe_lingers() -> None:
    class FakeWindow:
        def __init__(self, handle: int) -> None:
            self.handle = handle

    driver = KiCadGuiDriver()
    driver._find_pcb_editor_window = lambda: FakeWindow(55)
    driver._find_progress_dialog = lambda: object()
    driver._find_confirmation_dialog = lambda: None
    driver._find_standalone_editor_replace_confirmation_dialog = lambda: None
    driver._find_acknowledgement_dialog = lambda: None
    driver._find_import_dialog = lambda: FakeWindow(66)

    import types
    import sys

    post_calls: list[tuple[int, int, int, int]] = []
    fake_win32con = types.SimpleNamespace(WM_COMMAND=273)
    fake_win32gui = types.SimpleNamespace(PostMessage=lambda *args: post_calls.append(args))
    sys.modules["win32con"] = fake_win32con
    sys.modules["win32gui"] = fake_win32gui

    driver.open_pcb_editor_import()

    assert post_calls == [(55, 273, driver.PCB_EDITOR_NON_KICAD_IMPORT_COMMAND_ID, 0)]
    assert driver._active_dialog.handle == 66


def test_retry_confirm_skips_stale_hidden_dialog_without_reclicking() -> None:
    class FakeButton:
        def __init__(self, handle: int) -> None:
            self.handle = handle

        def window_text(self) -> str:
            return "打开(&O)"

        def is_visible(self) -> bool:
            return False

        def is_enabled(self) -> bool:
            return False

    class FakeDialog:
        def __init__(self) -> None:
            self.buttons = [FakeButton(22)]

        def is_visible(self) -> bool:
            return False

        def children(self, *, class_name: str | None = None):
            if class_name == "Button":
                return self.buttons
            return []

    driver = KiCadGuiDriver()
    driver._workflow_mode = "schematic_standalone_import"
    driver._find_import_dialog = lambda: FakeDialog()
    clicked: list[int] = []
    driver._activate_button = (
        lambda button, dialog=None, action_label=None: clicked.append(button.handle) or "bm_click"
    )

    still_visible = driver._retry_confirm_if_dialog_still_visible()

    assert still_visible is False
    assert clicked == []


def test_open_pcb_editor_import_waits_for_top_level_create_pcb_progress_window() -> None:
    class FakeWindow:
        def __init__(self, handle: int) -> None:
            self.handle = handle

    class FakeProgressWindow:
        def children(self, *, class_name: str):
            mapping = {
                "msctls_progress32": [object()],
                "Edit": [],
                "ComboBox": [],
                "Button": [object()],
            }
            return mapping.get(class_name, [])

    driver = KiCadGuiDriver()
    driver._find_pcb_editor_window = lambda: FakeWindow(55)
    progress_checks = {"count": 0}

    def fake_iter_win32_windows():
        progress_checks["count"] += 1
        if progress_checks["count"] == 1:
            return iter([FakeProgressWindow(), FakeWindow(55)])
        return iter([FakeWindow(55)])

    driver._iter_win32_windows = fake_iter_win32_windows
    driver._iter_dialogs = lambda: iter([])
    driver._find_standalone_editor_replace_confirmation_dialog = lambda: None
    driver._find_acknowledgement_dialog = lambda: None
    driver._find_import_dialog = lambda: FakeWindow(66) if progress_checks["count"] >= 2 else None

    import types
    import sys

    post_calls: list[tuple[int, int, int, int]] = []
    fake_win32con = types.SimpleNamespace(WM_COMMAND=273)
    fake_win32gui = types.SimpleNamespace(PostMessage=lambda *args: post_calls.append(args))
    sys.modules["win32con"] = fake_win32con
    sys.modules["win32gui"] = fake_win32gui

    original_sleep = __import__("eda2kicad.gui.driver", fromlist=["time"]).time.sleep
    __import__("eda2kicad.gui.driver", fromlist=["time"]).time.sleep = lambda _seconds: None
    try:
        driver.open_pcb_editor_import()
    finally:
        __import__("eda2kicad.gui.driver", fromlist=["time"]).time.sleep = original_sleep

    assert progress_checks["count"] >= 2
    assert post_calls == [(55, 273, driver.PCB_EDITOR_NON_KICAD_IMPORT_COMMAND_ID, 0)]
    assert driver._active_dialog.handle == 66

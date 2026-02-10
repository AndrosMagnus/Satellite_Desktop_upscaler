from __future__ import annotations

import os
import tempfile
import unittest


try:
    from PySide6 import QtWidgets

    PYSIDE_AVAILABLE = True
except ImportError:
    PYSIDE_AVAILABLE = False


class _FakeNotificationManager:
    def __init__(self) -> None:
        self.enabled = False
        self.calls: list[tuple[str, str]] = []

    def set_enabled(self, enabled: bool) -> None:
        self.enabled = enabled

    def notify(
        self, title: str, message: str, parent: QtWidgets.QWidget | None = None
    ) -> bool:
        if not self.enabled:
            return False
        self.calls.append((title, message))
        return True


@unittest.skipUnless(PYSIDE_AVAILABLE, "PySide6 is required for notification tests")
class TestCompletionNotifications(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        cls.app = QtWidgets.QApplication.instance()
        if cls.app is None:
            cls.app = QtWidgets.QApplication([])

    def _add_temp_input(self, window: "QtWidgets.QMainWindow") -> str:
        handle = tempfile.NamedTemporaryFile(delete=False, suffix=".tif")
        handle.close()
        window.input_list.add_paths([handle.name])
        window.input_list.clearSelection()
        for index in range(window.input_list.count() - 1, -1, -1):
            item = window.input_list.item(index)
            if item is None:
                continue
            if item.text() == handle.name:
                item.setSelected(True)
                window.input_list.setCurrentRow(index)
                break
        QtWidgets.QApplication.processEvents()
        return handle.name

    def _flush_events(self) -> None:
        QtWidgets.QApplication.processEvents()
        QtWidgets.QApplication.processEvents()

    def test_completion_notifications_are_optional(self) -> None:
        from app.ui import MainWindow

        fake_manager = _FakeNotificationManager()
        window = MainWindow(notification_manager=fake_manager)
        notification_check = window.advanced_options_panel.completion_notification_check

        temp_path = self._add_temp_input(window)
        window._start_run()
        self._flush_events()
        self.assertEqual(fake_manager.calls, [])

        notification_check.setChecked(True)
        self.assertTrue(fake_manager.enabled)
        window._start_run()
        self._flush_events()

        self.assertEqual(
            fake_manager.calls,
            [("Run complete", "Run finished. You're ready for the next step.")],
        )
        os.unlink(temp_path)

    def test_notification_manager_disabled_by_default(self) -> None:
        from app.ui import MainWindow

        fake_manager = _FakeNotificationManager()
        fake_manager.enabled = True

        window = MainWindow(notification_manager=fake_manager)
        notification_check = window.advanced_options_panel.completion_notification_check

        self.assertFalse(notification_check.isChecked())
        self.assertFalse(fake_manager.enabled)

        temp_path = self._add_temp_input(window)
        window._start_run()
        self._flush_events()
        self.assertEqual(fake_manager.calls, [])
        os.unlink(temp_path)

    def test_export_stage_click_does_not_emit_completion_notification(self) -> None:
        from app.ui import MainWindow

        fake_manager = _FakeNotificationManager()
        window = MainWindow(notification_manager=fake_manager)
        notification_check = window.advanced_options_panel.completion_notification_check
        notification_check.setChecked(True)

        window._handle_export_stage()
        self._flush_events()
        self.assertEqual(fake_manager.calls, [])

    def test_export_completion_notification_signal(self) -> None:
        from app.ui import MainWindow

        fake_manager = _FakeNotificationManager()
        window = MainWindow(notification_manager=fake_manager)
        notification_check = window.advanced_options_panel.completion_notification_check
        notification_check.setChecked(True)

        window._schedule_export_completion()
        self._flush_events()
        self.assertEqual(
            fake_manager.calls,
            [("Export complete", "Export finished. You're ready for the next step.")],
        )

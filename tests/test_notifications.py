from __future__ import annotations

import os
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

    def test_completion_notifications_are_optional(self) -> None:
        from app.ui import MainWindow

        fake_manager = _FakeNotificationManager()
        window = MainWindow(notification_manager=fake_manager)
        notification_check = window.advanced_options_panel.completion_notification_check

        window.workflow_stage_actions[4].click()
        self.assertEqual(fake_manager.calls, [])

        notification_check.setChecked(True)
        self.assertTrue(fake_manager.enabled)
        window.workflow_stage_actions[4].click()

        self.assertEqual(
            fake_manager.calls,
            [("Run complete", "Run finished. You're ready for the next step.")],
        )

    def test_notification_manager_disabled_by_default(self) -> None:
        from app.ui import MainWindow

        fake_manager = _FakeNotificationManager()
        fake_manager.enabled = True

        window = MainWindow(notification_manager=fake_manager)
        notification_check = window.advanced_options_panel.completion_notification_check

        self.assertFalse(notification_check.isChecked())
        self.assertFalse(fake_manager.enabled)

        window.workflow_stage_actions[4].click()
        self.assertEqual(fake_manager.calls, [])

    def test_export_completion_notification(self) -> None:
        from app.ui import MainWindow

        fake_manager = _FakeNotificationManager()
        window = MainWindow(notification_manager=fake_manager)
        notification_check = window.advanced_options_panel.completion_notification_check
        notification_check.setChecked(True)

        window.workflow_stage_actions[5].click()
        self.assertEqual(
            fake_manager.calls,
            [("Export complete", "Export finished. You're ready for the next step.")],
        )

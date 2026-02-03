from __future__ import annotations

import os
import unittest

from app.error_handling import UserFacingError, as_user_facing_error

try:
    from PySide6 import QtWidgets

    PYSIDE_AVAILABLE = True
except ImportError:
    PYSIDE_AVAILABLE = False


class TestErrorHandling(unittest.TestCase):
    def test_as_user_facing_error_wraps_missing_file(self) -> None:
        error = as_user_facing_error(FileNotFoundError("missing"))
        self.assertEqual(error.title, "File not found")
        self.assertEqual(error.error_code, "IO-001")
        self.assertGreater(len(error.suggested_fixes), 0)

    def test_user_facing_error_string_includes_code(self) -> None:
        error = UserFacingError(
            title="Example",
            summary="Something failed",
            suggested_fixes=("Fix it",),
            error_code="EX-001",
        )
        self.assertIn("EX-001", str(error))


@unittest.skipUnless(PYSIDE_AVAILABLE, "PySide6 is required for error dialog tests")
class TestErrorDialog(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        cls.app = QtWidgets.QApplication.instance()
        if cls.app is None:
            cls.app = QtWidgets.QApplication([])

    def test_error_dialog_retries(self) -> None:
        from app.ui import ErrorDialog

        calls: list[str] = []

        def retry() -> None:
            calls.append("retry")

        error = UserFacingError(
            title="Run failed",
            summary="We could not start the run.",
            suggested_fixes=("Try again.", "Check your inputs."),
            error_code="RUN-001",
            can_retry=True,
        )
        dialog = ErrorDialog(error, retry_action=retry)

        self.assertEqual(dialog.windowTitle(), "Run failed")
        self.assertIsNotNone(dialog.retry_button)
        dialog.retry_button.click()
        self.assertEqual(calls, ["retry"])

    def test_error_dialog_without_retry(self) -> None:
        from app.ui import ErrorDialog

        error = UserFacingError(
            title="Run failed",
            summary="We could not start the run.",
            suggested_fixes=(),
            error_code="RUN-002",
            can_retry=False,
        )
        dialog = ErrorDialog(error, retry_action=None)
        self.assertIsNone(dialog.retry_button)

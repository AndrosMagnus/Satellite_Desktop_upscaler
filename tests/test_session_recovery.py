import json
import os
import tempfile
import unittest


try:
    from PySide6 import QtWidgets

    PYSIDE_AVAILABLE = True
except ImportError:
    PYSIDE_AVAILABLE = False


@unittest.skipUnless(PYSIDE_AVAILABLE, "PySide6 is required for session recovery tests")
class TestSessionRecovery(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        cls.app = QtWidgets.QApplication.instance()
        if cls.app is None:
            cls.app = QtWidgets.QApplication([])

    def _set_session_env(self, path: str) -> None:
        old_value = os.environ.get("SAT_UPSCALE_SESSION_PATH")
        os.environ["SAT_UPSCALE_SESSION_PATH"] = path

        def _restore() -> None:
            if old_value is None:
                os.environ.pop("SAT_UPSCALE_SESSION_PATH", None)
            else:
                os.environ["SAT_UPSCALE_SESSION_PATH"] = old_value

        self.addCleanup(_restore)

    def test_restores_when_previous_session_dirty(self) -> None:
        from app.ui import MainWindow

        with tempfile.TemporaryDirectory() as tmpdir:
            session_path = os.path.join(tmpdir, "session.json")
            self._set_session_env(session_path)
            payload = {
                "dirty": True,
                "paths": ["/tmp/input_a.tif", "/tmp/input_b.tif"],
                "selected_paths": ["/tmp/input_b.tif"],
            }
            with open(session_path, "w", encoding="utf-8") as handle:
                json.dump(payload, handle)

            window = MainWindow()
            self.addCleanup(window.close)

            self.assertEqual(window.input_list.count(), 2)
            self.assertEqual(window.input_list.item(0).text(), "/tmp/input_a.tif")
            self.assertEqual(window.input_list.item(1).text(), "/tmp/input_b.tif")
            selected = [item.text() for item in window.input_list.selectedItems()]
            self.assertEqual(selected, ["/tmp/input_b.tif"])

    def test_ignores_clean_previous_session(self) -> None:
        from app.ui import MainWindow

        with tempfile.TemporaryDirectory() as tmpdir:
            session_path = os.path.join(tmpdir, "session.json")
            self._set_session_env(session_path)
            payload = {
                "dirty": False,
                "paths": ["/tmp/input_a.tif"],
                "selected_paths": ["/tmp/input_a.tif"],
            }
            with open(session_path, "w", encoding="utf-8") as handle:
                json.dump(payload, handle)

            window = MainWindow()
            self.addCleanup(window.close)

            self.assertEqual(window.input_list.count(), 1)
            self.assertEqual(window.input_list.item(0).text(), window.input_list.placeholder_text)

    def test_autosave_captures_current_state(self) -> None:
        from app.ui import MainWindow

        with tempfile.TemporaryDirectory() as tmpdir:
            session_path = os.path.join(tmpdir, "session.json")
            self._set_session_env(session_path)

            window = MainWindow()
            self.addCleanup(window.close)

            if os.path.exists(session_path):
                os.remove(session_path)

            window.input_list.clear()
            window.input_list.addItem("/tmp/autosave_input.tif")
            window._autosave_session_state()

            with open(session_path, "r", encoding="utf-8") as handle:
                payload = json.load(handle)

            self.assertEqual(payload["paths"], ["/tmp/autosave_input.tif"])
            self.assertTrue(payload["dirty"])


if __name__ == "__main__":
    unittest.main()

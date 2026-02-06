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
            cache_dir = os.path.join(tmpdir, "models")
            window.model_manager_panel.set_model_cache_dir(cache_dir)
            window._autosave_session_state()

            with open(session_path, "r", encoding="utf-8") as handle:
                payload = json.load(handle)

            self.assertEqual(payload["paths"], ["/tmp/autosave_input.tif"])
            self.assertEqual(payload["model_cache_dir"], cache_dir)
            self.assertTrue(payload["dirty"])

    def test_restores_preferences_from_dirty_session(self) -> None:
        from app.ui import MainWindow

        with tempfile.TemporaryDirectory() as tmpdir:
            session_path = os.path.join(tmpdir, "session.json")
            self._set_session_env(session_path)
            cache_dir = os.path.join(tmpdir, "models")
            payload = {
                "dirty": True,
                "paths": ["/tmp/input_a.tif"],
                "selected_paths": ["/tmp/input_a.tif"],
                "export_preset": "Landsat",
                "band_handling": "All bands",
                "output_format": "PNG",
                "comparison_mode": True,
                "comparison_model_a": "Satlas",
                "comparison_model_b": "SwinIR",
                "model_cache_dir": cache_dir,
                "advanced_scale": "8x",
                "advanced_tiling": "1024 px",
                "advanced_precision": "FP32",
                "advanced_compute": "CPU",
                "advanced_seam_blend": True,
                "advanced_safe_mode": False,
                "advanced_notifications": True,
            }
            with open(session_path, "w", encoding="utf-8") as handle:
                json.dump(payload, handle)

            window = MainWindow()
            self.addCleanup(window.close)

            preset_item = window.export_presets_panel.preset_list.currentItem()
            self.assertIsNotNone(preset_item)
            self.assertEqual(preset_item.text(), "Landsat")
            self.assertEqual(
                window.export_presets_panel.band_handling_combo.currentText(),
                "All bands",
            )
            self.assertEqual(
                window.export_presets_panel.output_format_combo.currentText(),
                "PNG",
            )

            comparison_panel = window.model_comparison_panel
            self.assertEqual(
                comparison_panel.mode_combo.currentText(),
                "Model comparison",
            )
            self.assertEqual(comparison_panel.model_a_combo.currentText(), "Satlas")
            self.assertEqual(comparison_panel.model_b_combo.currentText(), "SwinIR")
            self.assertEqual(
                window.model_manager_panel.cache_dir_input.text(),
                cache_dir,
            )

            advanced_panel = window.advanced_options_panel
            self.assertFalse(advanced_panel.safe_mode_check.isChecked())
            self.assertEqual(advanced_panel.scale_combo.currentText(), "8x")
            self.assertEqual(advanced_panel.tiling_combo.currentText(), "1024 px")
            self.assertEqual(advanced_panel.precision_combo.currentText(), "FP32")
            self.assertEqual(advanced_panel.compute_combo.currentText(), "CPU")
            self.assertTrue(advanced_panel.seam_blend_check.isChecked())
            self.assertTrue(advanced_panel.completion_notification_check.isChecked())


if __name__ == "__main__":
    unittest.main()

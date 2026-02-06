import os
import unittest


try:
    from PySide6 import QtWidgets

    PYSIDE_AVAILABLE = True
except ImportError:
    PYSIDE_AVAILABLE = False


@unittest.skipUnless(PYSIDE_AVAILABLE, "PySide6 is required for workflow stage tests")
class TestWorkflowStageActions(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        cls.app = QtWidgets.QApplication.instance()
        if cls.app is None:
            cls.app = QtWidgets.QApplication([])

    def test_import_stage_sets_message(self) -> None:
        from app.ui import MainWindow

        window = MainWindow()
        window.workflow_stage_actions[0].click()
        QtWidgets.QApplication.processEvents()
        self.assertEqual(
            window.status_bar.currentMessage(),
            "Import: add files or folders to begin.",
        )

    def test_review_stage_requires_selection(self) -> None:
        from app.ui import MainWindow

        window = MainWindow()
        window.workflow_stage_actions[1].click()
        QtWidgets.QApplication.processEvents()
        self.assertEqual(
            window.status_bar.currentMessage(),
            "Review: select a file to inspect preview and metadata.",
        )

    def test_stitch_stage_requires_multiple_tiles(self) -> None:
        from app.ui import MainWindow

        window = MainWindow()
        window.workflow_stage_actions[2].click()
        QtWidgets.QApplication.processEvents()
        self.assertEqual(
            window.status_bar.currentMessage(),
            "Stitch: select at least two tiles to preview mosaic bounds.",
        )

    def test_recommend_stage_updates_preset(self) -> None:
        from app.ui import MainWindow

        window = MainWindow()
        window.input_list.add_paths(["/tmp/landsat_scene.tif"])
        window.input_list.clearSelection()
        window.input_list.item(0).setSelected(True)
        QtWidgets.QApplication.processEvents()

        window.workflow_stage_actions[3].click()
        QtWidgets.QApplication.processEvents()

        self.assertEqual(
            window.export_presets_panel.recommended_combo.currentText(),
            "Landsat",
        )
        self.assertEqual(
            window.status_bar.currentMessage(),
            "Recommend: suggested preset 'Landsat' ready.",
        )

    def test_recommend_stage_handles_ambiguity(self) -> None:
        from app.ui import MainWindow

        window = MainWindow()
        window.export_presets_panel.recommended_combo.setCurrentText("PlanetScope")
        window.input_list.add_paths(["/tmp/sentinel_landsat_s2a_lc08_scene.tif"])
        window.input_list.clearSelection()
        window.input_list.item(0).setSelected(True)
        QtWidgets.QApplication.processEvents()

        window.workflow_stage_actions[3].click()
        QtWidgets.QApplication.processEvents()

        self.assertEqual(
            window.export_presets_panel.recommended_combo.currentText(),
            "PlanetScope",
        )
        message = window.status_bar.currentMessage()
        self.assertIn("Recommend: multiple providers match", message)
        self.assertIn("Landsat", message)
        self.assertIn("Sentinel-2", message)

    def test_export_stage_sets_message(self) -> None:
        from app.ui import MainWindow

        window = MainWindow()
        window.workflow_stage_actions[5].click()
        QtWidgets.QApplication.processEvents()
        self.assertEqual(
            window.status_bar.currentMessage(),
            "Export: confirm the preset and output format before saving outputs.",
        )

import os
import unittest


try:
    from PySide6 import QtCore, QtWidgets

    PYSIDE_AVAILABLE = True
except ImportError:
    PYSIDE_AVAILABLE = False


@unittest.skipUnless(PYSIDE_AVAILABLE, "PySide6 is required for mosaic hint tests")
class TestMosaicHint(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        cls.app = QtWidgets.QApplication.instance()
        if cls.app is None:
            cls.app = QtWidgets.QApplication([])

    def test_mosaic_hint_on_multiple_selection(self) -> None:
        from app.ui import MainWindow

        window = MainWindow()
        window.input_list.add_paths(
            [
                "/tmp/scene_r0_c0.tif",
                "/tmp/scene_r0_c1.tif",
            ]
        )
        window.input_list.setCurrentRow(
            0, QtCore.QItemSelectionModel.SelectionFlag.Select
        )
        window.input_list.setCurrentRow(
            1, QtCore.QItemSelectionModel.SelectionFlag.Select
        )
        QtWidgets.QApplication.processEvents()

        summary = window.metadata_summary.text().lower()
        self.assertIn("mosaic", summary)
        self.assertIn("stitch", summary)
        self.assertNotEqual(
            window.metadata_value_labels["Stitch extent"].text(),
            "—",
        )


if __name__ == "__main__":
    unittest.main()

import os
import tempfile
import unittest

try:
    from PySide6 import QtCore, QtGui, QtWidgets

    PYSIDE_AVAILABLE = True
except ImportError:
    PYSIDE_AVAILABLE = False


@unittest.skipUnless(PYSIDE_AVAILABLE, "PySide6 is required for UI preview tests")
class TestPreviewAndMetadata(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        cls.app = QtWidgets.QApplication.instance()
        if cls.app is None:
            cls.app = QtWidgets.QApplication([])

    def test_preview_and_metadata_update_on_selection(self) -> None:
        from app.ui import MainWindow

        window = MainWindow()
        with tempfile.TemporaryDirectory() as tmpdir:
            image_path = os.path.join(tmpdir, "sample.png")
            image = QtGui.QImage(24, 18, QtGui.QImage.Format.Format_ARGB32)
            image.fill(QtGui.QColor("#ff0000"))
            self.assertTrue(image.save(image_path))

            window.input_list.add_paths([image_path])
            window.input_list.setCurrentRow(0)
            QtWidgets.QApplication.processEvents()

            pixmap = window.comparison_viewer.side_by_side.before_viewer.pixmap()
            self.assertIsNotNone(pixmap)
            self.assertFalse(pixmap.isNull())

            metadata_values = window.metadata_value_labels
            self.assertEqual(metadata_values["Filename"].text(), "sample.png")
            self.assertEqual(metadata_values["Format"].text(), "PNG")
            self.assertEqual(metadata_values["Dimensions"].text(), "24 x 18 px")
            self.assertIn("B", metadata_values["File size"].text())
            self.assertTrue(metadata_values["Modified"].text())

    def test_non_image_shows_placeholder_metadata(self) -> None:
        from app.ui import MainWindow

        window = MainWindow()
        with tempfile.TemporaryDirectory() as tmpdir:
            text_path = os.path.join(tmpdir, "notes.txt")
            with open(text_path, "w", encoding="utf-8") as handle:
                handle.write("hello")

            window.input_list.add_paths([text_path])
            window.input_list.setCurrentRow(0)
            QtWidgets.QApplication.processEvents()

            self.assertEqual(window.metadata_value_labels["Format"].text(), "Not an image")
            self.assertEqual(window.metadata_value_labels["Dimensions"].text(), "Unknown")
            self.assertIn("notes.txt", window.metadata_summary.text())


if __name__ == "__main__":
    unittest.main()

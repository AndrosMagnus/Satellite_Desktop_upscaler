import os
import unittest


try:
    from PySide6 import QtWidgets

    PYSIDE_AVAILABLE = True
except ImportError:
    PYSIDE_AVAILABLE = False


@unittest.skipUnless(PYSIDE_AVAILABLE, "PySide6 is required for input list tests")
class TestInputListWidget(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        cls.app = QtWidgets.QApplication.instance()
        if cls.app is None:
            cls.app = QtWidgets.QApplication([])

    def test_placeholder_and_add_paths(self) -> None:
        from app.ui import InputListWidget

        widget = InputListWidget()
        self.assertEqual(widget.count(), 1)
        self.assertEqual(widget.item(0).text(), InputListWidget.placeholder_text)

        widget.add_paths(["/tmp/example.tif", "/tmp/example.tif", ""])
        self.assertEqual(widget.count(), 1)
        self.assertEqual(widget.item(0).text(), "/tmp/example.tif")

        widget.add_paths(["/tmp/example2.tif"])
        self.assertEqual(widget.count(), 2)
        self.assertEqual(widget.item(1).text(), "/tmp/example2.tif")

    def test_drag_drop_settings(self) -> None:
        from app.ui import InputListWidget

        widget = InputListWidget()
        self.assertTrue(widget.acceptDrops())
        self.assertEqual(
            widget.dragDropMode(),
            QtWidgets.QAbstractItemView.DragDropMode.DropOnly,
        )


@unittest.skipUnless(PYSIDE_AVAILABLE, "PySide6 is required for input list tests")
class TestImportButtons(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        cls.app = QtWidgets.QApplication.instance()
        if cls.app is None:
            cls.app = QtWidgets.QApplication([])

    def test_import_buttons_exist(self) -> None:
        from app.ui import MainWindow

        window = MainWindow()
        self.assertEqual(window.add_files_button.objectName(), "addFilesButton")
        self.assertEqual(window.add_files_button.text(), "Add Files")
        self.assertEqual(window.add_folder_button.objectName(), "addFolderButton")
        self.assertEqual(window.add_folder_button.text(), "Add Folder")


if __name__ == "__main__":
    unittest.main()

import os
import unittest


try:
    from PySide6 import QtCore, QtWidgets

    PYSIDE_AVAILABLE = True
except ImportError:
    PYSIDE_AVAILABLE = False


@unittest.skipUnless(PYSIDE_AVAILABLE, "PySide6 is required for UI layout tests")
class TestPrimaryLayout(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        cls.app = QtWidgets.QApplication.instance()
        if cls.app is None:
            cls.app = QtWidgets.QApplication([])

    def test_two_pane_layout(self) -> None:
        from app.ui import MainWindow

        window = MainWindow()
        splitter = window.splitter
        self.assertIsInstance(splitter, QtWidgets.QSplitter)
        self.assertEqual(splitter.orientation(), QtCore.Qt.Orientation.Horizontal)
        self.assertIs(window.input_list, splitter.widget(0))
        self.assertEqual(window.input_list.objectName(), "inputList")

    def test_preview_and_metadata_on_right(self) -> None:
        from app.ui import MainWindow

        window = MainWindow()
        self.assertIsInstance(window.preview_label, QtWidgets.QLabel)
        self.assertEqual(window.preview_label.objectName(), "previewLabel")
        self.assertIsInstance(window.metadata_summary, QtWidgets.QLabel)
        self.assertEqual(window.metadata_summary.objectName(), "metadataSummary")

    def test_workflow_stage_list(self) -> None:
        from app.ui import MainWindow

        window = MainWindow()
        self.assertIsInstance(window.workflow_group, QtWidgets.QGroupBox)
        self.assertEqual(window.workflow_group.objectName(), "workflowGroup")
        stage_texts = [label.text() for label in window.workflow_stage_labels]
        self.assertEqual(
            stage_texts,
            [
                "1. Import",
                "2. Review",
                "3. Stitch (Optional)",
                "4. Recommend",
                "5. Run",
                "6. Export",
            ],
        )
        self.assertEqual(len(window.workflow_stage_actions), 6)


if __name__ == "__main__":
    unittest.main()

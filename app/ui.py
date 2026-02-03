from __future__ import annotations

from PySide6 import QtCore, QtGui, QtWidgets


class InputListWidget(QtWidgets.QListWidget):
    placeholder_text = "Drop files or folders here to begin."

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setDragDropMode(QtWidgets.QAbstractItemView.DragDropMode.DropOnly)
        self.setDefaultDropAction(QtCore.Qt.DropAction.CopyAction)
        self.ensure_placeholder()

    def ensure_placeholder(self) -> None:
        if self.count() == 0:
            self.addItem(self.placeholder_text)

    def add_paths(self, paths: list[str]) -> None:
        cleaned = [path for path in paths if path]
        if not cleaned:
            return

        existing = {self.item(index).text() for index in range(self.count())}
        placeholder_only = existing == {self.placeholder_text}
        if placeholder_only:
            self.clear()
            existing = set()

        added_any = False
        for path in cleaned:
            if path in existing:
                continue
            self.addItem(path)
            existing.add(path)
            added_any = True

        if not added_any and self.count() == 0:
            self.ensure_placeholder()

    def _accept_drag(self, event: QtGui.QDragEnterEvent | QtGui.QDragMoveEvent) -> None:
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragEnterEvent(self, event: QtGui.QDragEnterEvent) -> None:
        self._accept_drag(event)

    def dragMoveEvent(self, event: QtGui.QDragMoveEvent) -> None:
        self._accept_drag(event)

    def dropEvent(self, event: QtGui.QDropEvent) -> None:
        mime = event.mimeData()
        if not mime.hasUrls():
            event.ignore()
            return

        paths: list[str] = []
        for url in mime.urls():
            local_path = url.toLocalFile()
            if local_path:
                paths.append(local_path)
        self.add_paths(paths)
        event.acceptProposedAction()


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Satellite Upscale")
        self._build_ui()

    def _build_ui(self) -> None:
        splitter = QtWidgets.QSplitter(QtCore.Qt.Orientation.Horizontal)
        splitter.setObjectName("primarySplitter")

        left_panel = QtWidgets.QWidget()
        left_panel.setObjectName("inputPanel")
        left_layout = QtWidgets.QVBoxLayout(left_panel)
        left_layout.setContentsMargins(12, 12, 12, 12)
        left_layout.setSpacing(8)

        import_row = QtWidgets.QWidget()
        import_row.setObjectName("importRow")
        import_layout = QtWidgets.QHBoxLayout(import_row)
        import_layout.setContentsMargins(0, 0, 0, 0)
        import_layout.setSpacing(8)

        add_files_button = QtWidgets.QPushButton("Add Files")
        add_files_button.setObjectName("addFilesButton")
        add_folder_button = QtWidgets.QPushButton("Add Folder")
        add_folder_button.setObjectName("addFolderButton")
        import_layout.addWidget(add_files_button)
        import_layout.addWidget(add_folder_button)
        import_layout.addStretch(1)

        input_list = InputListWidget()
        input_list.setObjectName("inputList")
        input_list.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.ExtendedSelection)

        left_layout.addWidget(import_row)
        left_layout.addWidget(input_list, 1)

        right_panel = QtWidgets.QWidget()
        right_panel.setObjectName("previewPanel")
        right_layout = QtWidgets.QVBoxLayout(right_panel)
        right_layout.setContentsMargins(16, 16, 16, 16)
        right_layout.setSpacing(12)

        preview_group = QtWidgets.QGroupBox("Preview")
        preview_group.setObjectName("previewGroup")
        preview_layout = QtWidgets.QVBoxLayout(preview_group)
        preview_label = QtWidgets.QLabel("Preview will appear here")
        preview_label.setObjectName("previewLabel")
        preview_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        preview_label.setMinimumHeight(220)
        preview_label.setFrameShape(QtWidgets.QFrame.Shape.StyledPanel)
        preview_layout.addWidget(preview_label)

        metadata_group = QtWidgets.QGroupBox("Metadata")
        metadata_group.setObjectName("metadataGroup")
        metadata_layout = QtWidgets.QVBoxLayout(metadata_group)
        metadata_summary = QtWidgets.QLabel(
            "Detected metadata will appear here (sensor, resolution, CRS, bands, etc.)."
        )
        metadata_summary.setObjectName("metadataSummary")
        metadata_summary.setWordWrap(True)
        metadata_layout.addWidget(metadata_summary)

        workflow_group = QtWidgets.QGroupBox("Workflow")
        workflow_group.setObjectName("workflowGroup")
        workflow_layout = QtWidgets.QVBoxLayout(workflow_group)
        workflow_layout.setSpacing(8)
        workflow_stages = [
            ("Import", "Choose Files"),
            ("Review", "Inspect"),
            ("Stitch (Optional)", "Detect"),
            ("Recommend", "Recommend Model"),
            ("Run", "Start"),
            ("Export", "Save Output"),
        ]
        workflow_stage_labels = []
        workflow_stage_actions = []
        for index, (stage_label_text, action_text) in enumerate(workflow_stages, start=1):
            stage_row = QtWidgets.QWidget()
            stage_row.setObjectName(f"workflowStageRow{index}")
            stage_row_layout = QtWidgets.QHBoxLayout(stage_row)
            stage_row_layout.setContentsMargins(0, 0, 0, 0)

            stage_label = QtWidgets.QLabel(f"{index}. {stage_label_text}")
            stage_label.setObjectName(f"workflowStageLabel{index}")
            stage_action = QtWidgets.QPushButton(action_text)
            stage_action.setObjectName(f"workflowStageAction{index}")

            stage_row_layout.addWidget(stage_label, 1)
            stage_row_layout.addWidget(stage_action)
            workflow_layout.addWidget(stage_row)
            workflow_stage_labels.append(stage_label)
            workflow_stage_actions.append(stage_action)
        workflow_layout.addStretch(1)

        right_layout.addWidget(preview_group)
        right_layout.addWidget(metadata_group)
        right_layout.addWidget(workflow_group)
        right_layout.addStretch(1)

        splitter.addWidget(left_panel)
        splitter.addWidget(right_panel)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 2)

        container = QtWidgets.QWidget()
        container_layout = QtWidgets.QHBoxLayout(container)
        container_layout.setContentsMargins(0, 0, 0, 0)
        container_layout.addWidget(splitter)

        self.setCentralWidget(container)
        self.splitter = splitter
        self.left_panel = left_panel
        self.input_list = input_list
        self.add_files_button = add_files_button
        self.add_folder_button = add_folder_button
        self.preview_label = preview_label
        self.metadata_summary = metadata_summary
        self.workflow_group = workflow_group
        self.workflow_stage_labels = workflow_stage_labels
        self.workflow_stage_actions = workflow_stage_actions

        add_files_button.clicked.connect(self._select_files)
        add_folder_button.clicked.connect(self._select_folder)

    def _select_files(self) -> None:
        files, _ = QtWidgets.QFileDialog.getOpenFileNames(
            self,
            "Select input files",
            "",
            "All Files (*)",
        )
        if files:
            self.input_list.add_paths(files)

    def _select_folder(self) -> None:
        folder = QtWidgets.QFileDialog.getExistingDirectory(
            self,
            "Select input folder",
            "",
            QtWidgets.QFileDialog.Option.ShowDirsOnly,
        )
        if folder:
            self.input_list.add_paths([folder])


def create_app() -> QtWidgets.QApplication:
    app = QtWidgets.QApplication.instance()
    if app is None:
        app = QtWidgets.QApplication([])
    return app


def main() -> int:
    app = create_app()
    window = MainWindow()
    window.resize(1100, 700)
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())

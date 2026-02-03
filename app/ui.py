from __future__ import annotations

import os

from PySide6 import QtCore, QtGui, QtWidgets


def _format_bytes(size_bytes: int) -> str:
    if size_bytes < 0:
        return "Unknown"
    units = ["B", "KB", "MB", "GB", "TB"]
    size = float(size_bytes)
    for unit in units:
        if size < 1024 or unit == units[-1]:
            if unit == "B":
                return f"{int(size)} {unit}"
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} TB"


class PreviewViewer(QtWidgets.QLabel):
    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self._source_pixmap: QtGui.QPixmap | None = None
        self.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self.setMinimumHeight(220)
        self.setFrameShape(QtWidgets.QFrame.Shape.StyledPanel)
        self.set_placeholder("Preview will appear here")

    def set_placeholder(self, text: str) -> None:
        self._source_pixmap = None
        self.setPixmap(QtGui.QPixmap())
        self.setText(text)

    def set_image(self, image: QtGui.QImage) -> None:
        pixmap = QtGui.QPixmap.fromImage(image)
        if pixmap.isNull():
            self.set_placeholder("Preview unavailable for this file.")
            return
        self._source_pixmap = pixmap
        self._update_scaled_pixmap()

    def _update_scaled_pixmap(self) -> None:
        if self._source_pixmap is None:
            return
        scaled = self._source_pixmap.scaled(
            self.size(),
            QtCore.Qt.AspectRatioMode.KeepAspectRatio,
            QtCore.Qt.TransformationMode.SmoothTransformation,
        )
        self.setPixmap(scaled)
        self.setText("")

    def resizeEvent(self, event: QtGui.QResizeEvent) -> None:
        super().resizeEvent(event)
        if self._source_pixmap is not None:
            self._update_scaled_pixmap()


class InputListWidget(QtWidgets.QListWidget):
    placeholder_text = "Drop files or folders here to begin."
    paths_added = QtCore.Signal(list)

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setDragDropMode(QtWidgets.QAbstractItemView.DragDropMode.DropOnly)
        self.setDefaultDropAction(QtCore.Qt.DropAction.CopyAction)
        self.ensure_placeholder()

    def ensure_placeholder(self) -> None:
        if self.count() == 0:
            self.addItem(self.placeholder_text)

    def add_paths(self, paths: list[str]) -> list[str]:
        cleaned = [path for path in paths if path]
        if not cleaned:
            return []

        existing = {self.item(index).text() for index in range(self.count())}
        placeholder_only = existing == {self.placeholder_text}
        if placeholder_only:
            self.clear()
            existing = set()

        added_any = False
        added_paths: list[str] = []
        for path in cleaned:
            if path in existing:
                continue
            self.addItem(path)
            existing.add(path)
            added_any = True
            added_paths.append(path)

        if not added_any and self.count() == 0:
            self.ensure_placeholder()
        if added_paths:
            self.paths_added.emit(added_paths)
        return added_paths

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
        preview_label = PreviewViewer()
        preview_label.setObjectName("previewLabel")
        preview_layout.addWidget(preview_label)

        metadata_group = QtWidgets.QGroupBox("Metadata")
        metadata_group.setObjectName("metadataGroup")
        metadata_layout = QtWidgets.QVBoxLayout(metadata_group)
        metadata_layout.setSpacing(6)
        metadata_summary = QtWidgets.QLabel(
            "Select a file to see metadata."
        )
        metadata_summary.setObjectName("metadataSummary")
        metadata_summary.setWordWrap(True)
        metadata_layout.addWidget(metadata_summary)

        metadata_form = QtWidgets.QWidget()
        metadata_form_layout = QtWidgets.QFormLayout(metadata_form)
        metadata_form_layout.setContentsMargins(0, 0, 0, 0)
        metadata_form_layout.setSpacing(8)
        metadata_form_layout.setLabelAlignment(QtCore.Qt.AlignmentFlag.AlignLeft)
        metadata_fields = [
            "Filename",
            "Path",
            "Format",
            "Dimensions",
            "File size",
            "Modified",
        ]
        metadata_value_labels: dict[str, QtWidgets.QLabel] = {}
        for field in metadata_fields:
            field_label = QtWidgets.QLabel(field)
            value_label = QtWidgets.QLabel("—")
            value_label.setTextInteractionFlags(QtCore.Qt.TextInteractionFlag.TextSelectableByMouse)
            value_label.setObjectName(f"metadataValue{field.replace(' ', '')}")
            metadata_form_layout.addRow(field_label, value_label)
            metadata_value_labels[field] = value_label
        metadata_layout.addWidget(metadata_form)

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
        self.metadata_value_labels = metadata_value_labels
        self.workflow_group = workflow_group
        self.workflow_stage_labels = workflow_stage_labels
        self.workflow_stage_actions = workflow_stage_actions

        add_files_button.clicked.connect(self._select_files)
        add_folder_button.clicked.connect(self._select_folder)
        input_list.itemSelectionChanged.connect(self._handle_selection_change)
        input_list.paths_added.connect(self._select_latest_added)

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

    def _select_latest_added(self, paths: list[str]) -> None:
        if not paths:
            return
        latest_path = paths[-1]
        for index in range(self.input_list.count() - 1, -1, -1):
            if self.input_list.item(index).text() == latest_path:
                self.input_list.setCurrentRow(index)
                self.input_list.scrollToItem(self.input_list.item(index))
                break

    def _handle_selection_change(self) -> None:
        items = self.input_list.selectedItems()
        if len(items) != 1:
            message = "Select a single file to preview."
            if not items:
                message = "Select a file to see metadata."
            elif len(items) > 1:
                message = "Multiple items selected."
            self.preview_label.set_placeholder("Preview will appear here")
            self.metadata_summary.setText(message)
            self._set_metadata_placeholders()
            return

        selected_path = items[0].text()
        if selected_path == self.input_list.placeholder_text:
            self.preview_label.set_placeholder("Preview will appear here")
            self.metadata_summary.setText("Select a file to see metadata.")
            self._set_metadata_placeholders()
            return

        self._load_preview_and_metadata(selected_path)

    def _load_preview_and_metadata(self, path: str) -> None:
        if not os.path.exists(path):
            self.preview_label.set_placeholder("Preview unavailable for this file.")
            self.metadata_summary.setText("File not found.")
            self._set_metadata_placeholders()
            return

        image = self._read_image(path)
        if image is None:
            self.preview_label.set_placeholder("No preview available for this file.")
        else:
            self.preview_label.set_image(image)
        metadata = self._build_metadata(path)
        filename = metadata.get("Filename", os.path.basename(path))
        self.metadata_summary.setText(f"Metadata for {filename}")
        self._set_metadata(metadata)

    def _read_image(self, path: str) -> QtGui.QImage | None:
        reader = QtGui.QImageReader(path)
        if not reader.canRead():
            return None
        image = reader.read()
        if image.isNull():
            return None
        return image

    def _build_metadata(self, path: str) -> dict[str, str]:
        info = QtCore.QFileInfo(path)
        metadata: dict[str, str] = {
            "Filename": info.fileName() or "Unknown",
            "Path": info.absoluteFilePath() or path,
            "File size": _format_bytes(info.size()),
            "Modified": info.lastModified().toString(QtCore.Qt.DateFormat.ISODate) or "Unknown",
        }
        reader = QtGui.QImageReader(path)
        if reader.canRead():
            fmt = reader.format()
            fmt_text = fmt.data().decode("ascii", errors="ignore").upper() if fmt else "Unknown"
            size = reader.size()
            if size.isValid():
                dimensions = f"{size.width()} x {size.height()} px"
            else:
                dimensions = "Unknown"
        else:
            fmt_text = "Not an image"
            dimensions = "Unknown"
        metadata["Format"] = fmt_text or "Unknown"
        metadata["Dimensions"] = dimensions
        return metadata

    def _set_metadata_placeholders(self) -> None:
        for label in self.metadata_value_labels.values():
            label.setText("—")

    def _set_metadata(self, metadata: dict[str, str]) -> None:
        for field, label in self.metadata_value_labels.items():
            label.setText(metadata.get(field, "—"))


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

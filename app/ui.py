from __future__ import annotations

import json
import os
import re

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


class SideBySideComparison(QtWidgets.QWidget):
    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        before_column = QtWidgets.QWidget()
        before_layout = QtWidgets.QVBoxLayout(before_column)
        before_layout.setContentsMargins(0, 0, 0, 0)
        before_layout.setSpacing(6)
        before_title = QtWidgets.QLabel("Before")
        before_title.setObjectName("beforeTitle")
        before_viewer = PreviewViewer()
        before_viewer.setObjectName("beforePreview")
        before_layout.addWidget(before_title)
        before_layout.addWidget(before_viewer, 1)

        after_column = QtWidgets.QWidget()
        after_layout = QtWidgets.QVBoxLayout(after_column)
        after_layout.setContentsMargins(0, 0, 0, 0)
        after_layout.setSpacing(6)
        after_title = QtWidgets.QLabel("After")
        after_title.setObjectName("afterTitle")
        after_viewer = PreviewViewer()
        after_viewer.setObjectName("afterPreview")
        after_layout.addWidget(after_title)
        after_layout.addWidget(after_viewer, 1)

        layout.addWidget(before_column, 1)
        layout.addWidget(after_column, 1)

        self.before_viewer = before_viewer
        self.after_viewer = after_viewer

    def set_before_image(self, image: QtGui.QImage | None) -> None:
        if image is None:
            return
        self.before_viewer.set_image(image)

    def set_after_image(self, image: QtGui.QImage | None) -> None:
        if image is None:
            return
        self.after_viewer.set_image(image)

    def set_before_placeholder(self, text: str) -> None:
        self.before_viewer.set_placeholder(text)

    def set_after_placeholder(self, text: str) -> None:
        self.after_viewer.set_placeholder(text)


class SwipeComparisonView(QtWidgets.QFrame):
    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self._before_pixmap: QtGui.QPixmap | None = None
        self._after_pixmap: QtGui.QPixmap | None = None
        self._placeholder_text = "Preview will appear here"
        self._slider_ratio = 0.5
        self.setFrameShape(QtWidgets.QFrame.Shape.StyledPanel)
        self.setMinimumHeight(220)

    def set_before_image(self, image: QtGui.QImage | None) -> None:
        self._before_pixmap = (
            QtGui.QPixmap.fromImage(image) if image is not None else None
        )
        self.update()

    def set_after_image(self, image: QtGui.QImage | None) -> None:
        self._after_pixmap = (
            QtGui.QPixmap.fromImage(image) if image is not None else None
        )
        self.update()

    def set_placeholder(self, text: str) -> None:
        self._placeholder_text = text
        self.update()

    def set_slider_ratio(self, ratio: float) -> None:
        self._slider_ratio = max(0.0, min(1.0, ratio))
        self.update()

    def has_before_image(self) -> bool:
        return self._before_pixmap is not None and not self._before_pixmap.isNull()

    def _target_rect(self, pixmap: QtGui.QPixmap) -> QtCore.QRect:
        if pixmap.isNull():
            return self.rect()
        scaled = pixmap.scaled(
            self.size(),
            QtCore.Qt.AspectRatioMode.KeepAspectRatio,
            QtCore.Qt.TransformationMode.SmoothTransformation,
        )
        x = (self.width() - scaled.width()) // 2
        y = (self.height() - scaled.height()) // 2
        return QtCore.QRect(x, y, scaled.width(), scaled.height())

    def paintEvent(self, event: QtGui.QPaintEvent) -> None:
        super().paintEvent(event)
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.RenderHint.SmoothPixmapTransform)
        painter.fillRect(self.rect(), self.palette().color(QtGui.QPalette.ColorRole.Base))

        if self._before_pixmap is None or self._before_pixmap.isNull():
            painter.drawText(
                self.rect(),
                QtCore.Qt.AlignmentFlag.AlignCenter,
                self._placeholder_text,
            )
            return

        target_rect = self._target_rect(self._before_pixmap)
        painter.drawPixmap(target_rect, self._before_pixmap)

        if self._after_pixmap is None or self._after_pixmap.isNull():
            return

        clip_width = int(target_rect.width() * self._slider_ratio)
        clip_rect = QtCore.QRect(
            target_rect.left(), target_rect.top(), clip_width, target_rect.height()
        )
        painter.save()
        painter.setClipRect(clip_rect)
        painter.drawPixmap(target_rect, self._after_pixmap)
        painter.restore()

        divider_x = target_rect.left() + clip_width
        divider_pen = QtGui.QPen(self.palette().color(QtGui.QPalette.ColorRole.Highlight))
        divider_pen.setWidth(2)
        painter.setPen(divider_pen)
        painter.drawLine(divider_x, target_rect.top(), divider_x, target_rect.bottom())


class SwipeComparisonWidget(QtWidgets.QWidget):
    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        view = SwipeComparisonView()
        view.setObjectName("swipePreview")
        slider_row = QtWidgets.QWidget()
        slider_layout = QtWidgets.QHBoxLayout(slider_row)
        slider_layout.setContentsMargins(0, 0, 0, 0)
        slider_label = QtWidgets.QLabel("Swipe")
        slider_label.setObjectName("swipeLabel")
        slider = QtWidgets.QSlider(QtCore.Qt.Orientation.Horizontal)
        slider.setObjectName("swipeSlider")
        slider.setRange(0, 100)
        slider.setValue(50)
        slider_layout.addWidget(slider_label)
        slider_layout.addWidget(slider, 1)

        slider.valueChanged.connect(lambda value: view.set_slider_ratio(value / 100.0))

        layout.addWidget(view, 1)
        layout.addWidget(slider_row)

        self.view = view
        self.slider = slider

    def set_before_image(self, image: QtGui.QImage | None) -> None:
        self.view.set_before_image(image)

    def set_after_image(self, image: QtGui.QImage | None) -> None:
        self.view.set_after_image(image)

    def set_placeholder(self, text: str) -> None:
        self.view.set_placeholder(text)


class ComparisonViewer(QtWidgets.QWidget):
    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        tabs = QtWidgets.QTabWidget()
        tabs.setObjectName("comparisonTabs")
        side_by_side = SideBySideComparison()
        side_by_side.setObjectName("sideBySideComparison")
        swipe = SwipeComparisonWidget()
        swipe.setObjectName("swipeComparison")
        tabs.addTab(side_by_side, "Side-by-side")
        tabs.addTab(swipe, "Swipe")

        layout.addWidget(tabs)

        self.tabs = tabs
        self.side_by_side = side_by_side
        self.swipe = swipe

        self.set_before_placeholder("Preview will appear here")
        self.set_after_placeholder("Upscaled preview will appear here")

    def set_before_image(self, image: QtGui.QImage | None) -> None:
        if image is None:
            self.set_before_placeholder("Preview will appear here")
            return
        self.side_by_side.set_before_image(image)
        self.swipe.set_before_image(image)

    def set_after_image(self, image: QtGui.QImage | None) -> None:
        if image is None:
            self.set_after_placeholder("Upscaled preview will appear here")
            return
        self.side_by_side.set_after_image(image)
        self.swipe.set_after_image(image)

    def set_before_placeholder(self, text: str) -> None:
        self.side_by_side.set_before_placeholder(text)
        self.swipe.set_placeholder(text)

    def set_after_placeholder(self, text: str) -> None:
        self.side_by_side.set_after_placeholder(text)
        if self.swipe.view.has_before_image():
            self.swipe.view.set_after_image(None)
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


class ModelManagerPanel(QtWidgets.QGroupBox):
    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__("Model Manager", parent)
        self.setObjectName("modelManagerPanel")
        layout = QtWidgets.QVBoxLayout(self)
        layout.setSpacing(8)

        model_table = QtWidgets.QTableWidget(0, 3)
        model_table.setObjectName("modelTable")
        model_table.setHorizontalHeaderLabels(["Model", "Version", "Status"])
        model_table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        model_table.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.SingleSelection)
        model_table.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        model_table.horizontalHeader().setStretchLastSection(True)
        model_table.verticalHeader().setVisible(False)

        selection_label = QtWidgets.QLabel("Select a model to manage.")
        selection_label.setObjectName("modelSelectionLabel")
        status_label = QtWidgets.QLabel("Status: —")
        status_label.setObjectName("modelStatusLabel")

        action_row = QtWidgets.QWidget()
        action_row_layout = QtWidgets.QHBoxLayout(action_row)
        action_row_layout.setContentsMargins(0, 0, 0, 0)
        action_row_layout.setSpacing(8)
        version_label = QtWidgets.QLabel("Version")
        version_label.setObjectName("modelVersionLabel")
        version_combo = QtWidgets.QComboBox()
        version_combo.setObjectName("modelVersionCombo")
        install_button = QtWidgets.QPushButton("Install")
        install_button.setObjectName("installModelButton")
        uninstall_button = QtWidgets.QPushButton("Uninstall")
        uninstall_button.setObjectName("uninstallModelButton")

        action_row_layout.addWidget(version_label)
        action_row_layout.addWidget(version_combo, 1)
        action_row_layout.addWidget(install_button)
        action_row_layout.addWidget(uninstall_button)

        layout.addWidget(model_table)
        layout.addWidget(selection_label)
        layout.addWidget(status_label)
        layout.addWidget(action_row)

        self.model_table = model_table
        self.selection_label = selection_label
        self.status_label = status_label
        self.version_combo = version_combo
        self.install_button = install_button
        self.uninstall_button = uninstall_button
        self.models = self._load_model_registry()
        self._populate_table()
        self._update_action_state()

        model_table.itemSelectionChanged.connect(self._handle_selection_change)
        version_combo.currentTextChanged.connect(self._apply_selected_version)
        install_button.clicked.connect(self._install_selected_model)
        uninstall_button.clicked.connect(self._uninstall_selected_model)

    def _load_model_registry(self) -> list[dict[str, object]]:
        repo_root = os.path.dirname(os.path.dirname(__file__))
        registry_path = os.path.join(repo_root, "models", "registry.json")
        try:
            with open(registry_path, "r", encoding="utf-8") as handle:
                data = json.load(handle)
        except (OSError, json.JSONDecodeError):
            return []
        if not isinstance(data, list):
            return []

        models: list[dict[str, object]] = []
        for entry in data:
            if not isinstance(entry, dict):
                continue
            name = str(entry.get("name", "Unknown"))
            weights_url = str(entry.get("weights_url", ""))
            bundled = bool(entry.get("bundled"))
            version = self._extract_version(weights_url)
            versions = ["Latest"]
            if version and version not in versions:
                versions.insert(0, version)
            models.append(
                {
                    "name": name,
                    "bundled": bundled,
                    "installed": bundled,
                    "version": versions[0],
                    "versions": versions,
                }
            )
        return models

    def _extract_version(self, weights_url: str) -> str | None:
        if not weights_url:
            return None
        match = re.search(r"/download/(v[^/]+)/", weights_url)
        if match:
            return match.group(1)
        match = re.search(r"\bv\d+\.\d+(?:\.\d+)?\b", weights_url)
        if match:
            return match.group(0)
        return None

    def _populate_table(self) -> None:
        self.model_table.setRowCount(len(self.models))
        for row, model in enumerate(self.models):
            name_item = QtWidgets.QTableWidgetItem(str(model["name"]))
            version_item = QtWidgets.QTableWidgetItem(str(model["version"]))
            status_item = QtWidgets.QTableWidgetItem(self._status_text(model))
            self.model_table.setItem(row, 0, name_item)
            self.model_table.setItem(row, 1, version_item)
            self.model_table.setItem(row, 2, status_item)

    def _status_text(self, model: dict[str, object]) -> str:
        if model.get("bundled"):
            return "Bundled"
        return "Installed" if model.get("installed") else "Not installed"

    def _selected_row(self) -> int | None:
        selected_rows = self.model_table.selectionModel().selectedRows()
        if not selected_rows:
            return None
        return selected_rows[0].row()

    def _selected_model(self) -> dict[str, object] | None:
        row = self._selected_row()
        if row is None or row >= len(self.models):
            return None
        return self.models[row]

    def _handle_selection_change(self) -> None:
        model = self._selected_model()
        if model is None:
            self.selection_label.setText("Select a model to manage.")
            self.status_label.setText("Status: —")
            self.version_combo.clear()
            self._update_action_state()
            return

        self.selection_label.setText(f"Selected: {model['name']}")
        self.status_label.setText(f"Status: {self._status_text(model)}")
        self.version_combo.blockSignals(True)
        self.version_combo.clear()
        self.version_combo.addItems([str(v) for v in model.get("versions", [])])
        self.version_combo.setCurrentText(str(model.get("version", "Latest")))
        self.version_combo.blockSignals(False)
        self._update_action_state()

    def _apply_selected_version(self, version: str) -> None:
        row = self._selected_row()
        if row is None:
            return
        model = self.models[row]
        model["version"] = version
        version_item = self.model_table.item(row, 1)
        if version_item is not None:
            version_item.setText(version)

    def _install_selected_model(self) -> None:
        model = self._selected_model()
        if model is None or model.get("bundled"):
            return
        model["installed"] = True
        self._refresh_selected_row()

    def _uninstall_selected_model(self) -> None:
        model = self._selected_model()
        if model is None or model.get("bundled"):
            return
        model["installed"] = False
        self._refresh_selected_row()

    def _refresh_selected_row(self) -> None:
        row = self._selected_row()
        if row is None:
            return
        model = self.models[row]
        status_item = self.model_table.item(row, 2)
        if status_item is not None:
            status_item.setText(self._status_text(model))
        self.status_label.setText(f"Status: {self._status_text(model)}")
        self._update_action_state()

    def _update_action_state(self) -> None:
        model = self._selected_model()
        if model is None:
            self.install_button.setEnabled(False)
            self.uninstall_button.setEnabled(False)
            self.version_combo.setEnabled(False)
            return
        self.version_combo.setEnabled(True)
        if model.get("bundled"):
            self.install_button.setEnabled(False)
            self.uninstall_button.setEnabled(False)
            return
        installed = bool(model.get("installed"))
        self.install_button.setEnabled(not installed)
        self.uninstall_button.setEnabled(installed)


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
        comparison_viewer = ComparisonViewer()
        comparison_viewer.setObjectName("comparisonViewer")
        preview_layout.addWidget(comparison_viewer)

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
        model_manager_panel = ModelManagerPanel()
        right_layout.addWidget(model_manager_panel)
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
        self.comparison_viewer = comparison_viewer
        self.metadata_summary = metadata_summary
        self.metadata_value_labels = metadata_value_labels
        self.workflow_group = workflow_group
        self.workflow_stage_labels = workflow_stage_labels
        self.workflow_stage_actions = workflow_stage_actions
        self.model_manager_panel = model_manager_panel

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
            self.comparison_viewer.set_before_placeholder("Preview will appear here")
            self.comparison_viewer.set_after_placeholder("Upscaled preview will appear here")
            self.metadata_summary.setText(message)
            self._set_metadata_placeholders()
            return

        selected_path = items[0].text()
        if selected_path == self.input_list.placeholder_text:
            self.comparison_viewer.set_before_placeholder("Preview will appear here")
            self.comparison_viewer.set_after_placeholder("Upscaled preview will appear here")
            self.metadata_summary.setText("Select a file to see metadata.")
            self._set_metadata_placeholders()
            return

        self._load_preview_and_metadata(selected_path)

    def _load_preview_and_metadata(self, path: str) -> None:
        if not os.path.exists(path):
            self.comparison_viewer.set_before_placeholder("Preview unavailable for this file.")
            self.comparison_viewer.set_after_placeholder("Upscaled preview will appear here")
            self.metadata_summary.setText("File not found.")
            self._set_metadata_placeholders()
            return

        image = self._read_image(path)
        if image is None:
            self.comparison_viewer.set_before_placeholder("No preview available for this file.")
        else:
            self.comparison_viewer.set_before_image(image)
        self.comparison_viewer.set_after_placeholder("Upscaled preview will appear here")
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

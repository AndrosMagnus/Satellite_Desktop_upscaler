from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from collections.abc import Callable

from PySide6 import QtCore, QtGui, QtWidgets

from app.band_handling import BandHandling, ExportSettings
from app.error_handling import UserFacingError, as_user_facing_error
from app.mosaic_detection import preview_stitch_bounds, suggest_mosaic
from app.metadata import extract_image_header_info
from app.model_installation import ModelInstaller, resolve_model_cache_dir
from app.output_metadata import metadata_loss_warning
from app.run_settings import (
    RunSettings,
    parse_compute,
    parse_precision,
    parse_scale,
    parse_tiling,
)
from app.session import SessionState, SessionStore


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


def _extract_model_version(weights_url: str) -> str | None:
    if not weights_url:
        return None
    match = re.search(r"/download/(v[^/]+)/", weights_url)
    if match:
        return match.group(1)
    match = re.search(r"\bv\d+\.\d+(?:\.\d+)?\b", weights_url)
    if match:
        return match.group(0)
    return None


def _detect_gpu_info() -> str:
    if shutil.which("nvidia-smi") is None:
        return "Not detected"
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=name", "--format=csv,noheader"],
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError:
        return "Not detected"
    lines = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    if not lines:
        return "Not detected"
    return ", ".join(lines)


def _detect_cuda_version() -> str:
    env_version = os.environ.get("CUDA_VERSION")
    if env_version:
        return env_version
    if shutil.which("nvidia-smi") is None:
        return "Not detected"
    try:
        result = subprocess.run(
            ["nvidia-smi"],
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError:
        return "Not detected"
    match = re.search(r"CUDA Version:\s*([0-9.]+)", result.stdout)
    if match:
        return match.group(1)
    return "Not detected"


def _load_model_registry() -> list[dict[str, object]]:
    repo_root = os.path.dirname(os.path.dirname(__file__))
    registry_path = os.path.join(repo_root, "models", "registry.json")
    try:
        with open(registry_path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, json.JSONDecodeError):
        return []
    if not isinstance(data, list):
        return []
    entries: list[dict[str, object]] = []
    for entry in data:
        if isinstance(entry, dict):
            entries.append(entry)
    return entries


def _format_model_versions(models: list[dict[str, object]]) -> str:
    if not models:
        return "No models available."
    lines = []
    for entry in models:
        name = str(entry.get("name", "Unknown"))
        weights_url = str(entry.get("weights_url", ""))
        version = _extract_model_version(weights_url) or "Unknown"
        lines.append(f"{name} — {version}")
    return "\n".join(lines)


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

        self.before_title = before_title
        self.after_title = after_title
        self.before_viewer = before_viewer
        self.after_viewer = after_viewer

    def set_titles(self, before_text: str, after_text: str) -> None:
        self.before_title.setText(before_text)
        self.after_title.setText(after_text)

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

    def set_titles(self, before_text: str, after_text: str) -> None:
        self.side_by_side.set_titles(before_text, after_text)

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
        self.swipe.set_before_image(None)
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


class ErrorDialog(QtWidgets.QDialog):
    def __init__(
        self,
        error: UserFacingError,
        retry_action: Callable[[], None] | None = None,
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(error.title)
        self.setObjectName("errorDialog")
        self._retry_action = retry_action

        layout = QtWidgets.QVBoxLayout(self)
        layout.setSpacing(10)

        title = QtWidgets.QLabel(error.title)
        title.setObjectName("errorTitleLabel")
        title.setStyleSheet("font-weight: 600;")

        summary = QtWidgets.QLabel(error.summary)
        summary.setObjectName("errorSummaryLabel")
        summary.setWordWrap(True)

        layout.addWidget(title)
        layout.addWidget(summary)

        suggestion_container = QtWidgets.QWidget()
        suggestion_layout = QtWidgets.QVBoxLayout(suggestion_container)
        suggestion_layout.setContentsMargins(0, 0, 0, 0)
        suggestion_layout.setSpacing(4)

        suggestion_header = QtWidgets.QLabel("Suggested fixes")
        suggestion_header.setObjectName("errorSuggestedHeader")
        suggestion_layout.addWidget(suggestion_header)

        self.suggestion_labels: list[QtWidgets.QLabel] = []
        if error.suggested_fixes:
            for fix in error.suggested_fixes:
                label = QtWidgets.QLabel(f"• {fix}")
                label.setObjectName("errorSuggestedFix")
                label.setWordWrap(True)
                suggestion_layout.addWidget(label)
                self.suggestion_labels.append(label)
        else:
            label = QtWidgets.QLabel("No suggestions available.")
            label.setObjectName("errorSuggestedFix")
            suggestion_layout.addWidget(label)
            self.suggestion_labels.append(label)

        layout.addWidget(suggestion_container)

        code_label = QtWidgets.QLabel(f"Error code: {error.error_code}")
        code_label.setObjectName("errorCodeLabel")
        layout.addWidget(code_label)

        button_box = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.StandardButton.Close)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

        self.retry_button: QtWidgets.QPushButton | None = None
        if retry_action is not None and error.can_retry:
            self.retry_button = QtWidgets.QPushButton("Retry")
            self.retry_button.setObjectName("errorRetryButton")
            self.retry_button.clicked.connect(self._handle_retry)
            button_box.addButton(self.retry_button, QtWidgets.QDialogButtonBox.ButtonRole.AcceptRole)

    def _handle_retry(self) -> None:
        if self._retry_action is not None:
            self._retry_action()
        self.accept()


class ModelManagerPanel(QtWidgets.QGroupBox):
    _STATUS_UPDATE_DELAY_MS = 600

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
        self._installer = ModelInstaller()
        self._install_actions_enabled = (
            os.environ.get("SATELLITE_UPSCALE_ENABLE_INSTALL") == "1"
            and os.environ.get("SATELLITE_UPSCALE_DISABLE_INSTALL") != "1"
        )
        self._model_cache_dir = resolve_model_cache_dir()
        self.models = self._load_model_registry()
        self._populate_table()
        self._update_action_state()

        model_table.itemSelectionChanged.connect(self._handle_selection_change)
        version_combo.currentTextChanged.connect(self._apply_selected_version)
        install_button.clicked.connect(self._install_selected_model)
        uninstall_button.clicked.connect(self._uninstall_selected_model)

    def _load_model_registry(self) -> list[dict[str, object]]:
        models: list[dict[str, object]] = []
        for entry in _load_model_registry():
            name = str(entry.get("name", "Unknown"))
            weights_url = str(entry.get("weights_url", ""))
            bundled = bool(entry.get("bundled"))
            license_acceptance_required = bool(entry.get("license_acceptance_required"))
            checksum = str(entry.get("checksum", ""))
            version = _extract_model_version(weights_url)
            versions = ["Latest"]
            if version and version not in versions:
                versions.insert(0, version)
            resolved_version = versions[0]
            installed = bundled
            if not bundled and self._install_actions_enabled:
                installed = self._installer.is_installed(name, resolved_version)
            models.append(
                {
                    "name": name,
                    "bundled": bundled,
                    "installed": installed,
                    "updating": False,
                    "version": resolved_version,
                    "versions": versions,
                    "weights_url": weights_url,
                    "checksum": checksum,
                    "license_acceptance_required": license_acceptance_required,
                }
            )
        return models

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
        if model.get("updating"):
            return "Updating"
        return "Installed" if model.get("installed") else "Available"

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
        if not model.get("bundled") and self._install_actions_enabled:
            model["installed"] = self._installer.is_installed(
                str(model.get("name", "")), version
            )
        version_item = self.model_table.item(row, 1)
        if version_item is not None:
            version_item.setText(version)
        self._refresh_row_for_model(model)

    def _install_selected_model(self) -> None:
        model = self._selected_model()
        if model is None or model.get("bundled") or model.get("updating"):
            return
        if model.get("installed"):
            return
        if model.get("license_acceptance_required"):
            self._show_install_error(
                UserFacingError(
                    title="License acceptance required",
                    summary="This model requires explicit license acceptance before install.",
                    suggested_fixes=(
                        "Review the license terms and accept them before installing.",
                    ),
                    error_code="MODEL-004",
                    can_retry=False,
                )
            )
            return
        self._begin_status_update(model, target_installed=True)

    def _uninstall_selected_model(self) -> None:
        model = self._selected_model()
        if model is None or model.get("bundled") or model.get("updating"):
            return
        if not model.get("installed"):
            return
        self._begin_status_update(model, target_installed=False)

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

    def _refresh_row_for_model(self, model: dict[str, object]) -> None:
        try:
            row = self.models.index(model)
        except ValueError:
            return
        status_item = self.model_table.item(row, 2)
        if status_item is not None:
            status_item.setText(self._status_text(model))
        if row == self._selected_row():
            self.status_label.setText(f"Status: {self._status_text(model)}")
            self._update_action_state()

    def _begin_status_update(
        self, model: dict[str, object], target_installed: bool
    ) -> None:
        model["updating"] = True
        self._refresh_row_for_model(model)
        if not self._install_actions_enabled:
            QtCore.QTimer.singleShot(
                self._STATUS_UPDATE_DELAY_MS,
                lambda: self._complete_status_update(model, target_installed),
            )
            return
        QtCore.QTimer.singleShot(
            self._STATUS_UPDATE_DELAY_MS,
            lambda: self._perform_update(model, target_installed),
        )

    def _perform_update(
        self, model: dict[str, object], target_installed: bool
    ) -> None:
        final_installed = bool(model.get("installed"))
        error: Exception | None = None
        if target_installed:
            try:
                self._installer.install(
                    str(model.get("name", "")),
                    str(model.get("version", "Latest")),
                    str(model.get("weights_url", "")),
                    checksum=str(model.get("checksum", "")),
                )
                final_installed = True
            except Exception as exc:  # noqa: BLE001
                final_installed = False
                error = exc
        else:
            try:
                self._installer.uninstall(
                    str(model.get("name", "")),
                    str(model.get("version", "Latest")),
                )
                final_installed = False
            except Exception as exc:  # noqa: BLE001
                final_installed = True
                error = exc
        self._complete_status_update(model, final_installed)
        if error is not None:
            self._show_install_error(error)

    def _complete_status_update(
        self, model: dict[str, object], target_installed: bool
    ) -> None:
        model["installed"] = target_installed
        model["updating"] = False
        self._refresh_row_for_model(model)

    def _show_install_error(self, exc: Exception) -> None:
        error = as_user_facing_error(exc)
        dialog = ErrorDialog(error, parent=self)
        dialog.exec()

    def _update_action_state(self) -> None:
        model = self._selected_model()
        if model is None:
            self.install_button.setEnabled(False)
            self.uninstall_button.setEnabled(False)
            self.version_combo.setEnabled(False)
            return
        if model.get("updating"):
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


class CollapsiblePanel(QtWidgets.QWidget):
    def __init__(self, title: str, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.toggle_button = QtWidgets.QToolButton()
        self.toggle_button.setText(title)
        self.toggle_button.setCheckable(True)
        self.toggle_button.setChecked(False)
        self.toggle_button.setToolButtonStyle(
            QtCore.Qt.ToolButtonStyle.ToolButtonTextBesideIcon
        )
        self.toggle_button.setArrowType(QtCore.Qt.ArrowType.RightArrow)

        self.content_area = QtWidgets.QWidget()
        self.content_area.setVisible(False)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        layout.addWidget(self.toggle_button)
        layout.addWidget(self.content_area)

        self.toggle_button.toggled.connect(self._toggle_content)

    def _toggle_content(self, expanded: bool) -> None:
        self.content_area.setVisible(expanded)
        self.toggle_button.setArrowType(
            QtCore.Qt.ArrowType.DownArrow if expanded else QtCore.Qt.ArrowType.RightArrow
        )


class AdvancedOptionsPanel(CollapsiblePanel):
    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__("Advanced Options", parent)
        self.setObjectName("advancedOptionsPanel")
        self.toggle_button.setObjectName("advancedOptionsToggle")
        self.content_area.setObjectName("advancedOptionsContent")

        content_layout = QtWidgets.QFormLayout(self.content_area)
        content_layout.setContentsMargins(12, 0, 12, 0)
        content_layout.setSpacing(8)

        safe_mode_check = QtWidgets.QCheckBox(
            "Safe mode (CPU-only, conservative defaults)"
        )
        safe_mode_check.setObjectName("safeModeCheck")

        scale_combo = QtWidgets.QComboBox()
        scale_combo.setObjectName("advancedScaleCombo")
        scale_combo.addItems(["2x", "4x", "8x"])

        tiling_combo = QtWidgets.QComboBox()
        tiling_combo.setObjectName("advancedTilingCombo")
        tiling_combo.addItems(["Auto", "512 px", "1024 px"])

        precision_combo = QtWidgets.QComboBox()
        precision_combo.setObjectName("advancedPrecisionCombo")
        precision_combo.addItems(["Auto", "FP16", "FP32"])

        compute_combo = QtWidgets.QComboBox()
        compute_combo.setObjectName("advancedComputeCombo")
        compute_combo.addItems(["Auto", "GPU", "CPU"])

        seam_blend_check = QtWidgets.QCheckBox("Enable seam blending")
        seam_blend_check.setObjectName("advancedSeamBlendCheck")

        completion_notification_check = QtWidgets.QCheckBox(
            "Desktop notification on completion"
        )
        completion_notification_check.setObjectName("advancedCompletionNotifyCheck")

        content_layout.addRow("", safe_mode_check)
        content_layout.addRow("Scale factor", scale_combo)
        content_layout.addRow("Tiling strategy", tiling_combo)
        content_layout.addRow("Precision", precision_combo)
        content_layout.addRow("Compute", compute_combo)
        content_layout.addRow("", seam_blend_check)
        content_layout.addRow("", completion_notification_check)

        self.scale_combo = scale_combo
        self.tiling_combo = tiling_combo
        self.precision_combo = precision_combo
        self.compute_combo = compute_combo
        self.seam_blend_check = seam_blend_check
        self.completion_notification_check = completion_notification_check
        self.safe_mode_check = safe_mode_check
        self._safe_mode_previous: dict[str, object] | None = None

        safe_mode_check.toggled.connect(self._apply_safe_mode_state)

    def _apply_safe_mode_state(self, enabled: bool) -> None:
        advanced_controls = [
            self.scale_combo,
            self.tiling_combo,
            self.precision_combo,
            self.compute_combo,
            self.seam_blend_check,
        ]

        if enabled:
            self._safe_mode_previous = {
                "scale": self.scale_combo.currentText(),
                "tiling": self.tiling_combo.currentText(),
                "precision": self.precision_combo.currentText(),
                "compute": self.compute_combo.currentText(),
                "seam_blend": self.seam_blend_check.isChecked(),
            }
            if self.scale_combo.findText("2x") >= 0:
                self.scale_combo.setCurrentText("2x")
            if self.tiling_combo.findText("512 px") >= 0:
                self.tiling_combo.setCurrentText("512 px")
            if self.precision_combo.findText("FP32") >= 0:
                self.precision_combo.setCurrentText("FP32")
            if self.compute_combo.findText("CPU") >= 0:
                self.compute_combo.setCurrentText("CPU")
            self.seam_blend_check.setChecked(False)
            for control in advanced_controls:
                control.setEnabled(False)
            return

        if self._safe_mode_previous:
            self.scale_combo.setCurrentText(str(self._safe_mode_previous["scale"]))
            self.tiling_combo.setCurrentText(str(self._safe_mode_previous["tiling"]))
            self.precision_combo.setCurrentText(str(self._safe_mode_previous["precision"]))
            self.compute_combo.setCurrentText(str(self._safe_mode_previous["compute"]))
            self.seam_blend_check.setChecked(
                bool(self._safe_mode_previous["seam_blend"])
            )
            self._safe_mode_previous = None
        for control in advanced_controls:
            control.setEnabled(True)


class ModelComparisonPanel(QtWidgets.QGroupBox):
    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__("Model Comparison", parent)
        self.setObjectName("modelComparisonPanel")
        layout = QtWidgets.QVBoxLayout(self)
        layout.setSpacing(6)

        mode_row = QtWidgets.QWidget()
        mode_row_layout = QtWidgets.QHBoxLayout(mode_row)
        mode_row_layout.setContentsMargins(0, 0, 0, 0)
        mode_label = QtWidgets.QLabel("Mode")
        mode_combo = QtWidgets.QComboBox()
        mode_combo.setObjectName("comparisonModeCombo")
        mode_combo.addItems(["Standard", "Model comparison"])
        mode_row_layout.addWidget(mode_label)
        mode_row_layout.addWidget(mode_combo, 1)

        helper_label = QtWidgets.QLabel(
            "Single-image only. Compare up to two models on the selected image."
        )
        helper_label.setObjectName("comparisonHelperLabel")
        helper_label.setWordWrap(True)

        model_a_row = QtWidgets.QWidget()
        model_a_row_layout = QtWidgets.QHBoxLayout(model_a_row)
        model_a_row_layout.setContentsMargins(0, 0, 0, 0)
        model_a_label = QtWidgets.QLabel("Model A")
        model_a_combo = QtWidgets.QComboBox()
        model_a_combo.setObjectName("comparisonModelACombo")
        model_a_row_layout.addWidget(model_a_label)
        model_a_row_layout.addWidget(model_a_combo, 1)

        model_b_row = QtWidgets.QWidget()
        model_b_row_layout = QtWidgets.QHBoxLayout(model_b_row)
        model_b_row_layout.setContentsMargins(0, 0, 0, 0)
        model_b_label = QtWidgets.QLabel("Model B (optional)")
        model_b_combo = QtWidgets.QComboBox()
        model_b_combo.setObjectName("comparisonModelBCombo")
        model_b_row_layout.addWidget(model_b_label)
        model_b_row_layout.addWidget(model_b_combo, 1)

        layout.addWidget(mode_row)
        layout.addWidget(helper_label)
        layout.addWidget(model_a_row)
        layout.addWidget(model_b_row)

        self.mode_combo = mode_combo
        self.model_a_combo = model_a_combo
        self.model_b_combo = model_b_combo
        self.helper_label = helper_label
        self.model_b_label = model_b_label
        self._models_available = False
        self._load_models()
        self._apply_mode(mode_combo.currentText())

        mode_combo.currentTextChanged.connect(self._apply_mode)
        self._batch_mode = False

    def _load_models(self) -> None:
        model_names = self._load_model_names()
        self.model_a_combo.clear()
        self.model_b_combo.clear()
        if not model_names:
            self.model_a_combo.addItem("No models available")
            self.model_b_combo.addItem("None")
            self.model_a_combo.setEnabled(False)
            self.model_b_combo.setEnabled(False)
            self._models_available = False
            return

        self._models_available = True
        self.model_a_combo.addItems(model_names)
        self.model_b_combo.addItems(["None", *model_names])

    def _load_model_names(self) -> list[str]:
        repo_root = os.path.dirname(os.path.dirname(__file__))
        registry_path = os.path.join(repo_root, "models", "registry.json")
        try:
            with open(registry_path, "r", encoding="utf-8") as handle:
                data = json.load(handle)
        except (OSError, json.JSONDecodeError):
            return []
        if not isinstance(data, list):
            return []
        names: list[str] = []
        for entry in data:
            if not isinstance(entry, dict):
                continue
            name = entry.get("name")
            if isinstance(name, str) and name:
                names.append(name)
        return names

    def _apply_mode(self, mode: str) -> None:
        comparison = mode == "Model comparison"
        if not self._models_available:
            self.model_a_combo.setEnabled(False)
            self.model_b_combo.setEnabled(False)
            return
        self.model_a_combo.setEnabled(comparison)
        self.model_b_combo.setEnabled(comparison)

    def set_batch_mode(self, enabled: bool) -> None:
        self._batch_mode = enabled
        if enabled and self.mode_combo.currentText() != "Standard":
            self.mode_combo.setCurrentText("Standard")
        self.mode_combo.setEnabled(not enabled)

    def is_comparison_mode(self) -> bool:
        return self.mode_combo.currentText() == "Model comparison"

    def selected_model_a(self) -> str | None:
        if not self._models_available:
            return None
        return self.model_a_combo.currentText()

    def selected_model_b(self) -> str | None:
        if not self._models_available:
            return None
        selection = self.model_b_combo.currentText()
        if selection == "None":
            return None
        return selection

    def comparison_labels(self) -> tuple[str, str]:
        if not self.is_comparison_mode():
            return ("Before", "After")
        model_a = self.selected_model_a()
        model_b = self.selected_model_b()
        before_label = "Model A"
        if model_a:
            before_label = f"Model A: {model_a}"
        after_label = "Model B (optional)"
        if model_b:
            after_label = f"Model B: {model_b}"
        return (before_label, after_label)

    def placeholder_texts(self) -> tuple[str, str]:
        if not self.is_comparison_mode():
            return ("Preview will appear here", "Upscaled preview will appear here")
        before_text = "Model output will appear here"
        after_text = "Model output will appear here"
        if self.selected_model_b() is None:
            after_text = "Select a second model to compare."
        return (before_text, after_text)


class ExportPresetsPanel(QtWidgets.QGroupBox):
    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__("Export Presets", parent)
        self.setObjectName("exportPresetsPanel")
        layout = QtWidgets.QVBoxLayout(self)
        layout.setSpacing(8)

        helper_text = QtWidgets.QLabel(
            "Choose a preset to configure export settings for common datasets."
        )
        helper_text.setWordWrap(True)
        helper_text.setObjectName("exportPresetsHelper")

        preset_list = QtWidgets.QListWidget()
        preset_list.setObjectName("exportPresetList")
        preset_list.setSelectionMode(
            QtWidgets.QAbstractItemView.SelectionMode.SingleSelection
        )

        recommended_row = QtWidgets.QWidget()
        recommended_row_layout = QtWidgets.QHBoxLayout(recommended_row)
        recommended_row_layout.setContentsMargins(0, 0, 0, 0)
        recommended_row_layout.setSpacing(6)
        recommended_label = QtWidgets.QLabel("Recommended preset")
        recommended_label.setObjectName("recommendedPresetLabel")
        recommended_combo = QtWidgets.QComboBox()
        recommended_combo.setObjectName("recommendedPresetCombo")
        use_recommended_button = QtWidgets.QPushButton("Use recommended")
        use_recommended_button.setObjectName("useRecommendedPresetButton")
        recommended_row_layout.addWidget(recommended_label)
        recommended_row_layout.addWidget(recommended_combo, 1)
        recommended_row_layout.addWidget(use_recommended_button)

        details_form = QtWidgets.QWidget()
        details_form_layout = QtWidgets.QFormLayout(details_form)
        details_form_layout.setContentsMargins(0, 0, 0, 0)
        details_form_layout.setSpacing(6)
        band_handling_combo = QtWidgets.QComboBox()
        band_handling_combo.setObjectName("bandHandlingCombo")
        band_handling_combo.addItems(BandHandling.labels())
        output_format_combo = QtWidgets.QComboBox()
        output_format_combo.setObjectName("outputFormatCombo")
        output_format_combo.addItems(["Match input", "GeoTIFF", "PNG", "JPEG"])
        details_form_layout.addRow("Band handling", band_handling_combo)
        details_form_layout.addRow("Output format", output_format_combo)

        metadata_warning = QtWidgets.QLabel("")
        metadata_warning.setObjectName("metadataWarningLabel")
        metadata_warning.setWordWrap(True)
        metadata_warning.setVisible(False)

        preset_description = QtWidgets.QLabel("Select a preset to see details.")
        preset_description.setObjectName("presetDescription")
        preset_description.setWordWrap(True)

        layout.addWidget(helper_text)
        layout.addWidget(preset_list)
        layout.addWidget(recommended_row)
        layout.addWidget(details_form)
        layout.addWidget(metadata_warning)
        layout.addWidget(preset_description)

        self.preset_list = preset_list
        self.recommended_label = recommended_label
        self.recommended_combo = recommended_combo
        self.use_recommended_button = use_recommended_button
        self.band_handling_combo = band_handling_combo
        self.output_format_combo = output_format_combo
        self.metadata_warning_label = metadata_warning
        self.preset_description = preset_description
        self._input_format: str | None = None
        self._recommended_label_text = recommended_label.text()

        self._presets = self._build_presets()
        self._populate_presets()
        self._select_initial_preset()

        preset_list.currentRowChanged.connect(self._apply_selected_preset)
        use_recommended_button.clicked.connect(self._apply_recommended_preset)
        output_format_combo.currentTextChanged.connect(self._update_metadata_warning)

    def _build_presets(self) -> list[dict[str, str]]:
        return [
            {
                "name": "Sentinel-2",
                "description": "Balanced export for Sentinel-2 tiles with multispectral data.",
                "band_handling": "RGB + all bands",
                "output_format": "GeoTIFF",
            },
            {
                "name": "PlanetScope",
                "description": "Optimized for 4-band PlanetScope imagery with RGB focus.",
                "band_handling": "RGB + all bands",
                "output_format": "GeoTIFF",
            },
            {
                "name": "Vantor",
                "description": "High-resolution export with RGB emphasis for WorldView-class data.",
                "band_handling": "RGB only",
                "output_format": "GeoTIFF",
            },
            {
                "name": "21AT",
                "description": (
                    "Conservative export to preserve high-resolution commercial imagery."
                ),
                "band_handling": "RGB only",
                "output_format": "GeoTIFF",
            },
            {
                "name": "Landsat",
                "description": "Multispectral-aware export tuned for Landsat scenes.",
                "band_handling": "All bands",
                "output_format": "GeoTIFF",
            },
        ]

    def _populate_presets(self) -> None:
        self.preset_list.clear()
        self.recommended_combo.clear()
        for preset in self._presets:
            item = QtWidgets.QListWidgetItem(preset["name"])
            item.setData(QtCore.Qt.ItemDataRole.UserRole, preset)
            self.preset_list.addItem(item)
            self.recommended_combo.addItem(preset["name"])

    def _select_initial_preset(self) -> None:
        if self.preset_list.count() == 0:
            return
        self.preset_list.setCurrentRow(0)
        self.recommended_combo.setCurrentIndex(0)
        self._apply_selected_preset(0)

    def _apply_selected_preset(self, row: int) -> None:
        item = self.preset_list.item(row)
        if item is None:
            self.preset_description.setText("Select a preset to see details.")
            return
        preset = item.data(QtCore.Qt.ItemDataRole.UserRole)
        if not isinstance(preset, dict):
            return
        self.preset_description.setText(preset.get("description", ""))
        self.band_handling_combo.setCurrentText(
            preset.get("band_handling", BandHandling.RGB_ONLY.value)
        )
        self.output_format_combo.setCurrentText(preset.get("output_format", "Match input"))

    def _apply_recommended_preset(self) -> None:
        self.select_preset(self.recommended_combo.currentText())

    def select_preset(self, name: str) -> None:
        for index in range(self.preset_list.count()):
            item = self.preset_list.item(index)
            if item is None:
                continue
            if item.text() == name:
                self.preset_list.setCurrentRow(index)
                return

    def set_recommended_preset(self, name: str) -> None:
        if name and self.recommended_combo.findText(name) >= 0:
            self.recommended_combo.setCurrentText(name)

    def set_batch_mode(self, enabled: bool) -> None:
        self.recommended_combo.setEnabled(not enabled)
        self.use_recommended_button.setEnabled(not enabled)
        if enabled:
            self.recommended_label.setText("Recommended preset (batch disabled)")
        else:
            self.recommended_label.setText(self._recommended_label_text)

    def selected_band_handling(self) -> BandHandling:
        return BandHandling.from_label(self.band_handling_combo.currentText())

    def selected_output_format(self) -> str:
        return self.output_format_combo.currentText()

    def export_settings(self) -> ExportSettings:
        return ExportSettings(
            band_handling=self.selected_band_handling(),
            output_format=self.selected_output_format(),
        )

    def set_band_handling(self, band_handling: BandHandling | str) -> None:
        label = (
            band_handling.value
            if isinstance(band_handling, BandHandling)
            else band_handling
        )
        if self.band_handling_combo.findText(label) >= 0:
            self.band_handling_combo.setCurrentText(label)

    def set_input_format(self, input_format: str | None) -> None:
        self._input_format = input_format
        self._update_metadata_warning()

    def _update_metadata_warning(self) -> None:
        warning = metadata_loss_warning(self._input_format, self.selected_output_format())
        if warning:
            self.metadata_warning_label.setText(warning)
            self.metadata_warning_label.setVisible(True)
        else:
            self.metadata_warning_label.setText("")
            self.metadata_warning_label.setVisible(False)


class SystemInfoPanel(QtWidgets.QGroupBox):
    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__("About / System Info", parent)
        self.setObjectName("systemInfoPanel")
        layout = QtWidgets.QVBoxLayout(self)
        layout.setSpacing(6)

        helper_text = QtWidgets.QLabel(
            "Hardware detection may vary by driver availability."
        )
        helper_text.setWordWrap(True)
        helper_text.setObjectName("systemInfoHelper")

        info_form = QtWidgets.QWidget()
        info_form_layout = QtWidgets.QFormLayout(info_form)
        info_form_layout.setContentsMargins(0, 0, 0, 0)
        info_form_layout.setSpacing(6)

        gpu_value = QtWidgets.QLabel(_detect_gpu_info())
        gpu_value.setObjectName("systemInfoGpuValue")
        gpu_value.setTextInteractionFlags(QtCore.Qt.TextInteractionFlag.TextSelectableByMouse)

        cuda_value = QtWidgets.QLabel(_detect_cuda_version())
        cuda_value.setObjectName("systemInfoCudaValue")
        cuda_value.setTextInteractionFlags(QtCore.Qt.TextInteractionFlag.TextSelectableByMouse)

        model_versions = QtWidgets.QLabel(_format_model_versions(_load_model_registry()))
        model_versions.setObjectName("systemInfoModelVersionsValue")
        model_versions.setWordWrap(True)
        model_versions.setTextInteractionFlags(
            QtCore.Qt.TextInteractionFlag.TextSelectableByMouse
        )

        info_form_layout.addRow("GPU", gpu_value)
        info_form_layout.addRow("CUDA", cuda_value)
        info_form_layout.addRow("Model versions", model_versions)

        layout.addWidget(helper_text)
        layout.addWidget(info_form)

        self.gpu_value = gpu_value
        self.cuda_value = cuda_value
        self.model_versions_value = model_versions


class ChangelogPanel(QtWidgets.QGroupBox):
    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__("Changelog", parent)
        self.setObjectName("changelogPanel")
        layout = QtWidgets.QVBoxLayout(self)
        layout.setSpacing(6)

        helper_text = QtWidgets.QLabel(
            "Review recent app improvements and model package updates."
        )
        helper_text.setWordWrap(True)
        helper_text.setObjectName("changelogHelper")

        tabs = QtWidgets.QTabWidget()
        tabs.setObjectName("changelogTabs")

        app_tab, app_list, app_details = self._build_tab("appChangelogList")
        model_tab, model_list, model_details = self._build_tab("modelChangelogList")
        tabs.addTab(app_tab, "App Updates")
        tabs.addTab(model_tab, "Model Updates")

        layout.addWidget(helper_text)
        layout.addWidget(tabs)

        self.tabs = tabs
        self.app_list = app_list
        self.app_details = app_details
        self.model_list = model_list
        self.model_details = model_details
        self._app_entries = self._build_app_entries()
        self._model_entries = self._build_model_entries()
        self._populate_list(self.app_list, self._app_entries)
        self._populate_list(self.model_list, self._model_entries)
        self._select_initial(self.app_list, self._app_entries, self.app_details)
        self._select_initial(self.model_list, self._model_entries, self.model_details)

        self.app_list.currentRowChanged.connect(
            lambda row: self._apply_entry(row, self._app_entries, self.app_details)
        )
        self.model_list.currentRowChanged.connect(
            lambda row: self._apply_entry(row, self._model_entries, self.model_details)
        )

    def _build_tab(
        self, list_object_name: str
    ) -> tuple[QtWidgets.QWidget, QtWidgets.QListWidget, QtWidgets.QLabel]:
        tab = QtWidgets.QWidget()
        tab_layout = QtWidgets.QVBoxLayout(tab)
        tab_layout.setContentsMargins(0, 0, 0, 0)
        tab_layout.setSpacing(6)

        changelog_list = QtWidgets.QListWidget()
        changelog_list.setObjectName(list_object_name)
        changelog_list.setSelectionMode(
            QtWidgets.QAbstractItemView.SelectionMode.SingleSelection
        )

        details = QtWidgets.QLabel("Select an entry to see details.")
        details.setWordWrap(True)
        details.setObjectName(f"{list_object_name}Details")

        tab_layout.addWidget(changelog_list, 1)
        tab_layout.addWidget(details)
        return tab, changelog_list, details

    def _build_app_entries(self) -> list[dict[str, str]]:
        return [
            {
                "date": "2026-01-20",
                "title": "Preview workflow polish",
                "details": (
                    "Refined the preview comparison layout and added clearer empty-state "
                    "messaging for faster review."
                ),
            },
            {
                "date": "2026-01-05",
                "title": "Model manager baseline",
                "details": (
                    "Introduced one-click install/uninstall controls with version visibility."
                ),
            },
        ]

    def _build_model_entries(self) -> list[dict[str, str]]:
        entries = [
            {
                "date": "2026-01-18",
                "title": "Real-ESRGAN bundled",
                "details": "Bundled RGB model ready for instant upscaling workflows.",
            },
            {
                "date": "2026-01-12",
                "title": "Satlas bundled",
                "details": "Bundled multi-band model tuned for Sentinel-2 scenes.",
            },
        ]
        return entries

    def _populate_list(
        self, changelog_list: QtWidgets.QListWidget, entries: list[dict[str, str]]
    ) -> None:
        changelog_list.clear()
        for entry in entries:
            label = f"{entry['date']} — {entry['title']}"
            item = QtWidgets.QListWidgetItem(label)
            item.setData(QtCore.Qt.ItemDataRole.UserRole, entry)
            changelog_list.addItem(item)

    def _select_initial(
        self,
        changelog_list: QtWidgets.QListWidget,
        entries: list[dict[str, str]],
        details: QtWidgets.QLabel,
    ) -> None:
        if changelog_list.count() == 0:
            details.setText("No updates available.")
            return
        changelog_list.setCurrentRow(0)
        self._apply_entry(0, entries, details)

    def _apply_entry(
        self,
        row: int,
        entries: list[dict[str, str]],
        details: QtWidgets.QLabel,
    ) -> None:
        if row < 0 or row >= len(entries):
            details.setText("Select an entry to see details.")
            return
        entry = entries[row]
        details.setText(f"{entry['date']} — {entry['details']}")


class MainWindow(QtWidgets.QMainWindow):
    run_completed = QtCore.Signal()
    export_completed = QtCore.Signal()

    def __init__(
        self, notification_manager: "DesktopNotificationManager | None" = None
    ) -> None:
        super().__init__()
        self.notification_manager = notification_manager or DesktopNotificationManager()
        self.setWindowTitle("Satellite Upscale")
        self._build_ui()
        self._configure_shortcuts()
        self._current_preview_image: QtGui.QImage | None = None
        self._update_comparison_state()
        self._session_store = SessionStore()
        self._restoring_session = False
        self._session_dirty = False
        self._autosave_timer = QtCore.QTimer(self)
        self._restore_session_if_needed()
        self._mark_session_active()
        self._configure_session_autosave()

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

        model_comparison_panel = ModelComparisonPanel()

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
            "Stitch extent",
            "Tile boundaries",
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
        workflow_stage_names = [stage_label for stage_label, _ in workflow_stages]

        right_layout.addWidget(preview_group)
        right_layout.addWidget(model_comparison_panel)
        right_layout.addWidget(metadata_group)
        right_layout.addWidget(workflow_group)
        export_presets_panel = ExportPresetsPanel()
        right_layout.addWidget(export_presets_panel)
        advanced_options_panel = AdvancedOptionsPanel()
        right_layout.addWidget(advanced_options_panel)
        model_manager_panel = ModelManagerPanel()
        right_layout.addWidget(model_manager_panel)
        changelog_panel = ChangelogPanel()
        right_layout.addWidget(changelog_panel)
        system_info_panel = SystemInfoPanel()
        right_layout.addWidget(system_info_panel)
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
        status_bar = self.statusBar()
        status_bar.setObjectName("mainStatusBar")
        self.splitter = splitter
        self.left_panel = left_panel
        self.input_list = input_list
        self.add_files_button = add_files_button
        self.add_folder_button = add_folder_button
        self.comparison_viewer = comparison_viewer
        self.model_comparison_panel = model_comparison_panel
        self.metadata_summary = metadata_summary
        self.metadata_value_labels = metadata_value_labels
        self.workflow_group = workflow_group
        self.workflow_stage_labels = workflow_stage_labels
        self.workflow_stage_actions = workflow_stage_actions
        self.workflow_stage_names = workflow_stage_names
        self.export_presets_panel = export_presets_panel
        self.advanced_options_panel = advanced_options_panel
        self.model_manager_panel = model_manager_panel
        self.changelog_panel = changelog_panel
        self.system_info_panel = system_info_panel
        self.status_bar = status_bar
        self.run_button: QtWidgets.QPushButton | None = None
        self._batch_mode = False
        self.last_run_settings: RunSettings | None = None

        add_files_button.clicked.connect(self._select_files)
        add_folder_button.clicked.connect(self._select_folder)
        input_list.itemSelectionChanged.connect(self._handle_selection_change)
        input_list.itemSelectionChanged.connect(self._persist_session_state)
        input_list.paths_added.connect(self._select_latest_added)
        input_list.paths_added.connect(self._persist_session_state)
        model_comparison_panel.mode_combo.currentTextChanged.connect(
            self._update_comparison_state
        )
        model_comparison_panel.model_a_combo.currentTextChanged.connect(
            self._update_comparison_state
        )
        model_comparison_panel.model_b_combo.currentTextChanged.connect(
            self._update_comparison_state
        )
        advanced_options_panel.completion_notification_check.toggled.connect(
            self._set_completion_notifications_enabled
        )
        self._set_completion_notifications_enabled(
            advanced_options_panel.completion_notification_check.isChecked()
        )
        self._wire_workflow_completion_notifications()
        self._wire_workflow_stage_actions()
        self._wire_run_action()

    def _configure_shortcuts(self) -> None:
        self.add_files_button.setShortcut(QtGui.QKeySequence("Ctrl+O"))
        self.add_folder_button.setShortcut(QtGui.QKeySequence("Ctrl+Shift+O"))
        workflow_shortcuts = [
            "Ctrl+1",
            "Ctrl+2",
            "Ctrl+3",
            "Ctrl+4",
            "Ctrl+5",
            "Ctrl+6",
        ]
        for action_button, shortcut in zip(
            self.workflow_stage_actions, workflow_shortcuts, strict=True
        ):
            action_button.setShortcut(QtGui.QKeySequence(shortcut))

    def _set_completion_notifications_enabled(self, enabled: bool) -> None:
        self.notification_manager.set_enabled(enabled)

    def _wire_workflow_completion_notifications(self) -> None:
        self.run_completed.connect(
            lambda: self._notify_workflow_completion("Run")
        )
        self.export_completed.connect(
            lambda: self._notify_workflow_completion("Export")
        )

    def _notify_workflow_completion(self, stage_name: str) -> None:
        title = f"{stage_name} complete"
        message = f"{stage_name} finished. You're ready for the next step."
        self.notification_manager.notify(title, message, parent=self)

    def _schedule_run_completion(self) -> None:
        QtCore.QTimer.singleShot(0, self.run_completed.emit)

    def _schedule_export_completion(self) -> None:
        QtCore.QTimer.singleShot(0, self.export_completed.emit)

    def _wire_run_action(self) -> None:
        if "Run" not in self.workflow_stage_names:
            return
        run_index = self.workflow_stage_names.index("Run")
        if run_index >= len(self.workflow_stage_actions):
            return
        self.run_button = self.workflow_stage_actions[run_index]
        self.run_button.clicked.connect(self._handle_run_clicked)

    def _wire_workflow_stage_actions(self) -> None:
        handlers = {
            "Import": self._handle_import_stage,
            "Review": self._handle_review_stage,
            "Stitch (Optional)": self._handle_stitch_stage,
            "Recommend": self._handle_recommend_stage,
            "Export": self._handle_export_stage,
        }
        for stage_name, button in zip(
            self.workflow_stage_names, self.workflow_stage_actions, strict=True
        ):
            handler = handlers.get(stage_name)
            if handler is not None:
                button.clicked.connect(handler)

    def _set_workflow_message(self, message: str) -> None:
        self.status_bar.showMessage(message)

    def _handle_import_stage(self) -> None:
        self.add_files_button.setFocus()
        self._set_workflow_message("Import: add files or folders to begin.")

    def _handle_review_stage(self) -> None:
        selected_paths = self._selected_input_paths()
        if len(selected_paths) == 1:
            message = "Review: preview and metadata updated for the selected file."
        elif len(selected_paths) > 1:
            message = "Review: select a single file to inspect details."
        else:
            message = "Review: select a file to inspect preview and metadata."
        self.comparison_viewer.setFocus()
        self._set_workflow_message(message)

    def _handle_stitch_stage(self) -> None:
        selected_paths = self._selected_input_paths()
        if len(selected_paths) < 2:
            message = "Stitch: select at least two tiles to preview mosaic bounds."
            self._set_workflow_message(message)
            return
        suggestion = suggest_mosaic(selected_paths)
        preview_metadata = self._preview_stitch_metadata(selected_paths)
        if preview_metadata:
            self._set_metadata_placeholders()
            self._set_metadata(preview_metadata)
        if suggestion.message:
            message = f"Stitch: {suggestion.message}"
        elif preview_metadata:
            message = "Stitch: stitch bounds previewed in metadata."
        else:
            message = "Stitch: no mosaic hints detected in selected tiles."
        self._set_workflow_message(message)

    def _handle_recommend_stage(self) -> None:
        selected_paths = self._selected_input_paths()
        if len(selected_paths) != 1:
            if selected_paths:
                message = "Recommend: select a single file for recommendations."
            else:
                message = "Recommend: select a single file to set a recommended preset."
            self._set_workflow_message(message)
            return
        from app.provider_detection import recommend_provider

        recommendation = recommend_provider(selected_paths[0])
        if recommendation.ambiguous:
            selection = self._prompt_for_provider_selection(recommendation.candidates)
            if selection:
                self.export_presets_panel.set_recommended_preset(selection)
                self._set_workflow_message(
                    f"Recommend: selected provider '{selection}' for the preset."
                )
                return
            candidates = ", ".join(match.name for match in recommendation.candidates)
            message = (
                "Recommend: multiple providers match "
                f"({candidates}). Choose a preset manually."
            )
            self._set_workflow_message(message)
            return
        if recommendation.best:
            self.export_presets_panel.set_recommended_preset(recommendation.best)
            self._set_workflow_message(
                f"Recommend: suggested preset '{recommendation.best}' ready."
            )
            return
        self._set_workflow_message(
            "Recommend: no provider match; choose a preset manually."
        )

    def _handle_export_stage(self) -> None:
        self.export_presets_panel.setFocus()
        self._set_workflow_message(
            "Export: confirm the preset and output format before saving outputs."
        )
        self._schedule_export_completion()

    def _handle_run_clicked(self) -> None:
        try:
            self._start_run()
        except Exception as exc:  # noqa: BLE001
            self._show_error_dialog(exc, retry_action=self._handle_run_clicked)

    def _start_run(self) -> None:
        selected_paths = self._selected_input_paths()
        if not selected_paths:
            raise UserFacingError(
                title="Nothing to run",
                summary="No input files are selected yet.",
                suggested_fixes=(
                    "Add one or more files to the list.",
                    "Select a file before starting a run.",
                ),
                error_code="INPUT-001",
                can_retry=True,
            )

        missing_paths = [path for path in selected_paths if not os.path.exists(path)]
        if missing_paths:
            sample_paths = ", ".join(missing_paths[:3])
            if len(missing_paths) > 3:
                sample_paths = f"{sample_paths}, and {len(missing_paths) - 3} more"
            raise UserFacingError(
                title="Input file missing",
                summary="One or more selected inputs can no longer be found on disk.",
                suggested_fixes=(
                    f"Verify these paths still exist: {sample_paths}.",
                    "Re-add the files or update your selection.",
                ),
                error_code="IO-001",
                can_retry=True,
            )
        self.last_run_settings = self._current_run_settings()
        self._schedule_run_completion()

    def _selected_input_paths(self) -> list[str]:
        paths = [item.text() for item in self.input_list.selectedItems()]
        if paths == [self.input_list.placeholder_text]:
            return []
        return [path for path in paths if path]

    def _current_run_settings(self) -> RunSettings:
        panel = self.advanced_options_panel
        return RunSettings(
            scale=parse_scale(panel.scale_combo.currentText()),
            tiling=parse_tiling(panel.tiling_combo.currentText()),
            precision=parse_precision(panel.precision_combo.currentText()),
            compute=parse_compute(panel.compute_combo.currentText()),
            seam_blend=panel.seam_blend_check.isChecked(),
            safe_mode=panel.safe_mode_check.isChecked(),
        )

    def _show_error_dialog(
        self,
        exc: Exception,
        retry_action: Callable[[], None] | None = None,
    ) -> None:
        error = as_user_facing_error(exc)
        dialog = ErrorDialog(error, retry_action=retry_action, parent=self)
        dialog.exec()

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

    def _restore_session_if_needed(self) -> None:
        state = self._session_store.load()
        if not state.dirty or not state.paths:
            return
        self._restoring_session = True
        try:
            self.input_list.add_paths(state.paths)
            if state.selected_paths:
                self._select_session_paths(state.selected_paths)
        finally:
            self._restoring_session = False

    def _select_session_paths(self, paths: list[str]) -> None:
        if not paths:
            return
        targets = set(paths)
        self.input_list.clearSelection()
        last_selected = None
        for index in range(self.input_list.count()):
            item = self.input_list.item(index)
            if item.text() in targets:
                item.setSelected(True)
                last_selected = item
        if last_selected is not None:
            self.input_list.scrollToItem(last_selected)

    def _current_input_paths(self) -> list[str]:
        paths = [self.input_list.item(index).text() for index in range(self.input_list.count())]
        return [
            path
            for path in paths
            if path and path != self.input_list.placeholder_text
        ]

    def _current_selected_paths(self) -> list[str]:
        paths = [item.text() for item in self.input_list.selectedItems()]
        return [
            path
            for path in paths
            if path and path != self.input_list.placeholder_text
        ]

    def _persist_session_state(self, *args: object, dirty: bool | None = None) -> None:
        if self._restoring_session:
            return
        if dirty is None:
            dirty = self._session_dirty
        state = SessionState(
            dirty=dirty,
            paths=self._current_input_paths(),
            selected_paths=self._current_selected_paths(),
        )
        self._session_dirty = state.dirty
        self._session_store.save(state)

    def _mark_session_active(self) -> None:
        self._session_dirty = True
        self._persist_session_state(dirty=True)

    def _configure_session_autosave(self) -> None:
        self._autosave_timer.setInterval(30_000)
        self._autosave_timer.timeout.connect(self._autosave_session_state)
        self._autosave_timer.start()

    def _autosave_session_state(self) -> None:
        self._persist_session_state()

    def _update_comparison_state(self) -> None:
        before_label, after_label = self.model_comparison_panel.comparison_labels()
        self.comparison_viewer.set_titles(before_label, after_label)

        if not self.model_comparison_panel.is_comparison_mode():
            if self._current_preview_image is None:
                self.comparison_viewer.set_before_placeholder("Preview will appear here")
            else:
                self.comparison_viewer.set_before_image(self._current_preview_image)
            self.comparison_viewer.set_after_placeholder("Upscaled preview will appear here")
            return

        before_placeholder, after_placeholder = (
            self.model_comparison_panel.placeholder_texts()
        )
        if self._current_preview_image is None:
            self.comparison_viewer.set_before_placeholder(before_placeholder)
            self.comparison_viewer.set_after_placeholder(after_placeholder)
            return

        if self.model_comparison_panel.selected_model_a() is None:
            self.comparison_viewer.set_before_placeholder(before_placeholder)
        else:
            self.comparison_viewer.set_before_image(self._current_preview_image)

        if self.model_comparison_panel.selected_model_b() is None:
            self.comparison_viewer.set_after_placeholder(after_placeholder)
        else:
            self.comparison_viewer.set_after_image(self._current_preview_image)

    def closeEvent(self, event: QtGui.QCloseEvent) -> None:  # noqa: N802
        if self._autosave_timer.isActive():
            self._autosave_timer.stop()
        self._persist_session_state(dirty=False)
        super().closeEvent(event)

    def _handle_selection_change(self) -> None:
        selected_paths = self._selected_input_paths()
        self._set_batch_mode(len(selected_paths) > 1)
        items = self.input_list.selectedItems()
        if len(items) != 1:
            message = "Select a single file to preview."
            preview_metadata: dict[str, str] = {}
            if not items:
                message = "Select a file to see metadata."
            elif len(items) > 1:
                paths = [item.text() for item in items]
                mosaic_hint = suggest_mosaic(paths)
                preview_metadata = self._preview_stitch_metadata(paths)
                if self.model_comparison_panel.is_comparison_mode():
                    message = "Model comparison requires a single image."
                    if mosaic_hint.message:
                        message = f"{message} {mosaic_hint.message}"
                else:
                    message = mosaic_hint.message or "Multiple items selected."
            self._current_preview_image = None
            self._update_comparison_state()
            self.metadata_summary.setText(message)
            self._set_metadata_placeholders()
            if preview_metadata:
                self._set_metadata(preview_metadata)
            self.export_presets_panel.set_input_format(None)
            return

        selected_path = items[0].text()
        if selected_path == self.input_list.placeholder_text:
            self._current_preview_image = None
            self._update_comparison_state()
            self.metadata_summary.setText("Select a file to see metadata.")
            self._set_metadata_placeholders()
            self.export_presets_panel.set_input_format(None)
            return

        self._load_preview_and_metadata(selected_path)

    def _set_batch_mode(self, enabled: bool) -> None:
        if self._batch_mode == enabled:
            return
        self._batch_mode = enabled
        self.export_presets_panel.set_batch_mode(enabled)
        self.model_comparison_panel.set_batch_mode(enabled)

    def _load_preview_and_metadata(self, path: str) -> None:
        self._update_recommended_preset(path)
        if not os.path.exists(path):
            self._current_preview_image = None
            if self.model_comparison_panel.is_comparison_mode():
                self.comparison_viewer.set_before_placeholder(
                    "Preview unavailable for this file."
                )
                self.comparison_viewer.set_after_placeholder(
                    "Preview unavailable for this file."
                )
            else:
                self.comparison_viewer.set_before_placeholder(
                    "Preview unavailable for this file."
                )
                self.comparison_viewer.set_after_placeholder("Upscaled preview will appear here")
            self.metadata_summary.setText("File not found.")
            self._set_metadata_placeholders()
            self.export_presets_panel.set_input_format(None)
            return

        image = self._read_image(path)
        if image is None:
            self._current_preview_image = None
            if self.model_comparison_panel.is_comparison_mode():
                self.comparison_viewer.set_before_placeholder(
                    "No preview available for this file."
                )
                self.comparison_viewer.set_after_placeholder(
                    "No preview available for this file."
                )
            else:
                self.comparison_viewer.set_before_placeholder(
                    "No preview available for this file."
                )
                self.comparison_viewer.set_after_placeholder("Upscaled preview will appear here")
        else:
            self._current_preview_image = image
            self._update_comparison_state()
        metadata = self._build_metadata(path)
        filename = metadata.get("Filename", os.path.basename(path))
        self.metadata_summary.setText(f"Metadata for {filename}")
        self._set_metadata(metadata)
        self.export_presets_panel.set_input_format(metadata.get("Format"))

    def _update_recommended_preset(self, path: str) -> None:
        recommendation = self._recommended_preset_for_path(path)
        if recommendation is None:
            return
        self.export_presets_panel.set_recommended_preset(recommendation)

    def _recommended_preset_for_path(self, path: str) -> str | None:
        from app.provider_detection import recommend_provider

        recommendation = recommend_provider(path)
        return recommendation.best

    def _prompt_for_provider_selection(
        self, candidates: tuple["ProviderMatch", ...]
    ) -> str | None:
        if not candidates:
            return None
        names = [candidate.name for candidate in candidates]
        message = (
            "Multiple providers match this file. Choose the correct provider to set "
            "the recommended export preset."
        )
        selection, accepted = QtWidgets.QInputDialog.getItem(
            self,
            "Select provider",
            message,
            names,
            0,
            False,
        )
        if accepted and selection:
            return selection
        return None

    def _read_image(self, path: str) -> QtGui.QImage | None:
        reader = QtGui.QImageReader(path)
        if not reader.canRead():
            return None
        image = reader.read()
        if image.isNull():
            return None
        return image

    def _preview_stitch_metadata(self, paths: list[str]) -> dict[str, str]:
        preview = preview_stitch_bounds(paths)
        if preview is None:
            return {}
        return {
            "Stitch extent": preview.extent,
            "Tile boundaries": preview.boundaries,
        }

    def _build_metadata(self, path: str) -> dict[str, str]:
        info = QtCore.QFileInfo(path)
        metadata: dict[str, str] = {
            "Filename": info.fileName() or "Unknown",
            "Path": info.absoluteFilePath() or path,
            "File size": _format_bytes(info.size()),
            "Modified": info.lastModified().toString(QtCore.Qt.DateFormat.ISODate) or "Unknown",
        }
        reader = QtGui.QImageReader(path)
        fmt_text = None
        dimensions = None
        if reader.canRead():
            fmt = reader.format()
            fmt_text = fmt.data().decode("ascii", errors="ignore").upper() if fmt else "Unknown"
            size = reader.size()
            if size.isValid():
                dimensions = f"{size.width()} x {size.height()} px"
        header_info = extract_image_header_info(path)
        if header_info is not None:
            if fmt_text in {None, "Unknown", "Not an image"}:
                fmt_text = header_info.format
            elif header_info.format == "GeoTIFF" and fmt_text in {"TIFF", "TIF"}:
                fmt_text = "GeoTIFF"
            if dimensions in {None, "Unknown"} and header_info.width and header_info.height:
                dimensions = f"{header_info.width} x {header_info.height} px"
        if fmt_text is None:
            fmt_text = "Not an image"
        if dimensions is None:
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


class DesktopNotificationManager:
    def __init__(self) -> None:
        self._enabled = False
        self._tray_icon: QtWidgets.QSystemTrayIcon | None = None

    def set_enabled(self, enabled: bool) -> None:
        self._enabled = enabled
        if not enabled and self._tray_icon is not None:
            self._tray_icon.hide()

    def notify(
        self, title: str, message: str, parent: QtWidgets.QWidget | None = None
    ) -> bool:
        if not self._enabled:
            return False
        if not QtWidgets.QSystemTrayIcon.isSystemTrayAvailable():
            return False
        if self._tray_icon is None:
            icon = parent.windowIcon() if parent is not None else QtGui.QIcon()
            if icon.isNull() and parent is not None:
                icon = parent.style().standardIcon(
                    QtWidgets.QStyle.StandardPixmap.SP_ComputerIcon
                )
            self._tray_icon = QtWidgets.QSystemTrayIcon(icon, parent)
            self._tray_icon.setVisible(True)
        self._tray_icon.showMessage(
            title,
            message,
            QtWidgets.QSystemTrayIcon.MessageIcon.Information,
        )
        return True


def main() -> int:
    app = create_app()
    window = MainWindow()
    window.resize(1100, 700)
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())

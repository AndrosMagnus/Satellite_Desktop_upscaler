from __future__ import annotations

from PySide6 import QtCore, QtWidgets


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Satellite Upscale")
        self._build_ui()

    def _build_ui(self) -> None:
        splitter = QtWidgets.QSplitter(QtCore.Qt.Orientation.Horizontal)
        splitter.setObjectName("primarySplitter")

        input_list = QtWidgets.QListWidget()
        input_list.setObjectName("inputList")
        input_list.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.ExtendedSelection)
        input_list.addItem("Drop files or folders here to begin.")

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

        splitter.addWidget(input_list)
        splitter.addWidget(right_panel)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 2)

        container = QtWidgets.QWidget()
        container_layout = QtWidgets.QHBoxLayout(container)
        container_layout.setContentsMargins(0, 0, 0, 0)
        container_layout.addWidget(splitter)

        self.setCentralWidget(container)
        self.splitter = splitter
        self.input_list = input_list
        self.preview_label = preview_label
        self.metadata_summary = metadata_summary
        self.workflow_group = workflow_group
        self.workflow_stage_labels = workflow_stage_labels
        self.workflow_stage_actions = workflow_stage_actions


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

"""UI package for the desktop upscaler."""

try:
    from .ui import MainWindow, create_app
except ModuleNotFoundError:  # pragma: no cover - allows non-UI tests without PySide6.
    MainWindow = None
    create_app = None

__all__ = ["MainWindow", "create_app"]

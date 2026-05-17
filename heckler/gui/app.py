"""GUI entry point: Qt application, model loading thread, ``PipelineController`` wiring."""

from __future__ import annotations

import logging
import sys
import threading

from PyQt6.QtCore import QThread, pyqtSignal
from PyQt6.QtWidgets import QApplication, QMessageBox

from heckler.config import load_config
from heckler.controller import PipelineController
from heckler.gui.main_window import HecklerMainWindow, SignalBridge

logger = logging.getLogger(__name__)


class ModelLoadThread(QThread):
    """Runs ``PipelineController.load_models`` off the GUI thread."""

    progress = pyqtSignal(str)
    finished_ok = pyqtSignal()
    failed = pyqtSignal(str)

    def __init__(self, controller: PipelineController) -> None:
        super().__init__()
        self._controller = controller

    def run(self) -> None:  # pragma: no cover — exercised via integration / manual run
        threading.current_thread().name = "heckler-gui-loader"
        try:

            def on_prog(msg: str) -> None:
                self.progress.emit(msg)

            self._controller.load_models(on_progress=on_prog)
            self.finished_ok.emit()
        except Exception as e:
            logger.exception("Model loading failed")
            self.failed.emit(str(e))


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    app = QApplication(sys.argv)

    config = load_config()
    bridge = SignalBridge()
    controller = PipelineController(config, bridge.as_callbacks())
    window = HecklerMainWindow(config, controller)
    window.attach_bridge(bridge)
    window.show()

    loader = ModelLoadThread(controller)

    def on_progress(msg: str) -> None:
        window.statusBar().showMessage(msg)

    def on_ready() -> None:
        window.set_models_ready(True)

    def on_failed(msg: str) -> None:
        QMessageBox.critical(window, "Model load failed", msg)
        app.quit()

    loader.progress.connect(on_progress)
    loader.finished_ok.connect(on_ready)
    loader.failed.connect(on_failed)
    loader.start()

    sys.exit(app.exec())

"""GUI entry point: Qt application, model loading thread, ``PipelineController`` wiring."""

from __future__ import annotations

import logging
import sys
import threading

from PyQt6.QtCore import QThread, pyqtSignal
from PyQt6.QtWidgets import QApplication, QMessageBox

from heckler.config import HecklerConfig, load_config
from heckler.controller import PipelineController
from heckler.gui.main_window import HecklerMainWindow, SignalBridge

logger = logging.getLogger(__name__)


class ModelLoadThread(QThread):
    """Runs ``PipelineController.load_models`` off the GUI thread."""

    progress = pyqtSignal(str)
    finished_ok = pyqtSignal()
    failed = pyqtSignal(str)

    def __init__(self, controller: PipelineController, config: HecklerConfig) -> None:
        super().__init__()
        self._controller = controller
        self._config = config

    def run(self) -> None:  # pragma: no cover — exercised via integration / manual run
        threading.current_thread().name = "heckler-gui-loader"
        try:

            def on_prog(msg: str) -> None:
                self.progress.emit(msg)

            mode = (self._config.mode or "persona").strip().lower()
            persona_name = self._config.persona_name if mode == "persona" else None
            self._controller.load_models(
                on_progress=on_prog,
                mode=mode,
                persona_name=persona_name,
            )
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

    loader = ModelLoadThread(controller, config)

    def on_progress(msg: str) -> None:
        status_bar = window.statusBar()
        if status_bar is not None:
            status_bar.showMessage(msg)

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

"""Main Qt window: mode toggle, persona picker, live feeds, session controls."""

from __future__ import annotations

import logging
from pathlib import Path

from PyQt6.QtCore import QObject, QUrl, pyqtSignal
from PyQt6.QtGui import QDesktopServices
from PyQt6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QRadioButton,
    QVBoxLayout,
    QWidget,
)

from heckler.config import HecklerConfig
from heckler.controller import (
    ControllerCallbacks,
    PipelineAlreadyRunningError,
    PipelineController,
    PipelineNotRunningError,
)
from heckler.models import ReactorResult
from heckler.persona import PersonaNotFoundError, list_personas

logger = logging.getLogger(__name__)


def _prompts_root() -> Path:
    """Repository ``prompts/`` directory (same resolution rule as ``PipelineController``)."""
    return Path(__file__).resolve().parent.parent.parent / "prompts"


class SignalBridge(QObject):
    """Thread-safe bridge from ``ControllerCallbacks`` (worker threads) to the GUI thread."""

    transcript_received = pyqtSignal(str)
    reaction_received = pyqtSignal(object, bool)  # ReactorResult, was_spoken
    status_received = pyqtSignal(str)
    error_received = pyqtSignal(str)

    def as_callbacks(self) -> ControllerCallbacks:
        return ControllerCallbacks(
            on_transcript=self.transcript_received.emit,
            on_reaction=lambda result, spoken: self.reaction_received.emit(result, spoken),
            on_status=self.status_received.emit,
            on_error=self.error_received.emit,
        )


class HecklerMainWindow(QMainWindow):
    """Single-window launcher: persona ↔ transcribe, feeds, start/stop, model-load gating."""

    def __init__(self, config: HecklerConfig, controller: PipelineController) -> None:
        super().__init__()
        self._config = config
        self._controller = controller
        self._models_ready = False

        self.setWindowTitle("Heckler")
        self.resize(720, 520)

        central = QWidget(self)
        self.setCentralWidget(central)
        root = QVBoxLayout(central)

        mode_box = QGroupBox("Mode")
        mode_row = QHBoxLayout(mode_box)
        self._radio_persona = QRadioButton("Persona")
        self._radio_transcribe = QRadioButton("Transcribe")
        mode_row.addWidget(self._radio_persona)
        mode_row.addWidget(self._radio_transcribe)
        mode_row.addStretch(1)
        root.addWidget(mode_box)

        header = QHBoxLayout()
        header.addWidget(QLabel("Persona:"))
        self._persona_combo = QComboBox()
        header.addWidget(self._persona_combo, stretch=1)
        root.addLayout(header)

        speech_row = QHBoxLayout()
        speech_row.addWidget(QLabel("Speech:"))
        self._locale_combo = QComboBox()
        speech_row.addWidget(self._locale_combo, stretch=1)
        root.addLayout(speech_row)

        self._feed = QPlainTextEdit()
        self._feed.setReadOnly(True)
        self._feed.setPlaceholderText("Live transcript and reactions appear here.")
        root.addWidget(self._feed, stretch=1)

        session_box = QGroupBox("Session (transcribe)")
        session_form = QFormLayout(session_box)
        self._session_name = QLineEdit()
        self._session_name.setPlaceholderText("Optional session label")
        session_form.addRow("Session name:", self._session_name)
        root.addWidget(session_box)

        buttons = QHBoxLayout()
        self._start_stop = QPushButton("Start")
        self._export = QPushButton("Open transcripts folder")
        buttons.addWidget(self._start_stop)
        buttons.addWidget(self._export)
        buttons.addStretch(1)
        root.addLayout(buttons)

        self.statusBar().showMessage("Loading models…")

        self._populate_personas()
        self._populate_locale_combo()
        self._wire_mode_from_config()
        self._apply_models_ready(False)

        self._radio_persona.toggled.connect(self._on_mode_ui_toggled)
        self._radio_transcribe.toggled.connect(self._on_mode_ui_toggled)
        self._start_stop.clicked.connect(self._on_start_stop)
        self._export.clicked.connect(self._on_export)
        self._persona_combo.currentTextChanged.connect(self._on_persona_changed)

    def attach_bridge(self, bridge: SignalBridge) -> None:
        """Connect worker-thread callbacks to UI slots (call from GUI thread after construction)."""
        bridge.transcript_received.connect(self._append_transcript)
        bridge.reaction_received.connect(self._append_reaction)
        bridge.status_received.connect(self._on_status)
        bridge.error_received.connect(self._on_error_message)

    def set_models_ready(self, ready: bool) -> None:
        """Enable pipeline controls after ``PipelineController.load_models`` completes."""
        self._models_ready = ready
        self._apply_models_ready(ready)
        if ready:
            self.statusBar().showMessage("Models ready.")

    def _populate_personas(self) -> None:
        names = list_personas(_prompts_root())
        self._persona_combo.blockSignals(True)
        self._persona_combo.clear()
        for n in names:
            self._persona_combo.addItem(n)
        preferred = self._config.persona_name
        idx = self._persona_combo.findText(preferred)
        if idx >= 0:
            self._persona_combo.setCurrentIndex(idx)
        elif self._persona_combo.count() > 0:
            self._persona_combo.setCurrentIndex(0)
        self._persona_combo.blockSignals(False)

    def _populate_locale_combo(self) -> None:
        from heckler.locale import supported_locale_labels

        self._locale_combo.blockSignals(True)
        self._locale_combo.clear()
        self._locale_combo.addItem("From persona")
        for slug in supported_locale_labels():
            self._locale_combo.addItem(slug)
        self._locale_combo.setCurrentIndex(0)
        self._locale_combo.blockSignals(False)

    def selected_locale_override(self) -> str | None:
        text = self._locale_combo.currentText()
        if text == "From persona" or not text:
            return None
        return text

    def selected_persona_name(self) -> str:
        return self._persona_combo.currentText()

    def _wire_mode_from_config(self) -> None:
        mode = (self._config.mode or "persona").strip().lower()
        if mode == "transcribe":
            self._radio_transcribe.setChecked(True)
        else:
            self._radio_persona.setChecked(True)

    def _selected_mode(self) -> str:
        return "transcribe" if self._radio_transcribe.isChecked() else "persona"

    def _apply_models_ready(self, ready: bool) -> None:
        self._radio_persona.setEnabled(ready and not self._controller.is_running)
        self._radio_transcribe.setEnabled(ready and not self._controller.is_running)
        self._session_name.setEnabled(ready and self._selected_mode() == "transcribe")
        self._start_stop.setEnabled(ready)
        persona_mode = self._selected_mode() == "persona"
        self._persona_combo.setEnabled(
            ready and persona_mode and not getattr(self, "_reloading", False)
        )
        self._locale_combo.setEnabled(
            ready and persona_mode and not getattr(self, "_reloading", False)
        )
        self._locale_combo.setVisible(persona_mode)
        self._export.setEnabled(ready and self._selected_mode() == "transcribe")
        self._start_stop.setText("Stop" if self._controller.is_running else "Start")

    def _on_mode_ui_toggled(self, _checked: bool) -> None:
        if not self._radio_persona.isChecked() and not self._radio_transcribe.isChecked():
            return
        self._session_name.setEnabled(self._models_ready and self._selected_mode() == "transcribe")
        self._export.setEnabled(self._models_ready and self._selected_mode() == "transcribe")
        if not self._controller.is_running:
            self._apply_models_ready(self._models_ready)
            return
        new_mode = self._selected_mode()
        try:
            if new_mode == "persona":
                name = self._persona_combo.currentText()
                self._controller.switch_mode("persona", persona_name=name or None)
            else:
                label = self._session_name.text().strip() or None
                self._controller.switch_mode("transcribe", session_name=label)
        except PipelineNotRunningError as e:
            self._show_error(str(e))
        except PersonaNotFoundError as e:
            self._show_error(str(e))
        except ValueError as e:
            self._show_error(str(e))
        except PipelineAlreadyRunningError:
            logger.exception("Unexpected PipelineAlreadyRunningError during mode switch")
            self._show_error("Mode switch failed (pipeline already starting).")
        self._refresh_running_state()

    def _on_start_stop(self) -> None:
        if not self._models_ready:
            self.statusBar().showMessage("Models are not ready yet.")
            return
        if self._controller.is_running:
            try:
                self._controller.stop()
            except Exception:  # pragma: no cover — defensive
                logger.exception("stop() failed")
                self._show_error("Stop failed; see logs.")
            self._refresh_running_state()
            return
        mode = self._selected_mode()
        persona = self._persona_combo.currentText() or None
        session = self._session_name.text().strip() or None
        try:
            if mode == "persona":
                locale_override = self.selected_locale_override()

                def _on_prog(msg: str) -> None:
                    sb = self.statusBar()
                    if sb:
                        sb.showMessage(msg)

                try:
                    self._controller.ensure_heavy_models(
                        persona_name=persona or None,
                        locale_override=locale_override,
                        on_progress=_on_prog,
                        mode="persona",
                    )
                except Exception as e:
                    self._show_error(f"Model load failed: {e}")
                    return
                self._controller.start("persona", persona_name=persona)
            else:
                self._controller.start("transcribe", session_name=session)
        except PipelineAlreadyRunningError as e:
            self._show_error(str(e))
        except PersonaNotFoundError as e:
            self._show_error(str(e))
        except ValueError as e:
            self._show_error(str(e))
        self._refresh_running_state()

    def _on_persona_changed(self, _name: str) -> None:
        name = self._persona_combo.currentText()
        if not name:
            return
        if not self._controller.is_running or self._controller.current_mode != "persona":
            try:
                from heckler.persona import load_persona

                persona = load_persona(_prompts_root() / name)
                locale = persona.config_overrides.get("locale")
                self._locale_combo.blockSignals(True)
                if locale:
                    idx = self._locale_combo.findText(locale)
                    self._locale_combo.setCurrentIndex(idx if idx >= 0 else 0)
                else:
                    self._locale_combo.setCurrentIndex(0)
                self._locale_combo.blockSignals(False)
            except PersonaNotFoundError:
                logger.debug("Could not sync locale combo from persona %r", name)
                self._locale_combo.blockSignals(True)
                self._locale_combo.setCurrentIndex(0)
                self._locale_combo.blockSignals(False)
            return
        try:
            self._controller.swap_persona(name)
        except PipelineNotRunningError as e:
            self._show_error(str(e))
        except PersonaNotFoundError as e:
            self._show_error(str(e))

    def _on_export(self) -> None:
        if self._selected_mode() != "transcribe":
            return
        path = Path(self._config.transcripts_dir).expanduser().resolve()
        path.mkdir(parents=True, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))

    def _append_transcript(self, text: str) -> None:
        self._feed.appendPlainText(text)

    def _append_reaction(self, result: object, was_spoken: bool) -> None:
        if not isinstance(result, ReactorResult):
            self._feed.appendPlainText(f"> (reaction) {result!r} spoken={was_spoken}")
            return
        tag = "spoken" if was_spoken else "not spoken"
        self._feed.appendPlainText(f"> {result.comment!s} ({tag}, score={result.score:.2f})")

    def _on_status(self, message: str) -> None:
        self.statusBar().showMessage(message)

    def _on_error_message(self, message: str) -> None:
        self.statusBar().showMessage(message, 8000)

    def _show_error(self, message: str) -> None:
        self.statusBar().showMessage(message, 8000)
        QMessageBox.warning(self, "Heckler", message)

    def _refresh_running_state(self) -> None:
        self._apply_models_ready(self._models_ready)

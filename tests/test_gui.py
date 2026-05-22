"""GUI tests (pytest-qt).

Headless / CI: ``QT_QPA_PLATFORM=offscreen`` is applied via ``setdefault`` below so
``QApplication`` can run without a display when operators forget to export the var.
"""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import threading
from unittest.mock import MagicMock, patch

import pytest
from PyQt6.QtCore import QUrl
from PyQt6.QtWidgets import QComboBox, QPlainTextEdit, QRadioButton

from heckler.config import HecklerConfig
from heckler.controller import SpeechReloadPolicy
from heckler.gui.app import ModelLoadThread
from heckler.gui.main_window import HecklerMainWindow, SignalBridge
from heckler.locale import SUPPORTED_LOCALES, supported_locale_labels
from heckler.models import CommentType, ReactorResult
from heckler.persona import Persona, PersonaNotFoundError


def _stub_controller(**kwargs) -> MagicMock:
    c = MagicMock()
    c.is_running = False
    c.current_mode = None
    c.current_persona_name = None
    for k, v in kwargs.items():
        setattr(c, k, v)
    return c


def test_main_window_creates(qtbot):
    cfg = HecklerConfig()
    ctrl = _stub_controller()
    w = HecklerMainWindow(cfg, ctrl)
    qtbot.addWidget(w)
    w.set_models_ready(True)
    assert w.windowTitle() == "Heckler"
    assert w.findChild(QComboBox) is not None
    assert w.findChild(QPlainTextEdit) is not None
    radios = w.findChildren(QRadioButton)
    assert len(radios) >= 2


@patch("heckler.gui.main_window.list_personas", return_value=["heckler", "test"])
def test_persona_combo_populated(_mock_list, qtbot):
    cfg = HecklerConfig()
    ctrl = _stub_controller()
    w = HecklerMainWindow(cfg, ctrl)
    qtbot.addWidget(w)
    names = [w._persona_combo.itemText(i) for i in range(w._persona_combo.count())]
    assert names == ["heckler", "test"]


def test_locale_combo_populated(qtbot):
    cfg = HecklerConfig()
    w = HecklerMainWindow(cfg, _stub_controller())
    qtbot.addWidget(w)
    labels = [w._locale_combo.itemText(i) for i in range(w._locale_combo.count())]
    assert labels == ["From persona", *supported_locale_labels()]


def test_selected_locale_override_from_persona(qtbot):
    cfg = HecklerConfig()
    w = HecklerMainWindow(cfg, _stub_controller())
    qtbot.addWidget(w)
    w._locale_combo.setCurrentIndex(0)
    assert w.selected_locale_override() is None


def test_selected_locale_override_explicit(qtbot):
    cfg = HecklerConfig()
    w = HecklerMainWindow(cfg, _stub_controller())
    qtbot.addWidget(w)
    idx = w._locale_combo.findText("es")
    assert idx >= 0
    w._locale_combo.setCurrentIndex(idx)
    assert w.selected_locale_override() == "es"


def test_locale_combo_hidden_in_transcribe_mode(qtbot):
    cfg = HecklerConfig()
    w = HecklerMainWindow(cfg, _stub_controller())
    qtbot.addWidget(w)
    w.set_models_ready(True)
    w._radio_transcribe.setChecked(True)
    w._apply_models_ready(True)
    assert w._locale_combo.isVisible() is False
    assert w._locale_combo.isEnabled() is False


@patch("heckler.gui.main_window.list_personas", return_value=["heckler_arg"])
@patch(
    "heckler.persona.load_persona",
    return_value=Persona(
        name="heckler_arg",
        description="",
        system_prompt="",
        examples=[],
        config_overrides={"locale": "es"},
    ),
)
def test_locale_combo_syncs_from_persona_when_not_running(
    _mock_load, _mock_list, qtbot
):
    cfg = HecklerConfig()
    w = HecklerMainWindow(cfg, _stub_controller())
    qtbot.addWidget(w)
    w._on_persona_changed("heckler_arg")
    assert w._locale_combo.currentText() == "es"


@patch("heckler.gui.main_window.list_personas", return_value=["missing"])
@patch(
    "heckler.persona.load_persona",
    side_effect=PersonaNotFoundError("missing"),
)
def test_locale_combo_defaults_on_persona_not_found(_mock_load, _mock_list, qtbot):
    cfg = HecklerConfig()
    w = HecklerMainWindow(cfg, _stub_controller())
    qtbot.addWidget(w)
    w._locale_combo.setCurrentIndex(w._locale_combo.findText("es"))
    w._on_persona_changed("missing")
    assert w._locale_combo.currentIndex() == 0
    assert w.selected_locale_override() is None


@patch("heckler.gui.main_window.list_personas", return_value=["weird"])
@patch(
    "heckler.persona.load_persona",
    return_value=Persona(
        name="weird",
        description="",
        system_prompt="",
        examples=[],
        config_overrides={"locale": "xx-unknown"},
    ),
)
def test_locale_combo_unknown_persona_locale_resets_to_from_persona(
    _mock_load, _mock_list, qtbot
):
    """Falsifier: TOML locale not in supported_locale_labels() must not leave a stale slug selected."""
    cfg = HecklerConfig()
    w = HecklerMainWindow(cfg, _stub_controller())
    qtbot.addWidget(w)
    w._locale_combo.setCurrentIndex(w._locale_combo.findText("es"))
    w._on_persona_changed("weird")
    assert w._locale_combo.currentIndex() == 0
    assert set(supported_locale_labels()) == set(SUPPORTED_LOCALES.keys())


def test_live_feed_is_read_only(qtbot):
    cfg = HecklerConfig()
    w = HecklerMainWindow(cfg, _stub_controller())
    qtbot.addWidget(w)
    feed = w.findChild(QPlainTextEdit)
    assert feed is not None
    assert feed.isReadOnly() is True


def test_signal_bridge_transcript_updates_feed(qtbot):
    cfg = HecklerConfig()
    w = HecklerMainWindow(cfg, _stub_controller())
    qtbot.addWidget(w)
    bridge = SignalBridge()
    w.attach_bridge(bridge)
    w.set_models_ready(True)
    bridge.transcript_received.emit("hello-feed")
    qtbot.waitUntil(lambda: "hello-feed" in w.findChild(QPlainTextEdit).toPlainText(), timeout=2000)


def test_signal_bridge_status_updates_status_bar(qtbot):
    cfg = HecklerConfig()
    w = HecklerMainWindow(cfg, _stub_controller())
    qtbot.addWidget(w)
    bridge = SignalBridge()
    w.attach_bridge(bridge)
    bridge.status_received.emit("mic-open")
    qtbot.waitUntil(lambda: w.statusBar().currentMessage() == "mic-open", timeout=2000)


def test_signal_bridge_transcript_from_worker_thread(qtbot):
    cfg = HecklerConfig()
    w = HecklerMainWindow(cfg, _stub_controller())
    qtbot.addWidget(w)
    bridge = SignalBridge()
    w.attach_bridge(bridge)
    feed = w.findChild(QPlainTextEdit)

    def worker() -> None:
        bridge.transcript_received.emit("thread-line")

    t = threading.Thread(target=worker)
    t.start()
    qtbot.waitUntil(lambda: "thread-line" in feed.toPlainText(), timeout=5000)
    t.join()


def test_signal_bridge_reaction_appends(qtbot):
    cfg = HecklerConfig()
    w = HecklerMainWindow(cfg, _stub_controller())
    qtbot.addWidget(w)
    bridge = SignalBridge()
    w.attach_bridge(bridge)
    rr = ReactorResult(
        comment="hi",
        score=0.5,
        comment_type=CommentType.SARCASM,
        raw_response="{}",
    )
    bridge.reaction_received.emit(rr, True)
    qtbot.waitUntil(lambda: "hi" in w.findChild(QPlainTextEdit).toPlainText(), timeout=2000)


def test_model_load_thread_invokes_load_models_off_thread(qtbot):
    ctrl = MagicMock()
    call_idents: list[int] = []

    def load_models(on_progress=None, **kwargs):
        call_idents.append(threading.current_thread().ident)
        if on_progress:
            on_progress("step")

    ctrl.load_models.side_effect = load_models
    thread = ModelLoadThread(
        ctrl,
        mode="persona",
        persona_name_fn=lambda: "test-persona",
        locale_override_fn=lambda: None,
    )
    with qtbot.waitSignal(thread.finished_ok, timeout=5000):
        thread.start()
    ctrl.load_models.assert_called_once()
    assert ctrl.load_models.call_args.kwargs["persona_name"] == "test-persona"
    assert ctrl.load_models.call_args.kwargs["locale_override"] is None
    assert ctrl.load_models.call_args.kwargs["mode"] == "persona"
    assert len(call_idents) == 1
    assert call_idents[0] != threading.main_thread().ident


def test_model_load_thread_transcribe_mode_omits_persona_name(qtbot):
    ctrl = MagicMock()
    ctrl.load_models.side_effect = lambda **kwargs: None
    thread = ModelLoadThread(
        ctrl,
        mode="transcribe",
        persona_name_fn=lambda: "heckler",
        locale_override_fn=lambda: "es",
    )
    with qtbot.waitSignal(thread.finished_ok, timeout=5000):
        thread.start()
    assert ctrl.load_models.call_args.kwargs["persona_name"] is None
    assert ctrl.load_models.call_args.kwargs["locale_override"] == "es"
    assert ctrl.load_models.call_args.kwargs["mode"] == "transcribe"


def test_model_load_thread_reads_combo_at_run_time(qtbot):
    """F1: persona_name_fn is invoked in run(), not captured at thread construction."""
    ctrl = MagicMock()
    ctrl.load_models.side_effect = lambda **kwargs: None
    calls: list[str] = []

    def persona_name_fn() -> str:
        calls.append("run")
        return "live-persona"

    thread = ModelLoadThread(
        ctrl,
        mode="persona",
        persona_name_fn=persona_name_fn,
        locale_override_fn=lambda: None,
    )
    assert calls == []
    with qtbot.waitSignal(thread.finished_ok, timeout=5000):
        thread.start()
    assert calls == ["run"]
    assert ctrl.load_models.call_args.kwargs["persona_name"] == "live-persona"


def test_selected_persona_name(qtbot):
    with patch("heckler.gui.main_window.list_personas", return_value=["alpha", "beta"]):
        w = HecklerMainWindow(HecklerConfig(), _stub_controller())
        qtbot.addWidget(w)
        w._persona_combo.setCurrentIndex(1)
        assert w.selected_persona_name() == "beta"


def test_persona_combo_enabled_before_pipeline_start(qtbot):
    """F2: persona combo enabled when models ready and persona mode, pipeline not running."""
    ctrl = _stub_controller(is_running=False)
    w = HecklerMainWindow(HecklerConfig(), ctrl)
    qtbot.addWidget(w)
    w.set_models_ready(True)
    assert w._persona_combo.isEnabled() is True


def test_start_button_apply_then_start_when_no_reload(qtbot):
    """D7/T5: Start in persona mode uses apply path; start() when no async reload."""
    ctrl = _stub_controller(is_running=False)
    ctrl.heavy_models_need_reload.return_value = False
    ctrl.start.side_effect = lambda *a, **k: None
    w = HecklerMainWindow(HecklerConfig(), ctrl)
    qtbot.addWidget(w)
    w.set_models_ready(True)
    w._on_start_stop()
    ctrl.heavy_models_need_reload.assert_called()
    ctrl.start.assert_called_once()
    assert w._reloading is False


@patch("heckler.gui.main_window.list_personas", return_value=["heckler"])
def test_apply_persona_and_speech_same_sig_hot_swap(_mock_list, qtbot):
    ctrl = _stub_controller(is_running=True, current_mode="persona", current_persona_name="heckler")
    ctrl.heavy_models_need_reload.return_value = False
    w = HecklerMainWindow(HecklerConfig(), ctrl)
    qtbot.addWidget(w)
    w.set_models_ready(True)
    w._apply_persona_and_speech(
        "heckler",
        None,
        running=True,
        reload_policy=SpeechReloadPolicy.ask,
        on_progress=lambda m: None,
    )
    ctrl.swap_persona.assert_called_once_with("heckler")
    ctrl.reload_speech_stack_for_persona.assert_not_called()


@patch("heckler.gui.main_window._ReloadThread")
@patch("heckler.gui.main_window.list_personas", return_value=["heckler_arg"])
def test_apply_persona_and_speech_cross_sig_auto_reloads(
    _mock_list, mock_thread_cls, qtbot
):
    mock_thread = MagicMock()
    mock_thread_cls.return_value = mock_thread
    ctrl = _stub_controller(is_running=False)
    ctrl.heavy_models_need_reload.return_value = True
    ctrl.loaded_speech_stack.return_value = ("en", "a")
    target_cfg = HecklerConfig(locale="es", kokoro_lang_code="e", whisper_language="es")
    ctrl.target_speech_config.return_value = target_cfg
    w = HecklerMainWindow(HecklerConfig(), ctrl)
    qtbot.addWidget(w)
    w.set_models_ready(True)
    w._apply_persona_and_speech(
        "heckler_arg",
        None,
        running=False,
        reload_policy=SpeechReloadPolicy.auto,
        on_progress=lambda m: None,
    )
    assert w._reloading is True
    mock_thread.start.assert_called_once()
    ctrl.reload_speech_stack_for_persona.assert_not_called()


@patch("heckler.gui.main_window._ReloadThread")
@patch("heckler.gui.main_window.QMessageBox.question")
@patch("heckler.gui.main_window.list_personas", return_value=["heckler_arg"])
def test_apply_persona_and_speech_ask_confirm_reloads(
    _mock_list, mock_question, mock_thread_cls, qtbot
):
    mock_thread_cls.return_value = MagicMock()
    from PyQt6.QtWidgets import QMessageBox

    mock_question.return_value = QMessageBox.StandardButton.Ok
    ctrl = _stub_controller(is_running=True, current_mode="persona", current_persona_name="heckler")
    ctrl.heavy_models_need_reload.return_value = True
    ctrl.loaded_speech_stack.return_value = ("en", "a")
    ctrl.target_speech_config.return_value = HecklerConfig(
        locale="es", kokoro_lang_code="e", whisper_language="es"
    )
    w = HecklerMainWindow(HecklerConfig(), ctrl)
    qtbot.addWidget(w)
    w.set_models_ready(True)
    w._persona_combo.setCurrentIndex(w._persona_combo.findText("heckler_arg"))
    w._apply_persona_and_speech(
        "heckler_arg",
        None,
        running=True,
        reload_policy=SpeechReloadPolicy.ask,
        on_progress=lambda m: None,
    )
    mock_question.assert_called_once()
    assert w._reloading is True


@patch("heckler.gui.main_window.QMessageBox.question")
@patch("heckler.gui.main_window.list_personas", return_value=["heckler", "heckler_arg"])
def test_apply_persona_and_speech_ask_cancel_reverts(
    _mock_list, mock_question, qtbot
):
    from PyQt6.QtWidgets import QMessageBox

    mock_question.return_value = QMessageBox.StandardButton.Cancel
    ctrl = _stub_controller(is_running=True, current_mode="persona", current_persona_name="heckler")
    ctrl.heavy_models_need_reload.return_value = True
    ctrl.loaded_speech_stack.return_value = ("en", "a")
    ctrl.target_speech_config.return_value = HecklerConfig(locale="en")
    w = HecklerMainWindow(HecklerConfig(), ctrl)
    qtbot.addWidget(w)
    w.set_models_ready(True)
    w._persona_combo.setCurrentIndex(w._persona_combo.findText("heckler"))
    w._locale_combo.setCurrentIndex(0)
    w._mark_stable_selection()
    prev_persona = w._stable_persona_idx
    prev_locale = w._stable_locale_idx
    w._persona_combo.setCurrentIndex(w._persona_combo.findText("heckler_arg"))
    w._apply_persona_and_speech(
        "heckler_arg",
        None,
        running=True,
        reload_policy=SpeechReloadPolicy.ask,
        on_progress=lambda m: None,
    )
    assert w._persona_combo.currentIndex() == prev_persona
    assert w._locale_combo.currentIndex() == prev_locale
    ctrl.swap_persona.assert_not_called()
    ctrl.reload_speech_stack_for_persona.assert_not_called()
    assert w._reloading is False


@patch.object(HecklerMainWindow, "_show_error")
@patch("heckler.gui.main_window.list_personas", return_value=["heckler_arg"])
def test_apply_persona_and_speech_reload_failure_reverts(
    _mock_list, _mock_show_error, qtbot
):
    ctrl = _stub_controller(is_running=True, current_mode="persona")
    ctrl.heavy_models_need_reload.return_value = True
    ctrl.loaded_speech_stack.return_value = ("en", "a")
    ctrl.target_speech_config.return_value = HecklerConfig(locale="es")
    ctrl.reload_speech_stack_for_persona.side_effect = RuntimeError("load boom")
    w = HecklerMainWindow(HecklerConfig(), ctrl)
    qtbot.addWidget(w)
    w.set_models_ready(True)
    w._persona_combo.setCurrentIndex(0)
    w._locale_combo.setCurrentIndex(w._locale_combo.findText("es"))
    saved_persona = 0
    saved_locale = w._locale_combo.currentIndex()
    w._reload_revert_persona_idx = saved_persona
    w._reload_revert_locale_idx = saved_locale
    w._persona_combo.setCurrentIndex(w._persona_combo.count() - 1)
    w._on_reload_done(False, "load boom")
    assert w._persona_combo.currentIndex() == saved_persona
    assert w._locale_combo.currentIndex() == saved_locale
    assert w._reloading is False


@patch.object(HecklerMainWindow, "_show_error")
@patch("heckler.gui.main_window._ReloadThread")
@patch("heckler.gui.main_window.QMessageBox.question")
@patch("heckler.gui.main_window.list_personas", return_value=["heckler"])
def test_reloading_flag_cleared_on_all_paths(
    _mock_list, mock_question, mock_thread_cls, _mock_show_error, qtbot
):
    mock_thread_cls.return_value = MagicMock()
    from PyQt6.QtWidgets import QMessageBox

    ctrl = _stub_controller(is_running=True, current_mode="persona", current_persona_name="heckler")
    ctrl.heavy_models_need_reload.return_value = True
    ctrl.target_speech_config.return_value = HecklerConfig(locale="es")
    w = HecklerMainWindow(HecklerConfig(), ctrl)
    qtbot.addWidget(w)
    w.set_models_ready(True)

    mock_question.return_value = QMessageBox.StandardButton.Cancel
    w._apply_persona_and_speech(
        "heckler",
        "es",
        running=True,
        reload_policy=SpeechReloadPolicy.ask,
        on_progress=lambda m: None,
    )
    assert w._reloading is False

    mock_question.return_value = QMessageBox.StandardButton.Ok
    w._apply_persona_and_speech(
        "heckler",
        "es",
        running=True,
        reload_policy=SpeechReloadPolicy.ask,
        on_progress=lambda m: None,
    )
    assert w._reloading is True
    w._on_reload_done(True, None)
    assert w._reloading is False

    w._apply_persona_and_speech(
        "heckler",
        "es",
        running=True,
        reload_policy=SpeechReloadPolicy.ask,
        on_progress=lambda m: None,
    )
    w._on_reload_done(False, "err")
    assert w._reloading is False


@patch("heckler.gui.main_window.list_personas", return_value=["heckler_arg"])
def test_voice_locale_mismatch_warning_logged(_mock_list, qtbot, caplog):
    import logging

    ctrl = _stub_controller()
    ctrl.heavy_models_need_reload.return_value = False
    ctrl.target_speech_config.return_value = HecklerConfig(
        locale="es",
        kokoro_lang_code="e",
        whisper_language="es",
        kokoro_voice="af_sarah",
    )
    w = HecklerMainWindow(HecklerConfig(), ctrl)
    qtbot.addWidget(w)
    with caplog.at_level(logging.WARNING):
        w._check_voice_locale_warning("heckler_arg", None)
    assert any("af_sarah" in r.message for r in caplog.records)
    assert any("may not be compatible" in r.message for r in caplog.records)


@patch("heckler.gui.main_window.list_personas", return_value=["heckler"])
def test_reload_speech_btn_present(_mock_list, qtbot):
    ctrl = _stub_controller()
    w = HecklerMainWindow(HecklerConfig(), ctrl)
    qtbot.addWidget(w)
    assert w._reload_speech_btn is not None
    assert w._reload_speech_btn.text() == "Reload speech models"
    w.set_models_ready(True)
    with patch.object(w, "_start_reload") as mock_start:
        w._reload_speech_btn.click()
        mock_start.assert_called_once()


@patch("heckler.gui.main_window.QDesktopServices.openUrl")
def test_export_opens_transcripts_dir(mock_open, qtbot):
    cfg = HecklerConfig(transcripts_dir="transcripts_test_gui")
    w = HecklerMainWindow(cfg, _stub_controller())
    qtbot.addWidget(w)
    w.set_models_ready(True)
    w._radio_transcribe.setChecked(True)
    w._on_export()
    mock_open.assert_called_once()
    url = mock_open.call_args[0][0]
    assert isinstance(url, QUrl)
    assert "transcripts_test_gui" in url.toLocalFile()


def test_as_callbacks_emit_signals(qtbot):
    bridge = SignalBridge()
    seen: list[str] = []

    def capture(s: str) -> None:
        seen.append(s)

    bridge.transcript_received.connect(capture)
    cb = bridge.as_callbacks()
    cb.on_transcript("x")
    qtbot.waitUntil(lambda: seen == ["x"], timeout=2000)

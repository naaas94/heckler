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
from heckler.gui.app import ModelLoadThread
from heckler.gui.main_window import HecklerMainWindow, SignalBridge
from heckler.models import CommentType, ReactorResult


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
    combo = w.findChild(QComboBox)
    assert combo is not None
    names = [combo.itemText(i) for i in range(combo.count())]
    assert names == ["heckler", "test"]


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
    cfg = HecklerConfig(persona_name="test-persona", mode="persona")
    ctrl = MagicMock()
    call_idents: list[int] = []

    def load_models(on_progress=None, **kwargs):
        call_idents.append(threading.current_thread().ident)
        if on_progress:
            on_progress("step")

    ctrl.load_models.side_effect = load_models
    thread = ModelLoadThread(ctrl, cfg)
    with qtbot.waitSignal(thread.finished_ok, timeout=5000):
        thread.start()
    ctrl.load_models.assert_called_once()
    assert ctrl.load_models.call_args.kwargs["persona_name"] == "test-persona"
    assert ctrl.load_models.call_args.kwargs["mode"] == "persona"
    assert len(call_idents) == 1
    assert call_idents[0] != threading.main_thread().ident


def test_model_load_thread_transcribe_mode_omits_persona_name(qtbot):
    cfg = HecklerConfig(persona_name="heckler", mode="transcribe")
    ctrl = MagicMock()
    ctrl.load_models.side_effect = lambda **kwargs: None
    thread = ModelLoadThread(ctrl, cfg)
    with qtbot.waitSignal(thread.finished_ok, timeout=5000):
        thread.start()
    assert ctrl.load_models.call_args.kwargs["persona_name"] is None
    assert ctrl.load_models.call_args.kwargs["mode"] == "transcribe"


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

"""HomeGuard — baby/children room monitor."""

from __future__ import annotations

import os
import sys

# Fix SSL certificate path when running as a PyInstaller --onefile EXE.
# Must happen before any import that triggers an HTTPS request.
if getattr(sys, "frozen", False):
    import certifi
    _ca = certifi.where()
    os.environ.setdefault("REQUESTS_CA_BUNDLE", _ca)
    os.environ.setdefault("SSL_CERT_FILE", _ca)

import queue
import threading
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np
import sounddevice as sd
from PyQt5.QtCore import Qt, QTimer, pyqtSignal
from PyQt5.QtGui import QFont, QImage, QPixmap
from PyQt5.QtWidgets import (
    QApplication,
    QComboBox,
    QDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSlider,
    QSpinBox,
    QStatusBar,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

import i18n
from i18n import tr
from config import get_base_dir, load_config, load_telegram_creds, save_config, save_telegram_creds
from gallery import GalleryWidget
from monitor import AudioMonitor, CameraThread, RecordingThread
from telegram_bot import TelegramSender

# ── Sounds ────────────────────────────────────────────────────────────────────

def _play_tone(freq: float, dur: float, vol: float = 0.35) -> None:
    def _run():
        sr = 44100
        t = np.linspace(0, dur, int(sr * dur), endpoint=False)
        wave = np.sin(2 * np.pi * freq * t) * vol
        fade = int(sr * 0.015)
        wave[:fade] *= np.linspace(0, 1, fade)
        wave[-fade:] *= np.linspace(1, 0, fade)
        try:
            sd.play(wave.astype(np.float32), sr)
            sd.wait()
        except Exception:
            pass
    threading.Thread(target=_run, daemon=True).start()


def play_beep() -> None:
    _play_tone(880, 0.12)


def play_armed_sound() -> None:
    def _run():
        for freq in [440, 550, 660, 880]:
            _play_tone(freq, 0.09, 0.4)
            import time; time.sleep(0.09)
    threading.Thread(target=_run, daemon=True).start()


# ── Dark stylesheet ────────────────────────────────────────────────────────────

STYLE = """
QMainWindow, QWidget, QDialog {
    background-color: #1a1b2e;
    color: #dde0f5;
    font-family: 'Segoe UI', Arial, sans-serif;
    font-size: 13px;
}
QGroupBox {
    border: 1px solid #363760;
    border-radius: 8px;
    margin-top: 14px;
    padding-top: 10px;
    color: #8888cc;
    font-weight: bold;
    font-size: 12px;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 5px;
}
QPushButton {
    background-color: #2b2c4a;
    color: #dde0f5;
    border: 1px solid #484980;
    border-radius: 6px;
    padding: 7px 14px;
}
QPushButton:hover { background-color: #3c3d66; border-color: #6668b0; }
QPushButton:pressed { background-color: #1e1f38; }
QPushButton:disabled { color: #555; border-color: #333; }
QSlider::groove:horizontal {
    height: 6px; background: #2b2c4a; border-radius: 3px;
}
QSlider::handle:horizontal {
    background: #7878ee;
    width: 16px; height: 16px;
    border-radius: 8px; margin: -5px 0;
}
QSlider::sub-page:horizontal { background: #5a5ace; border-radius: 3px; }
QProgressBar {
    border: 1px solid #363760;
    border-radius: 4px;
    background: #12131e;
    text-align: center;
    color: #aaa;
    font-size: 11px;
    max-height: 14px;
}
QProgressBar::chunk { border-radius: 3px; background: #3dbb6d; }
QComboBox {
    background: #2b2c4a; border: 1px solid #484980;
    border-radius: 4px; padding: 5px 8px; color: #dde0f5;
}
QComboBox::drop-down { border: none; }
QComboBox QAbstractItemView {
    background: #2b2c4a; color: #dde0f5;
    selection-background-color: #484980;
}
QTabWidget::pane { border: 1px solid #363760; border-radius: 4px; }
QTabBar::tab {
    background: #232440; color: #8888cc;
    padding: 8px 22px;
    border: 1px solid #363760;
    border-bottom: none;
    border-radius: 6px 6px 0 0;
    margin-right: 2px;
}
QTabBar::tab:selected { background: #2d2e50; color: #dde0f5; }
QScrollBar:vertical {
    background: #12131e; width: 10px; border-radius: 5px;
}
QScrollBar::handle:vertical {
    background: #484980; border-radius: 5px; min-height: 20px;
}
QStatusBar { background: #12131e; color: #888; border-top: 1px solid #363760; }
QLineEdit {
    background: #2b2c4a; border: 1px solid #484980;
    border-radius: 4px; padding: 6px 10px; color: #dde0f5;
}
QLineEdit:focus { border-color: #7878ee; }
QSpinBox {
    background: #2b2c4a; border: 1px solid #484980;
    border-radius: 4px; padding: 5px; color: #dde0f5;
}
"""

ARM_STYLE = """
QPushButton {
    background: #0d3d1a; color: #80ffaa;
    border: 2px solid #1a7a30;
    border-radius: 10px; font-size: 17px; font-weight: bold; padding: 14px;
}
QPushButton:hover { background: #1a5c28; border-color: #40cc60; }
"""

DISARM_STYLE = """
QPushButton {
    background: #3d0d0d; color: #ffaaaa;
    border: 2px solid #7a1a1a;
    border-radius: 10px; font-size: 17px; font-weight: bold; padding: 14px;
}
QPushButton:hover { background: #5c1a1a; border-color: #cc4444; }
"""

LANG_STYLE = """
QPushButton {
    background: #1e2040; color: #9090cc;
    border: 1px solid #454580;
    border-radius: 5px; font-size: 12px; padding: 4px 10px;
}
QPushButton:hover { background: #2a2c55; color: #c0c0ff; }
"""

# ── Countdown option keys and values ──────────────────────────────────────────

COUNTDOWN_OPTIONS = [
    ("cd_none", 0),
    ("cd_30s",  30),
    ("cd_1m",   60),
    ("cd_2m",   120),
    ("cd_5m",   300),
]

# ── State constants ────────────────────────────────────────────────────────────

STATE_DISARMED  = "DISARMED"
STATE_COUNTDOWN = "COUNTDOWN"
STATE_ARMED     = "ARMED"
STATE_RECORDING = "RECORDING"


# ── Setup dialog ───────────────────────────────────────────────────────────────

class SetupDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(tr("setup_title"))
        self.setMinimumWidth(500)
        self.setModal(True)
        self._build()

    def _build(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        title = QLabel(tr("setup_welcome"))
        title.setStyleSheet("font-size: 18px; font-weight: bold; color: #8080ff; padding: 8px 0;")
        layout.addWidget(title)

        from config import _TELEGRAM_FILE
        info = QLabel(tr("setup_info", path=_TELEGRAM_FILE))
        info.setTextFormat(Qt.RichText)
        info.setWordWrap(True)
        info.setStyleSheet("color: #aaa; font-size: 12px; background: #12131e; padding: 10px; border-radius: 6px;")
        layout.addWidget(info)

        form = QFormLayout()
        self.token_edit = QLineEdit()
        self.token_edit.setPlaceholderText(tr("setup_token_ph"))
        self.chat_edit = QLineEdit()
        self.chat_edit.setPlaceholderText(tr("setup_chat_ph"))
        form.addRow(tr("setup_token"), self.token_edit)
        form.addRow(tr("setup_chat"),  self.chat_edit)
        layout.addLayout(form)

        existing_token, existing_chat = load_telegram_creds()
        if existing_token:
            self.token_edit.setText(existing_token)
        if existing_chat:
            self.chat_edit.setText(existing_chat)

        self.status_lbl = QLabel("")
        self.status_lbl.setStyleSheet("font-size: 12px; padding: 4px;")
        self.status_lbl.setWordWrap(True)
        layout.addWidget(self.status_lbl)

        btns = QHBoxLayout()
        test_btn = QPushButton(tr("btn_test_conn"))
        test_btn.clicked.connect(self._test)
        self.save_btn = QPushButton(tr("btn_save"))
        self.save_btn.clicked.connect(self._save)
        skip_btn = QPushButton(tr("btn_skip"))
        skip_btn.clicked.connect(self.accept)
        btns.addWidget(test_btn)
        btns.addWidget(self.save_btn)
        btns.addWidget(skip_btn)
        layout.addLayout(btns)

    def _test(self) -> None:
        token = self.token_edit.text().strip()
        chat  = self.chat_edit.text().strip()
        if not token or not chat:
            self.status_lbl.setText(tr("setup_fill_both"))
            self.status_lbl.setStyleSheet("color: #ff6060; font-size: 12px;")
            return
        self.status_lbl.setText(tr("setup_testing"))
        sender = TelegramSender()
        sender.setup(token, chat)
        ok, msg = sender.test_connection()
        if ok:
            self.status_lbl.setText(f"✅ {msg}")
            self.status_lbl.setStyleSheet("color: #60ff90; font-size: 12px;")
        else:
            self.status_lbl.setText(f"❌ {msg}")
            self.status_lbl.setStyleSheet("color: #ff6060; font-size: 12px;")

    def _save(self) -> None:
        token = self.token_edit.text().strip()
        chat  = self.chat_edit.text().strip()
        if not token or not chat:
            self.status_lbl.setText(tr("setup_both_req"))
            self.status_lbl.setStyleSheet("color: #ff6060; font-size: 12px;")
            return
        save_telegram_creds(token, chat)
        self.accept()


# ── Main window ────────────────────────────────────────────────────────────────

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.config = load_config()

        # Apply stored language before building any UI
        i18n.set_lang(self.config.get("language", "en"))
        self._apply_layout_direction()

        self.state = STATE_DISARMED
        self.countdown_remaining = 0
        self._motion_consecutive = 0
        self._alert_cooldown = 0
        self.recorder: RecordingThread | None = None
        self._current_trigger = ""
        self._current_ts = ""
        self._current_path = ""
        self._last_motion_level = 0.0
        self._recording_chunk = 0

        token, chat_id = load_telegram_creds()

        rd = self.config["recordings_dir"]
        if not os.path.isabs(rd):
            rd = os.path.join(get_base_dir(), rd)
        self._recordings_dir = rd
        Path(self._recordings_dir).mkdir(exist_ok=True)

        self._build_ui()
        self.setStyleSheet(STYLE)

        self.telegram = TelegramSender(self)
        if token and chat_id:
            self.telegram.setup(token, chat_id)
        self.telegram.send_complete.connect(
            lambda m: self.statusBar().showMessage(tr("sb_tg_sent", msg=m), 5000)
        )
        self.telegram.send_failed.connect(
            lambda m: self.statusBar().showMessage(tr("sb_tg_fail", msg=m), 8000)
        )
        self.telegram.start()

        self.camera = CameraThread(self.config["camera_index"], self)
        self.camera.frame_ready.connect(self._on_frame)
        self.camera.camera_error.connect(self._on_cam_error)
        self.camera.set_sensitivity(self.config["motion_sensitivity"])
        self.camera.start()

        self.audio = AudioMonitor()
        self.audio.set_threshold(self.config["noise_threshold"])
        self.audio.start()

        self.poll_timer = QTimer(self)
        self.poll_timer.timeout.connect(self._poll)
        self.poll_timer.start(100)

        self.countdown_timer = QTimer(self)
        self.countdown_timer.timeout.connect(self._countdown_tick)

        if not (token and chat_id):
            QTimer.singleShot(200, self._show_setup)

    # ── UI construction ────────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        self.tabs = QTabWidget()
        self.setCentralWidget(self.tabs)

        monitor_tab = QWidget()
        self.tabs.addTab(monitor_tab, tr("tab_monitor"))

        self.gallery = GalleryWidget(self._recordings_dir, self)
        self.tabs.addTab(self.gallery, tr("tab_gallery"))

        outer = QHBoxLayout(monitor_tab)
        outer.setContentsMargins(10, 10, 10, 10)
        outer.setSpacing(12)

        # ── Left: video preview ────────────────────────────────────────────────
        left = QVBoxLayout()
        left.setSpacing(6)

        self.video_label = QLabel(tr("cam_no_signal"))
        self.video_label.setFixedSize(640, 480)
        self.video_label.setAlignment(Qt.AlignCenter)
        self.video_label.setStyleSheet(
            "background: #080810; color: #555; font-size: 16px;"
            " border: 2px solid #363760; border-radius: 6px;"
        )
        left.addWidget(self.video_label)

        cam_row = QHBoxLayout()
        self._lbl_cam_idx = QLabel(tr("lbl_camera_index"))
        cam_row.addWidget(self._lbl_cam_idx)
        self.cam_spin = QSpinBox()
        self.cam_spin.setRange(0, 9)
        self.cam_spin.setValue(self.config["camera_index"])
        self.cam_spin.setFixedWidth(60)
        self.cam_spin.valueChanged.connect(self._change_camera)
        cam_row.addWidget(self.cam_spin)
        cam_row.addStretch()
        left.addLayout(cam_row)
        left.addStretch()
        outer.addLayout(left)

        # ── Right: controls ────────────────────────────────────────────────────
        right = QVBoxLayout()
        right.setSpacing(10)

        # Language toggle (top of panel)
        lang_row = QHBoxLayout()
        lang_row.addStretch()
        self._lang_btn = QPushButton(tr("btn_lang"))
        self._lang_btn.setStyleSheet(LANG_STYLE)
        self._lang_btn.setFixedWidth(82)
        self._lang_btn.clicked.connect(self._toggle_lang)
        lang_row.addWidget(self._lang_btn)
        right.addLayout(lang_row)

        # Status
        self._grp_status = QGroupBox(tr("grp_status"))
        sb_layout = QVBoxLayout(self._grp_status)
        self.status_label = QLabel(tr("state_disarmed"))
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setFont(QFont("Segoe UI", 26, QFont.Bold))
        self.status_label.setStyleSheet("color: #666688;")
        sb_layout.addWidget(self.status_label)
        right.addWidget(self._grp_status)

        # Arm / disarm
        self._grp_arm = QGroupBox(tr("grp_arm"))
        ab_layout = QVBoxLayout(self._grp_arm)
        cd_row = QHBoxLayout()
        self._lbl_delay = QLabel(tr("lbl_delay"))
        cd_row.addWidget(self._lbl_delay)
        self.cd_combo = QComboBox()
        for key, _ in COUNTDOWN_OPTIONS:
            self.cd_combo.addItem(tr(key))
        saved_delay = self.config.get("countdown_delay", 30)
        idx = next((i for i, (_, v) in enumerate(COUNTDOWN_OPTIONS) if v == saved_delay), 1)
        self.cd_combo.setCurrentIndex(idx)
        cd_row.addWidget(self.cd_combo)
        ab_layout.addLayout(cd_row)

        btn_row = QHBoxLayout()
        self.arm_btn = QPushButton(tr("btn_arm"))
        self.arm_btn.setStyleSheet(ARM_STYLE)
        self.arm_btn.clicked.connect(self._arm)
        self.disarm_btn = QPushButton(tr("btn_disarm"))
        self.disarm_btn.setStyleSheet(DISARM_STYLE)
        self.disarm_btn.setEnabled(False)
        self.disarm_btn.clicked.connect(self._disarm)
        btn_row.addWidget(self.arm_btn)
        btn_row.addWidget(self.disarm_btn)
        ab_layout.addLayout(btn_row)
        right.addWidget(self._grp_arm)

        # Sensitivity
        self._grp_sens = QGroupBox(tr("grp_sens"))
        sl_layout = QVBoxLayout(self._grp_sens)
        sl_layout.setSpacing(6)

        self._lbl_motion_sens = QLabel(tr("lbl_motion_sens"))
        sl_layout.addWidget(self._lbl_motion_sens)
        ms_row = QHBoxLayout()
        self.motion_slider = QSlider(Qt.Horizontal)
        self.motion_slider.setRange(1, 10)
        self.motion_slider.setValue(self.config["motion_sensitivity"])
        self.motion_slider.setTickPosition(QSlider.TicksBelow)
        self.motion_slider.setTickInterval(1)
        self.motion_lbl_val = QLabel(str(self.config["motion_sensitivity"]))
        self.motion_lbl_val.setFixedWidth(22)
        self.motion_slider.valueChanged.connect(self._on_motion_sens)
        self._lbl_motion_low  = QLabel(tr("lbl_low"))
        self._lbl_motion_high = QLabel(tr("lbl_high"))
        ms_row.addWidget(self._lbl_motion_low)
        ms_row.addWidget(self.motion_slider)
        ms_row.addWidget(self._lbl_motion_high)
        ms_row.addWidget(self.motion_lbl_val)
        sl_layout.addLayout(ms_row)

        self._lbl_motion_live = QLabel(tr("lbl_motion_live"))
        sl_layout.addWidget(self._lbl_motion_live)
        self.motion_bar = QProgressBar()
        self.motion_bar.setRange(0, 100)
        self.motion_bar.setFormat("%v%")
        sl_layout.addWidget(self.motion_bar)

        sl_layout.addSpacing(4)
        self._lbl_noise_thresh = QLabel(tr("lbl_noise_thresh"))
        sl_layout.addWidget(self._lbl_noise_thresh)
        ns_row = QHBoxLayout()
        self.noise_slider = QSlider(Qt.Horizontal)
        self.noise_slider.setRange(1, 100)
        self.noise_slider.setValue(self.config["noise_threshold"])
        self.noise_lbl_val = QLabel(str(self.config["noise_threshold"]))
        self.noise_lbl_val.setFixedWidth(28)
        self.noise_slider.valueChanged.connect(self._on_noise_thresh)
        self._lbl_noise_low  = QLabel(tr("lbl_low"))
        self._lbl_noise_high = QLabel(tr("lbl_high"))
        ns_row.addWidget(self._lbl_noise_low)
        ns_row.addWidget(self.noise_slider)
        ns_row.addWidget(self._lbl_noise_high)
        ns_row.addWidget(self.noise_lbl_val)
        sl_layout.addLayout(ns_row)

        self._lbl_noise_live = QLabel(tr("lbl_noise_live"))
        sl_layout.addWidget(self._lbl_noise_live)
        self.noise_bar = QProgressBar()
        self.noise_bar.setRange(0, 100)
        self.noise_bar.setFormat("%v%")
        sl_layout.addWidget(self.noise_bar)
        right.addWidget(self._grp_sens)

        # Recording settings
        self._grp_rec = QGroupBox("Recording" if i18n.get_lang() == "en" else "הקלטה")
        rec_layout = QFormLayout(self._grp_rec)
        rec_layout.setSpacing(6)

        self._spin_clip = QSpinBox()
        self._spin_clip.setRange(5, 120)
        self._spin_clip.setSuffix(" s")
        self._spin_clip.setValue(self.config.get("clip_duration", 15))
        self._spin_clip.valueChanged.connect(self._on_clip_dur)
        self._lbl_clip = QLabel("Clip duration:" if i18n.get_lang() == "en" else ":אורך קטע")
        rec_layout.addRow(self._lbl_clip, self._spin_clip)

        self._spin_prebuf = QSpinBox()
        self._spin_prebuf.setRange(0, 30)
        self._spin_prebuf.setSuffix(" s")
        self._spin_prebuf.setValue(self.config.get("pre_buffer_secs", 5))
        self._spin_prebuf.valueChanged.connect(self._on_prebuf)
        self._lbl_prebuf = QLabel("Pre-buffer:" if i18n.get_lang() == "en" else ":באפר מקדים")
        rec_layout.addRow(self._lbl_prebuf, self._spin_prebuf)
        right.addWidget(self._grp_rec)

        # Telegram
        self._grp_tg = QGroupBox(tr("grp_telegram"))
        tg_layout = QVBoxLayout(self._grp_tg)
        self.tg_test_btn = QPushButton(tr("btn_test_tg"))
        self.tg_test_btn.clicked.connect(self._test_telegram)
        self._tg_creds_btn = QPushButton(tr("btn_creds"))
        self._tg_creds_btn.clicked.connect(self._show_setup)
        tg_layout.addWidget(self.tg_test_btn)
        tg_layout.addWidget(self._tg_creds_btn)
        right.addWidget(self._grp_tg)

        right.addStretch()
        outer.addLayout(right)

        self.setStatusBar(QStatusBar())
        self._update_window_title()
        self.statusBar().showMessage(tr("sb_ready"))

    # ── Language ───────────────────────────────────────────────────────────────

    def _toggle_lang(self) -> None:
        new_lang = "he" if i18n.get_lang() == "en" else "en"
        i18n.set_lang(new_lang)
        self.config["language"] = new_lang
        save_config(self.config)
        self._apply_layout_direction()
        self._retranslate_ui()

    def _apply_layout_direction(self) -> None:
        direction = Qt.RightToLeft if i18n.is_rtl() else Qt.LeftToRight
        QApplication.instance().setLayoutDirection(direction)

    def _update_window_title(self) -> None:
        self.setWindowTitle(tr("window_title"))

    def _retranslate_ui(self) -> None:
        """Update every stored widget text to the current language."""
        self._update_window_title()

        # Tabs
        self.tabs.setTabText(0, tr("tab_monitor"))
        self.tabs.setTabText(1, tr("tab_gallery"))

        # Status group
        self._grp_status.setTitle(tr("grp_status"))
        self._update_status()

        # Arm group
        self._grp_arm.setTitle(tr("grp_arm"))
        self._lbl_delay.setText(tr("lbl_delay"))
        self.arm_btn.setText(tr("btn_arm"))
        self.disarm_btn.setText(tr("btn_disarm"))

        # Repopulate countdown combo preserving current value
        cur_val = COUNTDOWN_OPTIONS[self.cd_combo.currentIndex()][1]
        self.cd_combo.blockSignals(True)
        self.cd_combo.clear()
        for key, _ in COUNTDOWN_OPTIONS:
            self.cd_combo.addItem(tr(key))
        idx = next((i for i, (_, v) in enumerate(COUNTDOWN_OPTIONS) if v == cur_val), 1)
        self.cd_combo.setCurrentIndex(idx)
        self.cd_combo.blockSignals(False)

        # Sensitivity group
        self._grp_sens.setTitle(tr("grp_sens"))
        self._lbl_motion_sens.setText(tr("lbl_motion_sens"))
        self._lbl_motion_live.setText(tr("lbl_motion_live"))
        self._lbl_motion_low.setText(tr("lbl_low"))
        self._lbl_motion_high.setText(tr("lbl_high"))
        self._lbl_noise_thresh.setText(tr("lbl_noise_thresh"))
        self._lbl_noise_live.setText(tr("lbl_noise_live"))
        self._lbl_noise_low.setText(tr("lbl_low"))
        self._lbl_noise_high.setText(tr("lbl_high"))

        # Recording group
        is_en = i18n.get_lang() == "en"
        self._grp_rec.setTitle("Recording" if is_en else "הקלטה")
        self._lbl_clip.setText("Clip duration:" if is_en else ":אורך קטע")
        self._lbl_prebuf.setText("Pre-buffer:" if is_en else ":באפר מקדים")

        # Telegram group
        self._grp_tg.setTitle(tr("grp_telegram"))
        self.tg_test_btn.setText(tr("btn_test_tg"))
        self._tg_creds_btn.setText(tr("btn_creds"))

        # Camera row + misc
        self._lbl_cam_idx.setText(tr("lbl_camera_index"))
        self._lang_btn.setText(tr("btn_lang"))

        # Gallery
        self.gallery.retranslate()

        # Status bar
        self.statusBar().showMessage(tr("sb_ready"))

    # ── State machine ──────────────────────────────────────────────────────────

    def _arm(self) -> None:
        delay = COUNTDOWN_OPTIONS[self.cd_combo.currentIndex()][1]
        self.config["countdown_delay"] = delay
        save_config(self.config)
        if delay > 0:
            self.state = STATE_COUNTDOWN
            self.countdown_remaining = delay
            self._update_status()
            self.countdown_timer.start(1000)
        else:
            self._go_armed()
        self.arm_btn.setEnabled(False)
        self.disarm_btn.setEnabled(True)

    def _disarm(self) -> None:
        self.countdown_timer.stop()
        self.state = STATE_DISARMED
        self._recording_chunk = 0
        self._update_status()
        self.arm_btn.setEnabled(True)
        self.disarm_btn.setEnabled(False)
        self.statusBar().showMessage(tr("sb_disarmed"), 3000)

    def _countdown_tick(self) -> None:
        play_beep()
        self.countdown_remaining -= 1
        self._update_status()
        if self.countdown_remaining <= 0:
            self.countdown_timer.stop()
            self._go_armed()

    def _go_armed(self) -> None:
        self.state = STATE_ARMED
        self._motion_consecutive = 0
        self._alert_cooldown = 0
        self._update_status()
        play_armed_sound()
        self.statusBar().showMessage(tr("sb_armed"), 4000)

    def _trigger_alert(self, trigger: str) -> None:
        """Start the FIRST recording chunk for a new alert event (with pre-buffer)."""
        if self.state != STATE_ARMED:
            return
        self._recording_chunk = 1
        self.state = STATE_RECORDING
        self._alert_cooldown = 150
        self._update_status()

        ts    = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        fname = datetime.now().strftime(f"%Y-%m-%d_%H-%M-%S_{trigger}.mp4")
        out   = os.path.join(self._recordings_dir, fname)

        self._current_trigger = trigger
        self._current_ts   = ts
        self._current_path = out

        dur  = self.config.get("clip_duration", 15)
        fps  = self.camera.actual_fps or 20.0
        size = self.camera.actual_size or (640, 480)
        pre_secs = self.config.get("pre_buffer_secs", 5)

        prebuffer = self.camera.snapshot_prebuffer(pre_secs)
        self.audio.stop()

        self.recorder = RecordingThread(self.camera, out, dur, fps, size, prebuffer, self)
        self.recorder.recording_complete.connect(self._on_rec_done)
        self.recorder.recording_failed.connect(self._on_rec_fail)
        self.recorder.start()

        trigger_name = tr(f"trigger_{trigger}")
        self.statusBar().showMessage(tr("sb_rec_1", type=trigger_name))

    def _continue_recording(self) -> None:
        """Start the next chunk because motion is still active."""
        self._recording_chunk += 1
        self.state = STATE_RECORDING
        self._update_status()

        ts      = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        chunk_n = self._recording_chunk
        fname   = datetime.now().strftime(
            f"%Y-%m-%d_%H-%M-%S_{self._current_trigger}_chunk{chunk_n}.mp4"
        )
        out = os.path.join(self._recordings_dir, fname)
        self._current_ts   = ts
        self._current_path = out

        dur  = self.config.get("clip_duration", 15)
        fps  = self.camera.actual_fps or 20.0
        size = self.camera.actual_size or (640, 480)

        self.audio.stop()
        old_recorder = self.recorder
        self.recorder = RecordingThread(self.camera, out, dur, fps, size, [], self)
        self.recorder.recording_complete.connect(self._on_rec_done)
        self.recorder.recording_failed.connect(self._on_rec_fail)
        self.recorder.start()
        if old_recorder is not None:
            old_recorder.deleteLater()

        self.statusBar().showMessage(tr("sb_rec_n", n=str(chunk_n)))

    def _on_rec_done(self, path: str) -> None:
        should_continue = (
            self.state == STATE_RECORDING and
            self._last_motion_level > self._motion_alert_threshold()
        )
        if not should_continue:
            self.audio.start()

        if self.telegram.is_configured():
            self.telegram.send_alert(
                self._current_trigger, self._current_ts, path,
                chunk=self._recording_chunk,
            )
        else:
            self.statusBar().showMessage(
                tr("sb_saved_no_tg", name=Path(path).name), 6000
            )

        if self.tabs.currentIndex() == 1:
            self.gallery.refresh()

        if should_continue:
            self._continue_recording()
        else:
            if self.state == STATE_RECORDING:
                self.state = STATE_ARMED
                self._update_status()

    def _on_rec_fail(self, error: str) -> None:
        self.audio.start()
        if self.state == STATE_RECORDING:
            self.state = STATE_ARMED
            self._update_status()
        self.statusBar().showMessage(tr("sb_rec_fail", err=error), 8000)

    # ── Slots ──────────────────────────────────────────────────────────────────

    def _on_frame(self, frame: np.ndarray, motion_level: float) -> None:
        self._last_motion_level = motion_level
        display = frame.copy()

        if self.state == STATE_COUNTDOWN:
            overlay = np.zeros_like(display)
            overlay[:] = (20, 20, 80)
            cv2.addWeighted(overlay, 0.3, display, 0.7, 0, display)
            cv2.putText(
                display, str(self.countdown_remaining),
                (display.shape[1] // 2 - 45, display.shape[0] // 2 + 30),
                cv2.FONT_HERSHEY_SIMPLEX, 3.5, (255, 200, 50), 5,
            )
            cv2.putText(
                display, tr("cam_overlay_arming"),
                (display.shape[1] // 2 - 80, display.shape[0] // 2 - 50),
                cv2.FONT_HERSHEY_SIMPLEX, 0.9, (255, 200, 50), 2,
            )

        elif self.state == STATE_RECORDING:
            cv2.circle(display, (22, 22), 10, (0, 0, 255), -1)
            cv2.putText(display, tr("cam_overlay_rec"), (38, 30),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.75, (0, 0, 255), 2)

        elif self.state == STATE_ARMED:
            cv2.putText(display, tr("cam_overlay_armed"), (8, 24),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.65, (50, 220, 80), 2)

        rgb = cv2.cvtColor(display, cv2.COLOR_BGR2RGB)
        h, w, _ = rgb.shape
        qimg = QImage(rgb.data, w, h, w * 3, QImage.Format_RGB888)
        pixmap = QPixmap.fromImage(qimg).scaled(
            self.video_label.width(), self.video_label.height(),
            Qt.KeepAspectRatio, Qt.SmoothTransformation,
        )
        self.video_label.setPixmap(pixmap)

        bar_val = int(motion_level * 100)
        self.motion_bar.setValue(min(bar_val, 100))
        chunk_color = "#ff4444" if motion_level > self._motion_alert_threshold() else "#3dbb6d"
        self.motion_bar.setStyleSheet(
            f"QProgressBar::chunk {{ border-radius: 3px; background: {chunk_color}; }}"
        )

        if self.state == STATE_ARMED and self._alert_cooldown <= 0:
            if motion_level > self._motion_alert_threshold():
                self._motion_consecutive += 1
                if self._motion_consecutive >= 3:
                    self._motion_consecutive = 0
                    self._trigger_alert("motion")
            else:
                self._motion_consecutive = 0

    def _poll(self) -> None:
        if self._alert_cooldown > 0:
            self._alert_cooldown -= 1

        level = self.audio.get_level()
        noise_pct = min(int(level / 0.5 * 100), 100)
        self.noise_bar.setValue(noise_pct)
        thresh = self.audio.get_threshold()
        chunk_color = "#ff4444" if level > thresh else "#3dbb6d"
        self.noise_bar.setStyleSheet(
            f"QProgressBar::chunk {{ border-radius: 3px; background: {chunk_color}; }}"
        )

        if self.state == STATE_ARMED and self._alert_cooldown <= 0:
            got_noise = False
            try:
                while True:
                    self.audio.noise_queue.get_nowait()
                    got_noise = True
            except queue.Empty:
                pass
            if got_noise:
                self._trigger_alert("noise")

    def _motion_alert_threshold(self) -> float:
        sens = self.config["motion_sensitivity"]
        return max(0.005, 0.15 - sens * 0.013)

    def _on_cam_error(self, msg: str) -> None:
        self.video_label.setText(tr("cam_err_prefix") + msg)
        self.statusBar().showMessage(msg, 0)

    def _on_motion_sens(self, val: int) -> None:
        self.motion_lbl_val.setText(str(val))
        self.config["motion_sensitivity"] = val
        self.camera.set_sensitivity(val)
        save_config(self.config)

    def _on_noise_thresh(self, val: int) -> None:
        self.noise_lbl_val.setText(str(val))
        self.config["noise_threshold"] = val
        self.audio.set_threshold(val)
        save_config(self.config)

    def _on_clip_dur(self, val: int) -> None:
        self.config["clip_duration"] = val
        save_config(self.config)

    def _on_prebuf(self, val: int) -> None:
        self.config["pre_buffer_secs"] = val
        save_config(self.config)

    def _change_camera(self, idx: int) -> None:
        self.config["camera_index"] = idx
        save_config(self.config)
        self.camera.stop()
        self.camera = CameraThread(idx, self)
        self.camera.frame_ready.connect(self._on_frame)
        self.camera.camera_error.connect(self._on_cam_error)
        self.camera.set_sensitivity(self.config["motion_sensitivity"])
        self.camera.start()

    def _update_status(self) -> None:
        styles = {
            STATE_DISARMED:  (tr("state_disarmed"), "#666688", "26px"),
            STATE_ARMED:     (tr("state_armed"),    "#30dd60", "26px"),
            STATE_RECORDING: (tr("state_rec"),      "#ff4444", "26px"),
        }
        if self.state == STATE_COUNTDOWN:
            unit = tr("state_cd_unit")
            self.status_label.setText(f"{tr('state_countdown')}\n{self.countdown_remaining}{unit}")
            self.status_label.setStyleSheet("color: #ffaa30; font-size: 22px; font-weight: bold;")
        else:
            text, color, size = styles.get(self.state, (self.state, "#888", "26px"))
            self.status_label.setText(text)
            self.status_label.setStyleSheet(
                f"color: {color}; font-size: {size}; font-weight: bold;"
            )

    def _show_setup(self) -> None:
        dlg = SetupDialog(self)
        if dlg.exec_() == QDialog.Accepted:
            token, chat_id = load_telegram_creds()
            if token and chat_id:
                self.telegram.setup(token, chat_id)
                self.statusBar().showMessage(tr("setup_updated"), 4000)

    def _test_telegram(self) -> None:
        if not self.telegram.is_configured():
            QMessageBox.warning(self, tr("tg_not_cfg_title"), tr("tg_not_cfg_msg"))
            return
        self.tg_test_btn.setEnabled(False)
        self.tg_test_btn.setText(tr("setup_testing"))
        ok, msg = self.telegram.test_connection()
        self.tg_test_btn.setEnabled(True)
        self.tg_test_btn.setText(tr("btn_test_tg"))
        if ok:
            QMessageBox.information(self, tr("tg_ok_title"), msg)
        else:
            QMessageBox.critical(self, tr("tg_err_title"), msg)

    # ── Lifecycle ──────────────────────────────────────────────────────────────

    def closeEvent(self, event) -> None:
        self.poll_timer.stop()
        self.countdown_timer.stop()
        self.camera.stop()
        self.audio.stop()
        self.telegram.stop()
        save_config(self.config)
        event.accept()


# ── Entry point ────────────────────────────────────────────────────────────────

def main() -> None:
    # Must be set before QApplication is created so Qt respects the OS display scale factor
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
    app = QApplication(sys.argv)
    app.setApplicationName("HomeGuard")
    app.setStyle("Fusion")
    win = MainWindow()
    win.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()

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

# ── Setup dialog ───────────────────────────────────────────────────────────────

class SetupDialog(QDialog):
    """First-run dialog to configure Telegram credentials.

    Credentials are saved to telegram.txt next to the EXE.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("HomeGuard — Telegram Setup")
        self.setMinimumWidth(500)
        self.setModal(True)
        self._build()

    def _build(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        title = QLabel("🏠 Welcome to HomeGuard")
        title.setStyleSheet("font-size: 18px; font-weight: bold; color: #8080ff; padding: 8px 0;")
        layout.addWidget(title)

        from config import _TELEGRAM_FILE  # show the user exactly where the file is saved
        info = QLabel(
            "To receive alerts on your phone you need a Telegram bot.\n\n"
            "1. Open Telegram → search <b>@BotFather</b> → /newbot\n"
            "2. Copy the <b>Bot Token</b> it gives you.\n"
            "3. Send any message to your new bot.\n"
            "4. Visit: <tt>https://api.telegram.org/bot&lt;TOKEN&gt;/getUpdates</tt>\n"
            f"   Find <tt>\"chat\":{{\"id\":YOUR_ID}}</tt> — copy that number.\n\n"
            f"Credentials will be saved to:\n<tt>{_TELEGRAM_FILE}</tt>"
        )
        info.setTextFormat(Qt.RichText)
        info.setWordWrap(True)
        info.setStyleSheet("color: #aaa; font-size: 12px; background: #12131e; padding: 10px; border-radius: 6px;")
        layout.addWidget(info)

        form = QFormLayout()
        self.token_edit = QLineEdit()
        self.token_edit.setPlaceholderText("1234567890:ABCdef...")
        self.chat_edit = QLineEdit()
        self.chat_edit.setPlaceholderText("123456789")
        form.addRow("Bot Token:", self.token_edit)
        form.addRow("Chat ID:", self.chat_edit)
        layout.addLayout(form)

        # Pre-fill if credentials already exist
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
        test_btn = QPushButton("🔗 Test Connection")
        test_btn.clicked.connect(self._test)
        self.save_btn = QPushButton("✅ Save & Continue")
        self.save_btn.clicked.connect(self._save)
        skip_btn = QPushButton("Skip (no Telegram)")
        skip_btn.clicked.connect(self.accept)
        btns.addWidget(test_btn)
        btns.addWidget(self.save_btn)
        btns.addWidget(skip_btn)
        layout.addLayout(btns)

    def _test(self) -> None:
        token = self.token_edit.text().strip()
        chat = self.chat_edit.text().strip()
        if not token or not chat:
            self.status_lbl.setText("❌ Fill in both fields first.")
            self.status_lbl.setStyleSheet("color: #ff6060; font-size: 12px;")
            return
        self.status_lbl.setText("Testing…")
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
        chat = self.chat_edit.text().strip()
        if not token or not chat:
            self.status_lbl.setText("❌ Both fields are required.")
            self.status_lbl.setStyleSheet("color: #ff6060; font-size: 12px;")
            return
        save_telegram_creds(token, chat)
        self.accept()


# ── Main window ────────────────────────────────────────────────────────────────

COUNTDOWN_OPTIONS = [("No delay", 0), ("30 seconds", 30), ("1 minute", 60),
                     ("2 minutes", 120), ("5 minutes", 300)]

STATE_DISARMED  = "DISARMED"
STATE_COUNTDOWN = "COUNTDOWN"
STATE_ARMED     = "ARMED"
STATE_RECORDING = "RECORDING"

STATE_STYLES = {
    STATE_DISARMED:  ("DISARMED",   "#666688"),
    STATE_ARMED:     ("● ARMED",    "#30dd60"),
    STATE_RECORDING: ("⬤ REC",     "#ff4444"),
}


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("HomeGuard — Room Monitor")
        self.setMinimumSize(1100, 680)
        self.config = load_config()
        self.state = STATE_DISARMED
        self.countdown_remaining = 0
        self._motion_consecutive = 0
        self._alert_cooldown = 0       # ticks of 100 ms
        self.recorder: RecordingThread | None = None
        self._current_trigger = ""
        self._current_ts = ""
        self._current_path = ""
        self._last_motion_level = 0.0   # updated every frame (even during recording)
        self._recording_chunk = 0       # 1 for first clip, 2+ for continuations

        token, chat_id = load_telegram_creds()

        # Always resolve recordings dir relative to the EXE / script location
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
            lambda m: self.statusBar().showMessage(f"📤 {m}", 5000)
        )
        self.telegram.send_failed.connect(
            lambda m: self.statusBar().showMessage(f"❌ {m}", 8000)
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
        self.tabs.addTab(monitor_tab, "🏠  Monitor")

        self.gallery = GalleryWidget(self._recordings_dir, self)
        self.tabs.addTab(self.gallery, "📹  Gallery")

        outer = QHBoxLayout(monitor_tab)
        outer.setContentsMargins(10, 10, 10, 10)
        outer.setSpacing(12)

        # ── Left: video preview ────────────────────────────────────────────────
        left = QVBoxLayout()
        left.setSpacing(6)

        self.video_label = QLabel("No camera signal")
        self.video_label.setFixedSize(640, 480)
        self.video_label.setAlignment(Qt.AlignCenter)
        self.video_label.setStyleSheet(
            "background: #080810; color: #555; font-size: 16px;"
            " border: 2px solid #363760; border-radius: 6px;"
        )
        left.addWidget(self.video_label)

        cam_row = QHBoxLayout()
        cam_row.addWidget(QLabel("Camera index:"))
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

        # Status
        status_box = QGroupBox("Status")
        sb_layout = QVBoxLayout(status_box)
        self.status_label = QLabel("DISARMED")
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setFont(QFont("Segoe UI", 26, QFont.Bold))
        self.status_label.setStyleSheet("color: #666688;")
        sb_layout.addWidget(self.status_label)
        right.addWidget(status_box)

        # Arm / disarm
        arm_box = QGroupBox("Arm / Disarm")
        ab_layout = QVBoxLayout(arm_box)
        cd_row = QHBoxLayout()
        cd_row.addWidget(QLabel("Delay:"))
        self.cd_combo = QComboBox()
        for label, _ in COUNTDOWN_OPTIONS:
            self.cd_combo.addItem(label)
        idx = next(
            (i for i, (_, v) in enumerate(COUNTDOWN_OPTIONS)
             if v == self.config.get("countdown_delay", 30)),
            1,
        )
        self.cd_combo.setCurrentIndex(idx)
        cd_row.addWidget(self.cd_combo)
        ab_layout.addLayout(cd_row)

        btn_row = QHBoxLayout()
        self.arm_btn = QPushButton("🟢  ARM")
        self.arm_btn.setStyleSheet(ARM_STYLE)
        self.arm_btn.clicked.connect(self._arm)
        self.disarm_btn = QPushButton("🔴  DISARM")
        self.disarm_btn.setStyleSheet(DISARM_STYLE)
        self.disarm_btn.setEnabled(False)
        self.disarm_btn.clicked.connect(self._disarm)
        btn_row.addWidget(self.arm_btn)
        btn_row.addWidget(self.disarm_btn)
        ab_layout.addLayout(btn_row)
        right.addWidget(arm_box)

        # Sensitivity
        sens_box = QGroupBox("Detection Sensitivity")
        sl_layout = QVBoxLayout(sens_box)
        sl_layout.setSpacing(6)

        sl_layout.addWidget(QLabel("Motion sensitivity:"))
        ms_row = QHBoxLayout()
        self.motion_slider = QSlider(Qt.Horizontal)
        self.motion_slider.setRange(1, 10)
        self.motion_slider.setValue(self.config["motion_sensitivity"])
        self.motion_slider.setTickPosition(QSlider.TicksBelow)
        self.motion_slider.setTickInterval(1)
        self.motion_lbl_val = QLabel(str(self.config["motion_sensitivity"]))
        self.motion_lbl_val.setFixedWidth(22)
        self.motion_slider.valueChanged.connect(self._on_motion_sens)
        ms_row.addWidget(QLabel("Low"))
        ms_row.addWidget(self.motion_slider)
        ms_row.addWidget(QLabel("High"))
        ms_row.addWidget(self.motion_lbl_val)
        sl_layout.addLayout(ms_row)
        sl_layout.addWidget(QLabel("Live motion level:"))
        self.motion_bar = QProgressBar()
        self.motion_bar.setRange(0, 100)
        self.motion_bar.setFormat("%v%")
        sl_layout.addWidget(self.motion_bar)

        sl_layout.addSpacing(4)
        sl_layout.addWidget(QLabel("Noise threshold:"))
        ns_row = QHBoxLayout()
        self.noise_slider = QSlider(Qt.Horizontal)
        self.noise_slider.setRange(1, 100)
        self.noise_slider.setValue(self.config["noise_threshold"])
        self.noise_lbl_val = QLabel(str(self.config["noise_threshold"]))
        self.noise_lbl_val.setFixedWidth(28)
        self.noise_slider.valueChanged.connect(self._on_noise_thresh)
        ns_row.addWidget(QLabel("Low"))
        ns_row.addWidget(self.noise_slider)
        ns_row.addWidget(QLabel("High"))
        ns_row.addWidget(self.noise_lbl_val)
        sl_layout.addLayout(ns_row)
        sl_layout.addWidget(QLabel("Live noise level:"))
        self.noise_bar = QProgressBar()
        self.noise_bar.setRange(0, 100)
        self.noise_bar.setFormat("%v%")
        sl_layout.addWidget(self.noise_bar)
        right.addWidget(sens_box)

        # Settings / Telegram
        tg_box = QGroupBox("Telegram")
        tg_layout = QVBoxLayout(tg_box)
        self.tg_test_btn = QPushButton("📡  Test Telegram Connection")
        self.tg_test_btn.clicked.connect(self._test_telegram)
        setup_btn = QPushButton("⚙️  Change Credentials")
        setup_btn.clicked.connect(self._show_setup)
        tg_layout.addWidget(self.tg_test_btn)
        tg_layout.addWidget(setup_btn)
        right.addWidget(tg_box)

        right.addStretch()
        outer.addLayout(right)

        self.setStatusBar(QStatusBar())
        self.statusBar().showMessage("HomeGuard ready.")

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
        self.statusBar().showMessage("Disarmed.", 3000)

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
        self.statusBar().showMessage("Armed — monitoring active.", 4000)

    def _trigger_alert(self, trigger: str) -> None:
        """Start the FIRST recording chunk for a new alert event (with 10 s pre-buffer)."""
        if self.state != STATE_ARMED:
            return
        self._recording_chunk = 1
        self.state = STATE_RECORDING
        self._alert_cooldown = 150    # 15 s at 100 ms ticks
        self._update_status()

        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        fname = datetime.now().strftime(f"%Y-%m-%d_%H-%M-%S_{trigger}.mp4")
        out = os.path.join(self._recordings_dir, fname)

        self._current_trigger = trigger
        self._current_ts = ts
        self._current_path = out

        dur = self.config["clip_duration"]
        fps = self.camera.actual_fps or 20.0
        size = self.camera.actual_size or (640, 480)

        # Snapshot the pre-event frame buffer (last ~10 s) BEFORE stopping audio.
        prebuffer = self.camera.snapshot_prebuffer()

        # Stop the microphone monitor BEFORE starting RecordingThread.
        # Both would otherwise open simultaneous PortAudio input streams on the
        # same device, which crashes the audio driver on many Windows systems.
        self.audio.stop()

        self.recorder = RecordingThread(self.camera, out, dur, fps, size, prebuffer, self)
        self.recorder.recording_complete.connect(self._on_rec_done)
        self.recorder.recording_failed.connect(self._on_rec_fail)
        self.recorder.start()

        self.statusBar().showMessage(f"⚠️  {trigger.upper()} detected — recording chunk 1…")

    def _continue_recording(self) -> None:
        """Start the next 15 s chunk because motion is still active in frame."""
        self._recording_chunk += 1
        self.state = STATE_RECORDING
        self._update_status()

        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        chunk_n = self._recording_chunk
        fname = datetime.now().strftime(
            f"%Y-%m-%d_%H-%M-%S_{self._current_trigger}_chunk{chunk_n}.mp4"
        )
        out = os.path.join(self._recordings_dir, fname)
        self._current_ts = ts
        self._current_path = out

        dur = self.config["clip_duration"]
        fps = self.camera.actual_fps or 20.0
        size = self.camera.actual_size or (640, 480)

        # No pre-buffer for continuation chunks (we are already recording continuously)
        self.audio.stop()
        old_recorder = self.recorder
        self.recorder = RecordingThread(self.camera, out, dur, fps, size, [], self)
        self.recorder.recording_complete.connect(self._on_rec_done)
        self.recorder.recording_failed.connect(self._on_rec_fail)
        self.recorder.start()
        # Defer deletion of the previous thread so Qt can finish its signal dispatch
        if old_recorder is not None:
            old_recorder.deleteLater()

        self.statusBar().showMessage(
            f"⚠️  Motion still active — recording chunk {chunk_n}…"
        )

    def _on_rec_done(self, path: str) -> None:
        # Decide BEFORE touching audio whether we should keep recording.
        # This prevents the start→stop audio cycle when continuing.
        should_continue = (
            self.state == STATE_RECORDING and
            self._last_motion_level > self._motion_alert_threshold()
        )

        if not should_continue:
            self.audio.start()   # restart mic only when we're done with the event

        if self.telegram.is_configured():
            self.telegram.send_alert(
                self._current_trigger, self._current_ts, path,
                chunk=self._recording_chunk,
            )
        else:
            self.statusBar().showMessage(
                f"Clip saved (Telegram not configured): {Path(path).name}", 6000
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
        self.audio.start()   # restart mic monitoring even on failure
        if self.state == STATE_RECORDING:
            self.state = STATE_ARMED
            self._update_status()
        self.statusBar().showMessage(f"❌ Recording failed: {error}", 8000)

    # ── Slots ──────────────────────────────────────────────────────────────────

    def _on_frame(self, frame: np.ndarray, motion_level: float) -> None:
        self._last_motion_level = motion_level   # always current, used by continuation logic
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
                display, "ARMING IN",
                (display.shape[1] // 2 - 80, display.shape[0] // 2 - 50),
                cv2.FONT_HERSHEY_SIMPLEX, 0.9, (255, 200, 50), 2,
            )

        elif self.state == STATE_RECORDING:
            cv2.circle(display, (22, 22), 10, (0, 0, 255), -1)
            cv2.putText(display, "REC", (38, 30),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.75, (0, 0, 255), 2)

        elif self.state == STATE_ARMED:
            cv2.putText(display, "ARMED", (8, 24),
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
        self.video_label.setText(f"⚠️ Camera error:\n{msg}")
        self.statusBar().showMessage(f"Camera error: {msg}", 0)

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
        if self.state == STATE_COUNTDOWN:
            self.status_label.setText(f"COUNTDOWN\n{self.countdown_remaining}s")
            self.status_label.setStyleSheet("color: #ffaa30; font-size: 22px; font-weight: bold;")
        else:
            text, color = STATE_STYLES.get(self.state, ("UNKNOWN", "#888"))
            self.status_label.setText(text)
            self.status_label.setStyleSheet(
                f"color: {color}; font-size: 26px; font-weight: bold;"
            )

    def _show_setup(self) -> None:
        dlg = SetupDialog(self)
        if dlg.exec_() == QDialog.Accepted:
            token, chat_id = load_telegram_creds()
            if token and chat_id:
                self.telegram.setup(token, chat_id)
                self.statusBar().showMessage("Telegram credentials updated.", 4000)

    def _test_telegram(self) -> None:
        if not self.telegram.is_configured():
            QMessageBox.warning(self, "Not configured", "Please set up Telegram credentials first.")
            return
        self.tg_test_btn.setEnabled(False)
        self.tg_test_btn.setText("Testing…")
        ok, msg = self.telegram.test_connection()
        self.tg_test_btn.setEnabled(True)
        self.tg_test_btn.setText("📡  Test Telegram Connection")
        if ok:
            QMessageBox.information(self, "Telegram OK", msg)
        else:
            QMessageBox.critical(self, "Telegram Error", msg)

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
    app = QApplication(sys.argv)
    app.setApplicationName("HomeGuard")
    app.setStyle("Fusion")
    win = MainWindow()
    win.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()

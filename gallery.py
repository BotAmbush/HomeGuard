import os
from pathlib import Path

import cv2
from PyQt5.QtCore import Qt, QUrl, pyqtSignal
from PyQt5.QtGui import QFont, QImage, QPixmap
from PyQt5.QtMultimedia import QMediaContent, QMediaPlayer
from PyQt5.QtMultimediaWidgets import QVideoWidget
from PyQt5.QtWidgets import (
    QDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from i18n import tr, is_rtl

TRIGGER_COLORS = {"motion": "#e05a00", "noise": "#00a0a0", "both": "#cc1111"}


class VideoThumbnailWidget(QFrame):
    clicked = pyqtSignal(str)
    delete_requested = pyqtSignal(str)

    def __init__(self, video_path: str, parent=None):
        super().__init__(parent)
        self.video_path = video_path
        self.setFixedSize(185, 210)
        self.setFrameStyle(QFrame.StyledPanel)
        self.setCursor(Qt.PointingHandCursor)
        self.setStyleSheet(
            "VideoThumbnailWidget { background: #22223a; border: 1px solid #3a3b5a; border-radius: 8px; }"
            "VideoThumbnailWidget:hover { border-color: #7c7cff; background: #2a2b4a; }"
        )
        self._build(video_path)

    def _build(self, path: str) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(4)

        thumb = QLabel()
        thumb.setFixedSize(173, 110)
        thumb.setAlignment(Qt.AlignCenter)
        thumb.setStyleSheet("background: #111122; border-radius: 4px;")
        pix = self._thumbnail(path)
        if pix:
            thumb.setPixmap(pix.scaled(173, 110, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        else:
            thumb.setText("\U0001f4f9")
            thumb.setFont(QFont("Segoe UI", 28))
        layout.addWidget(thumb)

        stem = Path(path).stem
        parts = stem.split("_")
        date_str = time_str = trigger = ""
        try:
            date_str = parts[0]
            time_str = parts[1].replace("-", ":")
            trigger = parts[2] if len(parts) > 2 else "unknown"
        except Exception:
            trigger = "unknown"

        color = TRIGGER_COLORS.get(trigger, "#666")
        trigger_label = tr(f"trigger_{trigger}")
        badge = QLabel(f"  {trigger_label}  ")
        badge.setAlignment(Qt.AlignCenter)
        badge.setStyleSheet(
            f"background: {color}; color: white; border-radius: 4px;"
            f" padding: 2px; font-size: 10px; font-weight: bold;"
        )
        layout.addWidget(badge)

        dt_lbl = QLabel(f"{date_str}  {time_str}")
        dt_lbl.setAlignment(Qt.AlignCenter)
        dt_lbl.setStyleSheet("color: #aaa; font-size: 10px;")
        layout.addWidget(dt_lbl)

        del_btn = QPushButton(tr("gallery_del_btn"))
        del_btn.setFixedHeight(24)
        del_btn.setStyleSheet(
            "QPushButton { background: #3a0000; color: #ff8080; border: 1px solid #5a1010;"
            " border-radius: 4px; font-size: 10px; padding: 2px; }"
            "QPushButton:hover { background: #5a1010; }"
        )
        del_btn.clicked.connect(lambda: self.delete_requested.emit(self.video_path))
        layout.addWidget(del_btn)

    def _thumbnail(self, path: str) -> QPixmap | None:
        try:
            cap = cv2.VideoCapture(path)
            ret, frame = cap.read()
            cap.release()
            if ret:
                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                h, w, _ = rgb.shape
                img = QImage(rgb.data, w, h, w * 3, QImage.Format_RGB888)
                return QPixmap.fromImage(img)
        except Exception:
            pass
        return None

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.LeftButton:
            self.clicked.emit(self.video_path)


class VideoPlayerDialog(QDialog):
    def __init__(self, video_path: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle(tr("gallery_player_title", name=Path(video_path).name))
        self.setMinimumSize(720, 540)
        self.setStyleSheet(
            "QDialog { background: #12131e; color: #e0e0f0; }"
            "QPushButton { background: #2d2e4a; color: #e0e0f0; border: 1px solid #4a4b6a;"
            " border-radius: 6px; padding: 8px 18px; } QPushButton:hover { background: #3d3e6a; }"
        )
        self._build(video_path)

    def _build(self, path: str) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(8)

        self.player = QMediaPlayer(None, QMediaPlayer.VideoSurface)
        self.video_widget = QVideoWidget()
        self.video_widget.setMinimumSize(640, 420)
        self.player.setVideoOutput(self.video_widget)
        url = QUrl.fromLocalFile(os.path.abspath(path))
        self.player.setMedia(QMediaContent(url))
        layout.addWidget(self.video_widget)

        ctrl = QHBoxLayout()
        self.play_btn = QPushButton(tr("player_pause"))
        stop_btn = QPushButton(tr("player_stop"))
        close_btn = QPushButton(tr("player_close"))
        self.play_btn.clicked.connect(self._toggle)
        stop_btn.clicked.connect(self.player.stop)
        close_btn.clicked.connect(self.close)
        for b in [self.play_btn, stop_btn, close_btn]:
            ctrl.addWidget(b)
        layout.addLayout(ctrl)

        self.player.play()

    def _toggle(self) -> None:
        if self.player.state() == QMediaPlayer.PlayingState:
            self.player.pause()
            self.play_btn.setText(tr("player_play"))
        else:
            self.player.play()
            self.play_btn.setText(tr("player_pause"))

    def closeEvent(self, event) -> None:
        self.player.stop()
        super().closeEvent(event)


class GalleryWidget(QWidget):
    def __init__(self, recordings_dir: str, parent=None):
        super().__init__(parent)
        self.recordings_dir = recordings_dir
        self._build()
        self.refresh()

    def _build(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(8)
        layout.setContentsMargins(10, 10, 10, 10)

        toolbar = QHBoxLayout()
        self._title_lbl = QLabel(tr("gallery_title"))
        self._title_lbl.setStyleSheet("font-size: 15px; font-weight: bold; color: #c0c0f0;")
        self.count_lbl = QLabel("—")
        self.count_lbl.setStyleSheet("color: #8888aa; font-size: 12px;")
        self._refresh_btn = QPushButton(tr("gallery_refresh"))
        self._refresh_btn.setFixedWidth(110)
        self._refresh_btn.clicked.connect(self.refresh)
        self._clear_btn = QPushButton(tr("gallery_clear"))
        self._clear_btn.setFixedWidth(110)
        self._clear_btn.setStyleSheet(
            "QPushButton { background: #3a0000; color: #ff8080; border: 1px solid #5a1010;"
            " border-radius: 6px; padding: 6px 12px; } QPushButton:hover { background: #5a1010; }"
        )
        self._clear_btn.clicked.connect(self._clear_all)
        toolbar.addWidget(self._title_lbl)
        toolbar.addWidget(self.count_lbl)
        toolbar.addStretch()
        toolbar.addWidget(self._refresh_btn)
        toolbar.addWidget(self._clear_btn)
        layout.addLayout(toolbar)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setStyleSheet("QScrollArea { border: none; }")

        self.grid_widget = QWidget()
        self.grid = QGridLayout(self.grid_widget)
        self.grid.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        self.grid.setSpacing(10)
        self.grid.setContentsMargins(4, 4, 4, 4)
        scroll.setWidget(self.grid_widget)
        layout.addWidget(scroll)

    def retranslate(self) -> None:
        """Update all stored widget texts to the current language."""
        self._title_lbl.setText(tr("gallery_title"))
        self._refresh_btn.setText(tr("gallery_refresh"))
        self._clear_btn.setText(tr("gallery_clear"))
        self.refresh()   # rebuilds thumbnails with translated badge text

    def refresh(self) -> None:
        while self.grid.count():
            item = self.grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if not os.path.exists(self.recordings_dir):
            self.count_lbl.setText(tr("gallery_no_folder"))
            return

        files = sorted(
            Path(self.recordings_dir).glob("*.mp4"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )

        if not files:
            self.count_lbl.setText(tr("gallery_empty"))
            placeholder = QLabel(tr("gallery_empty_hint"))
            placeholder.setAlignment(Qt.AlignCenter)
            placeholder.setStyleSheet("color: #555; font-size: 14px; padding: 40px;")
            self.grid.addWidget(placeholder, 0, 0)
            return

        n = len(files)
        # English needs pluralisation; Hebrew string already covers all counts
        if is_rtl():
            self.count_lbl.setText(tr("gallery_count", n=str(n)))
        else:
            self.count_lbl.setText(tr("gallery_count", n=str(n), s="s" if n != 1 else ""))
        cols = 5
        for i, fp in enumerate(files):
            w = VideoThumbnailWidget(str(fp))
            w.clicked.connect(self._play)
            w.delete_requested.connect(self._delete)
            self.grid.addWidget(w, i // cols, i % cols)

    def _play(self, path: str) -> None:
        dlg = VideoPlayerDialog(path, self)
        dlg.exec_()

    def _delete(self, path: str) -> None:
        reply = QMessageBox.question(
            self,
            tr("gallery_del_title"),
            tr("gallery_del_msg", name=Path(path).name),
            QMessageBox.Yes | QMessageBox.No,
        )
        if reply == QMessageBox.Yes:
            try:
                os.remove(path)
            except Exception as e:
                QMessageBox.warning(self, tr("gallery_err_title"),
                                    tr("gallery_err_del", err=str(e)))
            self.refresh()

    def _clear_all(self) -> None:
        if not os.path.exists(self.recordings_dir):
            return
        files = list(Path(self.recordings_dir).glob("*.mp4"))
        if not files:
            return
        reply = QMessageBox.question(
            self,
            tr("gallery_clear_title"),
            tr("gallery_clear_msg", n=str(len(files))),
            QMessageBox.Yes | QMessageBox.No,
        )
        if reply == QMessageBox.Yes:
            for fp in files:
                try:
                    fp.unlink()
                except Exception:
                    pass
            self.refresh()

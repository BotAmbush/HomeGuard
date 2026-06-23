from collections import deque
import glob
import os
import queue
import subprocess
import sys
import threading
import time

import cv2
import imageio_ffmpeg
import numpy as np
import sounddevice as sd
import soundfile as sf
from PyQt5.QtCore import QMutex, QMutexLocker, QThread, pyqtSignal

# Pre-buffer: 10 s at 20 fps ≈ 200 frames; 250 is a generous ceiling
_PREBUFFER_MAXLEN = 250


class CameraThread(QThread):
    """Captures frames, performs motion detection, and optionally records to disk."""

    frame_ready = pyqtSignal(object, float)   # display_frame (ndarray), motion_level 0-1
    camera_error = pyqtSignal(str)

    def __init__(self, camera_index: int = 0, parent=None):
        super().__init__(parent)
        self.camera_index = camera_index
        self._running = False
        self._sensitivity = 5
        self._recording = False
        self._writer = None
        self._mutex = QMutex()
        self.actual_fps: float = 20.0
        self.actual_size: tuple[int, int] = (640, 480)
        # Rolling pre-event buffer — always contains the last ~10 s of raw frames
        self._prebuffer: deque = deque(maxlen=_PREBUFFER_MAXLEN)

    # ── Public thread-safe API ─────────────────────────────────────────────────

    def set_sensitivity(self, value: int) -> None:
        with QMutexLocker(self._mutex):
            self._sensitivity = max(1, min(10, value))

    def snapshot_prebuffer(self) -> list[np.ndarray]:
        """Return a copy of the current pre-event frame buffer (thread-safe)."""
        with QMutexLocker(self._mutex):
            return list(self._prebuffer)

    def start_recording(self, writer: cv2.VideoWriter) -> None:
        with QMutexLocker(self._mutex):
            self._writer = writer
            self._recording = True

    def stop_recording(self) -> None:
        with QMutexLocker(self._mutex):
            self._recording = False
            self._writer = None

    # ── Thread body ────────────────────────────────────────────────────────────

    def run(self) -> None:
        self._running = True
        cap = cv2.VideoCapture(self.camera_index, cv2.CAP_DSHOW)
        if not cap.isOpened():
            cap = cv2.VideoCapture(self.camera_index)
        if not cap.isOpened():
            self.camera_error.emit(f"לא ניתן לפתוח מצלמה {self.camera_index}")
            return

        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        cap.set(cv2.CAP_PROP_FPS, 20)

        self.actual_size = (
            int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)),
            int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)),
        )
        raw_fps = cap.get(cv2.CAP_PROP_FPS)
        self.actual_fps = raw_fps if raw_fps > 0 else 20.0

        prev_gray = None

        while self._running:
            ret, frame = cap.read()
            if not ret:
                time.sleep(0.05)
                continue

            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            gray = cv2.GaussianBlur(gray, (21, 21), 0)

            motion_level = 0.0
            display = frame.copy()

            if prev_gray is not None:
                with QMutexLocker(self._mutex):
                    sens = self._sensitivity

                diff_thresh = int(55 - sens * 5)
                min_area = max(300, int(8000 / sens))

                diff = cv2.absdiff(prev_gray, gray)
                _, thresh = cv2.threshold(diff, diff_thresh, 255, cv2.THRESH_BINARY)
                kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
                thresh = cv2.dilate(thresh, kernel, iterations=2)

                contours, _ = cv2.findContours(
                    thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
                )

                total_area = 0
                for c in contours:
                    area = cv2.contourArea(c)
                    if area > min_area:
                        total_area += area
                        x, y, w, h = cv2.boundingRect(c)
                        cv2.rectangle(display, (x, y), (x + w, y + h), (0, 255, 80), 2)
                        cv2.putText(
                            display, "MOTION",
                            (x, max(y - 5, 12)),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 255, 80), 1,
                        )

                frame_area = frame.shape[0] * frame.shape[1]
                motion_level = min(total_area / frame_area * 8, 1.0)

            prev_gray = gray

            with QMutexLocker(self._mutex):
                # Always feed the pre-event circular buffer
                self._prebuffer.append(frame.copy())
                # Write to VideoWriter when a recording is active
                if self._recording and self._writer is not None:
                    self._writer.write(frame)

            self.frame_ready.emit(display, motion_level)

        cap.release()

    def stop(self) -> None:
        self._running = False
        self.wait(3000)


class AudioMonitor:
    """Listens to the microphone and tracks RMS level; queues noise events."""

    def __init__(self):
        self._threshold: float = 0.05
        self._level: float = 0.0
        self._lock = threading.Lock()
        self._stream: sd.InputStream | None = None
        self.noise_queue: queue.Queue = queue.Queue()
        self._cooldown: int = 0
        self._active = False

    def set_threshold(self, percent: int) -> None:
        with self._lock:
            self._threshold = 0.005 + (percent / 100.0) * 0.495

    def get_level(self) -> float:
        with self._lock:
            return self._level

    def get_threshold(self) -> float:
        with self._lock:
            return self._threshold

    def start(self) -> None:
        if self._active:
            return
        try:
            self._stream = sd.InputStream(
                callback=self._callback,
                channels=1,
                samplerate=44100,
                blocksize=2048,
            )
            self._stream.start()
            self._active = True
        except Exception as e:
            print(f"[AudioMonitor] Could not start microphone: {e}")

    def stop(self) -> None:
        self._active = False
        if self._stream:
            try:
                self._stream.stop()
                self._stream.close()
            except Exception:
                pass
            self._stream = None

    def _callback(self, indata, frames, time_info, status) -> None:
        rms = float(np.sqrt(np.mean(indata ** 2)))
        with self._lock:
            self._level = rms
            threshold = self._threshold
            cd = self._cooldown
            if cd > 0:
                self._cooldown -= 1

        if rms > threshold and cd <= 0:
            with self._lock:
                self._cooldown = 44
            self.noise_queue.put(rms)


def _find_ffmpeg() -> str:
    """Locate ffmpeg — handles both dev mode and PyInstaller --onefile frozen EXE."""
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        pattern = os.path.join(sys._MEIPASS, "imageio_ffmpeg", "binaries", "ffmpeg*.exe")
        matches = glob.glob(pattern)
        if matches:
            return sorted(matches)[-1]
    return imageio_ffmpeg.get_ffmpeg_exe()


def _run_ffmpeg(cmd: list[str], timeout: int = 180) -> subprocess.CompletedProcess:
    """Run an ffmpeg command, hiding the console window on Windows."""
    kwargs: dict = {
        "capture_output": True,
        "stdin": subprocess.DEVNULL,
        "timeout": timeout,
    }
    if sys.platform == "win32":
        si = subprocess.STARTUPINFO()
        si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        si.wShowWindow = subprocess.SW_HIDE
        kwargs["startupinfo"] = si
        kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
    return subprocess.run(cmd, **kwargs)


class RecordingThread(QThread):
    """Records a video+audio clip (with optional pre-event buffer) and merges via ffmpeg.

    Pre-event buffer
    ----------------
    Pass `prebuffer` (list of raw frames from CameraThread.snapshot_prebuffer()) to
    prepend 10 s of footage recorded *before* the alert triggered.  Silent audio is
    generated for that portion so the final MP4 has matching A/V duration.

    For continuation chunks (motion still active), pass ``prebuffer=[]``.

    Audio conflict
    --------------
    The caller must call AudioMonitor.stop() BEFORE starting this thread and
    AudioMonitor.start() when recording_complete / recording_failed fires.
    """

    recording_complete = pyqtSignal(str)
    recording_failed = pyqtSignal(str)

    def __init__(
        self,
        camera_thread: CameraThread,
        output_path: str,
        duration: float,
        fps: float = 20.0,
        size: tuple[int, int] = (640, 480),
        prebuffer: list | None = None,
        parent=None,
    ):
        super().__init__(parent)
        self.camera_thread = camera_thread
        self.output_path = output_path
        self.duration = duration
        self.fps = fps
        self.size = size
        self.prebuffer: list[np.ndarray] = prebuffer or []

    def run(self) -> None:
        base = self.output_path.replace(".mp4", "")
        temp_vid = base + "__vid.avi"
        temp_aud = base + "__aud.wav"

        try:
            # ── Video writer ───────────────────────────────────────────────────
            fourcc = cv2.VideoWriter_fourcc(*"XVID")
            writer = cv2.VideoWriter(temp_vid, fourcc, self.fps, self.size)
            if not writer.isOpened():
                raise RuntimeError("VideoWriter failed to open")

            # Write pre-event frames (before live capture starts)
            for frame in self.prebuffer:
                resized = (
                    cv2.resize(frame, self.size)
                    if frame.shape[1] != self.size[0] or frame.shape[0] != self.size[1]
                    else frame
                )
                writer.write(resized)

            # Start live capture
            self.camera_thread.start_recording(writer)

            # ── Audio capture ──────────────────────────────────────────────────
            sample_rate = 44100
            audio_chunks: list[np.ndarray] = []
            audio_lock = threading.Lock()
            has_audio = False

            def audio_cb(indata, frames, time_info, status) -> None:
                with audio_lock:
                    audio_chunks.append(indata.copy())

            try:
                with sd.InputStream(
                    callback=audio_cb,
                    channels=1,
                    samplerate=sample_rate,
                    blocksize=2048,
                ):
                    time.sleep(self.duration)
                has_audio = bool(audio_chunks)
            except Exception as mic_err:
                print(f"[RecordingThread] mic unavailable (video-only): {mic_err}")
                time.sleep(self.duration)

            self.camera_thread.stop_recording()
            writer.release()

            # ── Save audio: prepend silence for the pre-buffer period ──────────
            if has_audio:
                pre_secs = len(self.prebuffer) / max(self.fps, 1.0)
                silence = np.zeros((int(pre_secs * sample_rate), 1), dtype=np.float32)
                live_audio = np.concatenate(audio_chunks, axis=0)
                full_audio = np.concatenate([silence, live_audio], axis=0)
                sf.write(temp_aud, full_audio, sample_rate)

            # ── Merge video + audio via ffmpeg ─────────────────────────────────
            ffmpeg = _find_ffmpeg()

            if has_audio and os.path.exists(temp_aud):
                cmd = [
                    ffmpeg, "-y",
                    "-i", temp_vid,
                    "-i", temp_aud,
                    "-c:v", "libx264",
                    "-c:a", "aac",
                    "-shortest",
                    self.output_path,
                ]
            else:
                cmd = [
                    ffmpeg, "-y",
                    "-i", temp_vid,
                    "-c:v", "libx264",
                    self.output_path,
                ]

            result = _run_ffmpeg(cmd)
            if result.returncode != 0:
                err = result.stderr.decode(errors="replace")
                raise RuntimeError(f"ffmpeg exit {result.returncode}: {err[:400]}")

            self.recording_complete.emit(self.output_path)

        except Exception as e:
            self.recording_failed.emit(str(e))
        finally:
            self.camera_thread.stop_recording()
            for f in [temp_vid, temp_aud]:
                if os.path.exists(f):
                    try:
                        os.remove(f)
                    except Exception:
                        pass

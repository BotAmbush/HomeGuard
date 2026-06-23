import os
import queue
import time

import requests
from PyQt5.QtCore import QThread, pyqtSignal

from i18n import tr, is_rtl


class TelegramSender(QThread):
    send_complete = pyqtSignal(str)
    send_failed = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._token = ""
        self._chat_id = ""
        self._queue: queue.Queue = queue.Queue()
        self._running = False

    def setup(self, token: str, chat_id: str) -> None:
        self._token = token.strip()
        self._chat_id = str(chat_id).strip()

    def is_configured(self) -> bool:
        return bool(self._token and self._chat_id)

    def test_connection(self) -> tuple[bool, str]:
        if not self.is_configured():
            return False, tr("tg_err_no_creds")
        try:
            r = requests.get(
                f"https://api.telegram.org/bot{self._token}/getMe", timeout=10
            )
            data = r.json()
            if not data.get("ok"):
                return False, data.get("description", tr("tg_err_title"))
            username = data["result"]["username"]
            self._send_text(tr("tg_connected"))
            return True, tr("tg_connected_as", username=username)
        except requests.exceptions.SSLError:
            return False, tr("tg_err_ssl")
        except requests.exceptions.ConnectionError:
            return False, tr("tg_err_conn")
        except requests.exceptions.Timeout:
            return False, tr("tg_err_timeout")
        except Exception as e:
            return False, str(e)

    def send_snapshot(self, alert_type: str, timestamp: str, jpeg_bytes: bytes) -> None:
        """Queue a snapshot photo for immediate delivery (before the clip is ready)."""
        self._queue.put({
            "task":       "snapshot",
            "alert_type": alert_type,
            "timestamp":  timestamp,
            "jpeg_bytes": jpeg_bytes,
        })

    def send_alert(
        self,
        alert_type: str,
        timestamp: str,
        video_path: str | None = None,
        chunk: int = 1,
    ) -> None:
        self._queue.put({
            "task":       "video",
            "alert_type": alert_type,
            "timestamp":  timestamp,
            "video_path": video_path,
            "chunk":      chunk,
            "retries":    0,
        })

    # ── Internal helpers ───────────────────────────────────────────────────────

    def _send_text(self, text: str) -> None:
        requests.post(
            f"https://api.telegram.org/bot{self._token}/sendMessage",
            json={"chat_id": self._chat_id, "text": text},
            timeout=15,
        ).raise_for_status()

    def _send_video(self, path: str, caption: str) -> None:
        with open(path, "rb") as f:
            requests.post(
                f"https://api.telegram.org/bot{self._token}/sendVideo",
                data={"chat_id": self._chat_id, "caption": caption},
                files={"video": f},
                timeout=120,
            ).raise_for_status()

    def _build_snapshot_caption(self, item: dict) -> str:
        """Caption for the immediate snapshot photo."""
        name = tr(f"trigger_{item['alert_type']}")
        ts   = item["timestamp"]
        rtl  = "‏" if is_rtl() else ""
        return "\n".join([
            f"{rtl}{tr('tg_snap_detected', name=name)}",
            "",
            f"{rtl}{tr('tg_time')}: {ts}",
            f"{rtl}{tr('tg_camera')}",
            f"{rtl}{tr('tg_snap_coming')}",
        ])

    def _build_message(self, item: dict) -> tuple[str, str]:
        """Return (text_message, video_caption) using the current UI language."""
        atype = item["alert_type"]
        ts    = item["timestamp"]
        chunk = item.get("chunk", 1)
        name  = tr(f"trigger_{atype}")
        rtl   = "‏" if is_rtl() else ""   # RTL mark only when Hebrew is active

        if chunk == 1:
            header = tr("tg_header_1", name=name)
            extra  = ""
        else:
            header = tr("tg_header_n", name=name, chunk=str(chunk))
            extra  = tr("tg_still_in_frame")

        lines = [
            f"{rtl}{header}",
            f"{rtl}",
            f"{rtl}{tr('tg_event_type')}: {name}",
            f"{rtl}{tr('tg_time')}: {ts}",
            f"{rtl}{tr('tg_camera')}",
        ]
        if extra:
            lines.insert(2, f"{rtl}{extra}")

        text = "\n".join(lines)

        if chunk == 1:
            caption = tr("tg_caption", name=name, ts=ts)
        else:
            caption = tr("tg_caption_n", name=name, ts=ts, chunk=str(chunk))

        return text, caption

    # ── Thread body ────────────────────────────────────────────────────────────

    def run(self) -> None:
        self._running = True
        while self._running:
            try:
                item = self._queue.get(timeout=1)
            except queue.Empty:
                continue

            task = item.get("task", "video")
            try:
                if task == "snapshot":
                    caption = self._build_snapshot_caption(item)
                    requests.post(
                        f"https://api.telegram.org/bot{self._token}/sendPhoto",
                        data={"chat_id": self._chat_id, "caption": caption},
                        files={"photo": ("snapshot.jpg", item["jpeg_bytes"], "image/jpeg")},
                        timeout=30,
                    ).raise_for_status()
                    self.send_complete.emit(f"snapshot — {item['timestamp']}")

                else:
                    text, caption = self._build_message(item)
                    chunk = item.get("chunk", 1)

                    # Chunk 1: snapshot already notified the user — just send the clip.
                    # Chunk 2+: send a continuation text before the clip.
                    if chunk > 1:
                        self._send_text(text)

                    vp = item.get("video_path")
                    if vp and os.path.exists(vp):
                        self._send_video(vp, caption)

                    self.send_complete.emit(
                        f"{item['alert_type']} — {item['timestamp']}"
                    )

            except Exception as e:
                if task == "video" and item.get("retries", 0) < 3:
                    item["retries"] = item.get("retries", 0) + 1
                    self._queue.put(item)
                    time.sleep(30)
                else:
                    self.send_failed.emit(tr("tg_fail_retry", err=str(e)))

    def stop(self) -> None:
        self._running = False
        self.wait(3000)

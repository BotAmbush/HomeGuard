import os
import queue
import time

import requests
from PyQt5.QtCore import QThread, pyqtSignal

# RTL mark — forces right-to-left rendering in Telegram for every line
_R = "‏"

_ALERT_NAMES = {
    "motion": "תנועה",
    "noise":  "רעש חריג",
    "both":   "תנועה ורעש",
}
_ALERT_ICONS = {
    "motion": "👁️",
    "noise":  "🔊",
    "both":   "⚠️",
}


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
            return False, "טוקן הבוט או מזהה הצ'אט חסרים."
        try:
            r = requests.get(
                f"https://api.telegram.org/bot{self._token}/getMe", timeout=10
            )
            data = r.json()
            if not data.get("ok"):
                return False, data.get("description", "שגיאת Telegram לא ידועה")
            username = data["result"]["username"]
            self._send_text(f"{_R}✅ HomeGuard מחובר ועובד!")
            return True, f"מחובר כ-@{username}"
        except requests.exceptions.SSLError:
            return False, "שגיאת SSL — נסה לבנות מחדש עם build.py."
        except requests.exceptions.ConnectionError:
            return False, "לא ניתן להגיע ל-Telegram — בדוק חיבור אינטרנט."
        except requests.exceptions.Timeout:
            return False, "פג זמן ההמתנה (10 שניות) — בדוק חיבור אינטרנט."
        except Exception as e:
            return False, str(e)

    def send_alert(
        self,
        alert_type: str,
        timestamp: str,
        video_path: str | None = None,
        chunk: int = 1,
    ) -> None:
        self._queue.put({
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

    def _build_message(self, item: dict) -> tuple[str, str]:
        """Return (text_message, video_caption) in Hebrew RTL."""
        atype  = item["alert_type"]
        ts     = item["timestamp"]
        chunk  = item.get("chunk", 1)
        name   = _ALERT_NAMES.get(atype, atype)
        icon   = _ALERT_ICONS.get(atype, "🚨")

        if chunk == 1:
            header = f"🚨 התראת HomeGuard — {name} זוהתה!"
            extra  = ""
        else:
            header = f"🚨 המשך אירוע — {name} (קטע {chunk})"
            extra  = f"{_R}🔄 הדמות עדיין בפריים — ממשיך להקליט\n"

        lines = [
            f"{_R}{header}",
            f"{_R}",
            f"{_R}{icon} סוג אירוע: {name}",
            f"{_R}🕐 שעה: {ts}",
            f"{_R}📹 מצלמת HomeGuard",
        ]
        if extra:
            lines.insert(2, extra.rstrip())

        text = "\n".join(lines)
        caption = f"{_R}📹 {name} — {ts}" + (f" (קטע {chunk})" if chunk > 1 else "")
        return text, caption

    # ── Thread body ────────────────────────────────────────────────────────────

    def run(self) -> None:
        self._running = True
        while self._running:
            try:
                item = self._queue.get(timeout=1)
            except queue.Empty:
                continue

            try:
                text, caption = self._build_message(item)
                self._send_text(text)

                vp = item.get("video_path")
                if vp and os.path.exists(vp):
                    self._send_video(vp, caption)

                self.send_complete.emit(
                    f"התראה נשלחה: {item['alert_type']} — {item['timestamp']}"
                )

            except Exception as e:
                if item["retries"] < 3:
                    item["retries"] += 1
                    self._queue.put(item)
                    time.sleep(30)
                else:
                    self.send_failed.emit(f"שליחת התראה נכשלה לאחר 3 ניסיונות: {e}")

    def stop(self) -> None:
        self._running = False
        self.wait(3000)

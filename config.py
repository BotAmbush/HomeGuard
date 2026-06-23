import json
import os
import sys


def get_base_dir() -> str:
    """Directory that holds all user data (config, credentials, recordings).

    Frozen EXE  → folder that contains the EXE.
    Dev script  → folder that contains this file.
    """
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


# ── Paths ──────────────────────────────────────────────────────────────────────
_CONFIG_FILE = os.path.join(get_base_dir(), "config.json")
_TELEGRAM_FILE = os.path.join(get_base_dir(), "telegram.txt")

# ── App config ─────────────────────────────────────────────────────────────────
DEFAULT_CONFIG = {
    "motion_sensitivity": 5,
    "noise_threshold": 30,
    "countdown_delay": 30,
    "camera_index": 0,
    "clip_duration": 15,
    "recordings_dir": "recordings",
}


def load_config() -> dict:
    if os.path.exists(_CONFIG_FILE):
        try:
            with open(_CONFIG_FILE, encoding="utf-8") as f:
                cfg = json.load(f)
            for k, v in DEFAULT_CONFIG.items():
                cfg.setdefault(k, v)
            return cfg
        except Exception:
            pass
    return DEFAULT_CONFIG.copy()


def save_config(config: dict) -> None:
    with open(_CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2)


# ── Telegram credentials ───────────────────────────────────────────────────────

def load_telegram_creds() -> tuple[str, str]:
    """Returns (bot_token, chat_id).  Both are '' if the file doesn't exist yet."""
    if not os.path.exists(_TELEGRAM_FILE):
        return "", ""
    try:
        data: dict[str, str] = {}
        with open(_TELEGRAM_FILE, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line.startswith("#") or "=" not in line:
                    continue
                key, _, val = line.partition("=")
                data[key.strip()] = val.strip()
        return data.get("BOT_TOKEN", ""), data.get("CHAT_ID", "")
    except Exception:
        return "", ""


def save_telegram_creds(token: str, chat_id: str) -> None:
    """Write credentials to telegram.txt next to the EXE / script."""
    with open(_TELEGRAM_FILE, "w", encoding="utf-8") as f:
        f.write("# HomeGuard — Telegram credentials\n")
        f.write("# Edit this file if you need to change your bot token or chat ID.\n")
        f.write("# Keep this file private — do not share it.\n\n")
        f.write(f"BOT_TOKEN={token}\n")
        f.write(f"CHAT_ID={chat_id}\n")

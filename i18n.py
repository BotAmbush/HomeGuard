"""Internationalisation helpers — English (en) and Hebrew (he)."""
from __future__ import annotations

_STRINGS: dict[str, dict[str, str]] = {
    "en": {
        # Window
        "window_title":     "HomeGuard — Room Monitor",
        "tab_monitor":      "\U0001f3e0  Monitor",
        "tab_gallery":      "\U0001f4f9  Gallery",

        # Status group
        "grp_status":       "Status",
        "state_disarmed":   "DISARMED",
        "state_armed":      "● ARMED",
        "state_rec":        "⬤ REC",
        "state_countdown":  "COUNTDOWN",
        "state_cd_unit":    "s",

        # Arm/Disarm group
        "grp_arm":          "Arm / Disarm",
        "lbl_delay":        "Delay:",
        "btn_arm":          "\U0001f7e2  ARM",
        "btn_disarm":       "\U0001f534  DISARM",

        # Countdown options
        "cd_none":  "No delay",
        "cd_30s":   "30 seconds",
        "cd_1m":    "1 minute",
        "cd_2m":    "2 minutes",
        "cd_5m":    "5 minutes",

        # Sensitivity group
        "grp_sens":          "Detection Sensitivity",
        "lbl_motion_sens":   "Motion sensitivity:",
        "lbl_motion_live":   "Live motion level:",
        "lbl_noise_thresh":  "Noise threshold:",
        "lbl_noise_live":    "Live noise level:",
        "lbl_low":           "Low",
        "lbl_high":          "High",

        # Camera row
        "lbl_camera_index":  "Camera index:",
        "cam_no_signal":     "No camera signal",
        "cam_overlay_armed": "ARMED",
        "cam_overlay_rec":   "REC",
        "cam_overlay_arming":"ARMING IN",

        # Telegram group
        "grp_telegram":  "Telegram",
        "btn_test_tg":   "\U0001f4e1  Test Telegram Connection",
        "btn_creds":     "⚙️  Change Credentials",

        # Language toggle
        "btn_lang":      "עברית",

        # Status bar messages
        "sb_ready":        "HomeGuard ready.",
        "sb_disarmed":     "Disarmed.",
        "sb_armed":        "Armed — monitoring active.",
        "sb_rec_1":        "⚠️  {type} detected — recording clip 1…",
        "sb_rec_n":        "⚠️  Motion continues — recording clip {n}…",
        "sb_saved_no_tg":  "Clip saved (Telegram not configured): {name}",
        "sb_rec_fail":     "❌ Recording failed: {err}",
        "sb_tg_sent":      "\U0001f4e4 {msg}",
        "sb_tg_fail":      "❌ {msg}",

        # Telegram messages sent to phone
        "tg_connected":        "✅ HomeGuard connected!",
        "tg_header_1":         "\U0001f6a8 HomeGuard Alert — {name} detected!",
        "tg_header_n":         "\U0001f6a8 Continuing — {name} (clip {chunk})",
        "tg_still_in_frame":   "\U0001f504 Still in frame — recording continues",
        "tg_event_type":       "Event",
        "tg_time":             "Time",
        "tg_camera":           "HomeGuard camera",
        "tg_caption":          "\U0001f4f9 {name} — {ts}",
        "tg_caption_n":        "\U0001f4f9 {name} — {ts} (clip {chunk})",
        "tg_connected_as":     "Connected as @{username}",

        # Trigger type names (in Telegram + gallery badge)
        "trigger_motion":  "Motion",
        "trigger_noise":   "Noise",
        "trigger_both":    "Motion & Noise",

        # Telegram connection errors
        "tg_err_no_creds":  "Bot token or chat ID is missing.",
        "tg_err_ssl":       "SSL error — try rebuilding with build.py.",
        "tg_err_conn":      "Cannot reach Telegram — check internet.",
        "tg_err_timeout":   "Connection timed out (10 s).",
        "tg_fail_retry":    "Alert failed after 3 attempts: {err}",

        # Setup dialog
        "setup_title":      "HomeGuard — Telegram Setup",
        "setup_welcome":    "\U0001f3e0 Welcome to HomeGuard",
        "setup_info": (
            "To receive alerts on your phone you need a Telegram bot.\n\n"
            "1. Open Telegram → search <b>@BotFather</b> → /newbot\n"
            "2. Copy the <b>Bot Token</b> it gives you.\n"
            "3. Send any message to your new bot.\n"
            "4. Visit: <tt>https://api.telegram.org/bot&lt;TOKEN&gt;/getUpdates</tt>\n"
            "   Find <tt>\"chat\":{{\"id\":YOUR_ID}}</tt> — copy that number.\n\n"
            "Credentials will be saved to:\n<tt>{path}</tt>"
        ),
        "setup_token":      "Bot Token:",
        "setup_chat":       "Chat ID:",
        "setup_token_ph":   "1234567890:ABCdef…",
        "setup_chat_ph":    "123456789",
        "btn_test_conn":    "\U0001f517 Test Connection",
        "btn_save":         "✅ Save & Continue",
        "btn_skip":         "Skip (no Telegram)",
        "setup_fill_both":  "❌ Fill in both fields first.",
        "setup_testing":    "Testing…",
        "setup_both_req":   "❌ Both fields are required.",
        "setup_updated":    "Telegram credentials updated.",

        # Dialogs
        "tg_not_cfg_title": "Not configured",
        "tg_not_cfg_msg":   "Please set up Telegram credentials first.",
        "tg_ok_title":      "Telegram OK",
        "tg_err_title":     "Telegram Error",
        "cam_err_prefix":   "⚠️ Camera error:\n",

        # Gallery
        "gallery_title":       "\U0001f4f9  Recorded Alerts",
        "gallery_no_folder":   "No recordings folder",
        "gallery_empty":       "No recordings yet",
        "gallery_empty_hint":  "No recordings yet.\nArm HomeGuard to start monitoring.",
        "gallery_count":       "{n} recording{s}",
        "gallery_refresh":     "\U0001f504 Refresh",
        "gallery_clear":       "\U0001f5d1 Clear All",
        "gallery_del_btn":     "\U0001f5d1 Delete",
        "gallery_del_title":   "Delete Recording",
        "gallery_del_msg":     "Delete this clip?\n{name}",
        "gallery_clear_title": "Clear All",
        "gallery_clear_msg":   "Permanently delete all {n} recordings?",
        "gallery_err_title":   "Error",
        "gallery_err_del":     "Could not delete: {err}",
        "gallery_player_title":"HomeGuard Player — {name}",
        "player_pause":        "⏸ Pause",
        "player_play":         "▶ Play",
        "player_stop":         "⏹ Stop",
        "player_close":        "✕ Close",
    },

    "he": {
        # Window
        "window_title":     "HomeGuard — ניטור חדר",
        "tab_monitor":      "\U0001f3e0  ניטור",
        "tab_gallery":      "\U0001f4f9  גלריה",

        # Status group
        "grp_status":       "מצב",
        "state_disarmed":   "כבוי",
        "state_armed":      "● פעיל",
        "state_rec":        "⬤ מקליט",
        "state_countdown":  "ספירה לאחור",
        "state_cd_unit":    "ש׳",

        # Arm/Disarm group
        "grp_arm":          "הפעלה / כיבוי",
        "lbl_delay":        ":עיכוב",
        "btn_arm":          "\U0001f7e2  הפעל",
        "btn_disarm":       "\U0001f534  כבה",

        # Countdown options
        "cd_none":  "ללא עיכוב",
        "cd_30s":   "30 שניות",
        "cd_1m":    "דקה אחת",
        "cd_2m":    "2 דקות",
        "cd_5m":    "5 דקות",

        # Sensitivity group
        "grp_sens":          "רגישות זיהוי",
        "lbl_motion_sens":   ":רגישות תנועה",
        "lbl_motion_live":   ":רמת תנועה נוכחית",
        "lbl_noise_thresh":  ":סף רעש",
        "lbl_noise_live":    ":רמת רעש נוכחית",
        "lbl_low":           "נמוך",
        "lbl_high":          "גבוה",

        # Camera row
        "lbl_camera_index":  ":מצלמה",
        "cam_no_signal":     "אין אות מצלמה",
        "cam_overlay_armed": "ARMED",
        "cam_overlay_rec":   "REC",
        "cam_overlay_arming":"ARMING IN",

        # Telegram group
        "grp_telegram":  "טלגרם",
        "btn_test_tg":   "\U0001f4e1  בדוק חיבור טלגרם",
        "btn_creds":     "⚙️  שנה פרטי חיבור",

        # Language toggle
        "btn_lang":      "English",

        # Status bar messages
        "sb_ready":        ".HomeGuard מוכן",
        "sb_disarmed":     ".המערכת כובתה",
        "sb_armed":        ".מערכת פעילה — ניטור פועל",
        "sb_rec_1":        "…{type} זוהתה — מקליט קטע 1 ⚠️",
        "sb_rec_n":        "…תנועה עדיין פעילה — מקליט קטע {n} ⚠️",
        "sb_saved_no_tg":  "(קטע נשמר (טלגרם לא מוגדר: {name}",
        "sb_rec_fail":     "הקלטה נכשלה: {err} ❌",
        "sb_tg_sent":      "{msg} \U0001f4e4",
        "sb_tg_fail":      "{msg} ❌",

        # Telegram messages sent to phone
        "tg_connected":        "✅ HomeGuard מחובר ועובד!",
        "tg_header_1":         "\U0001f6a8 התראת HomeGuard — {name} זוהתה!",
        "tg_header_n":         "\U0001f6a8 המשך אירוע — {name} (קטע {chunk})",
        "tg_still_in_frame":   "\U0001f504 הדמות עדיין בפריים — ממשיך להקליט",
        "tg_event_type":       "סוג אירוע",
        "tg_time":             "שעה",
        "tg_camera":           "מצלמת HomeGuard",
        "tg_caption":          "\U0001f4f9 {name} — {ts}",
        "tg_caption_n":        "\U0001f4f9 {name} — {ts} (קטע {chunk})",
        "tg_connected_as":     "מחובר כע-@{username}",

        # Trigger type names
        "trigger_motion":  "תנועה",
        "trigger_noise":   "רעש",
        "trigger_both":    "תנועה ורעש",

        # Telegram connection errors
        "tg_err_no_creds":  ".טוקן הבוט או מזהה הצ'אט חסרים",
        "tg_err_ssl":       ".SSL שגיאת — נסה לבנות מחדש עם build.py",
        "tg_err_conn":      ".לא ניתן להגיע ל-Telegram — בדוק חיבור אינטרנט",
        "tg_err_timeout":   ".(10 שניות) פג זמן ההמתנה",
        "tg_fail_retry":    "שליחת התראה נכשלה לאחר 3 ניסיונות: {err}",

        # Setup dialog
        "setup_title":      "HomeGuard — הגדרת טלגרם",
        "setup_welcome":    "ברוך הבא ל-HomeGuard \U0001f3e0",
        "setup_info": (
            "כדי לקבל התראות בטלפון תצטרך בוט טלגרם.\n\n"
            "1. פתח טלגרם → חפש <b>@BotFather</b> → /newbot\n"
            "2. העתק את ה-<b>Bot Token</b> שתקבל.\n"
            "3. שלח הודעה כלשהי לבוט החדש.\n"
            "4. בקר ב: <tt>https://api.telegram.org/bot&lt;TOKEN&gt;/getUpdates</tt>\n"
            '   מצא <tt>"chat":{{"id":המספר}}</tt> — העתק את המספר.\n\n'
            "הפרטים ישמרו ב:\n<tt>{path}</tt>"
        ),
        "setup_token":      ":טוקן בוט",
        "setup_chat":       ":מזהה צ'אט",
        "setup_token_ph":   "1234567890:ABCdef…",
        "setup_chat_ph":    "123456789",
        "btn_test_conn":    "\U0001f517 בדוק חיבור",
        "btn_save":         "✅ שמור והמשך",
        "btn_skip":         "דלג (ללא טלגרם)",
        "setup_fill_both":  ".יש למלא את שני השדות ❌",
        "setup_testing":    "…בודק",
        "setup_both_req":   ".שני השדות נדרשים ❌",
        "setup_updated":    ".פרטי הטלגרם עודכנו",

        # Dialogs
        "tg_not_cfg_title": "לא מוגדר",
        "tg_not_cfg_msg":   ".יש להגדיר פרטי טלגרם תחילה",
        "tg_ok_title":      "טלגרם תקין",
        "tg_err_title":     "שגיאת טלגרם",
        "cam_err_prefix":   "שגיאת מצלמה:\n ⚠️",

        # Gallery
        "gallery_title":       "\U0001f4f9  הקלטות",
        "gallery_no_folder":   "תיקיית הקלטות לא קיימת",
        "gallery_empty":       "אין הקלטות עדיין",
        "gallery_empty_hint":  ".אין הקלטות עדיין\nהפעל את HomeGuard כדי להתחיל לנטר",
        "gallery_count":       "{n} הקלטות",
        "gallery_refresh":     "\U0001f504 רענן",
        "gallery_clear":       "\U0001f5d1 מחק הכל",
        "gallery_del_btn":     "\U0001f5d1 מחק",
        "gallery_del_title":   "מחיקת הקלטה",
        "gallery_del_msg":     "למחוק את הקטע?\n{name}",
        "gallery_clear_title": "מחיקת הכל",
        "gallery_clear_msg":   "למחוק לצמיתות את כל {n} ההקלטות?",
        "gallery_err_title":   "שגיאה",
        "gallery_err_del":     "לא ניתן למחוק: {err}",
        "gallery_player_title":"HomeGuard — {name}",
        "player_pause":        "⏸ השהה",
        "player_play":         "▶ הפעל",
        "player_stop":         "⏹ עצור",
        "player_close":        "✕ סגור",
    },
}

_lang: str = "en"


def set_lang(lang: str) -> None:
    global _lang
    _lang = lang if lang in _STRINGS else "en"


def get_lang() -> str:
    return _lang


def is_rtl() -> bool:
    return _lang == "he"


def tr(key: str, **kw: str) -> str:
    """Return the translated string for *key* in the current language."""
    text = _STRINGS[_lang].get(key) or _STRINGS["en"].get(key, key)
    if kw:
        try:
            return text.format(**kw)
        except (KeyError, ValueError):
            return text
    return text

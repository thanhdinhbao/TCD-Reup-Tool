"""Telegram notification service."""
import os
import json
import logging
import requests
from typing import Optional, List, Dict, Any

logger = logging.getLogger(__name__)

TELEGRAM_API_BASE = "https://api.telegram.org/bot"


class TelegramNotifier:
    def __init__(self, bot_token: str = "", bot_username: str = "", telegram_chat_ids: Optional[List[str]] = None, enabled: bool = True):
        self.bot_token = bot_token
        self.bot_username = bot_username
        self.telegram_chat_ids = telegram_chat_ids or []
        self.enabled = enabled

    def is_enabled(self) -> bool:
        return bool(self.enabled and self.bot_token and self.telegram_chat_ids)

    def send_alert(self, message: str, parse_mode: str = "HTML") -> bool:
        if not self.is_enabled():
            return False
        return self.send_message(message, parse_mode=parse_mode)

    def send_message(self, text: str, parse_mode: str = "HTML") -> bool:
        if not self.bot_token or not self.telegram_chat_ids:
            return False
        url = f"{TELEGRAM_API_BASE}{self.bot_token}/sendMessage"
        success = True
        for chat_id in self.telegram_chat_ids:
            try:
                res = requests.post(url, json={"chat_id": chat_id.strip(), "text": text, "parse_mode": parse_mode}, timeout=10)
                if res.status_code != 200:
                    success = False
            except Exception as e:
                logger.error(f"Failed to send telegram msg: {e}")
                success = False
        return success

    def notify_upload_success(self, video_title: str, tiktok_url: str):
        if not self.enabled:
            return False
        msg = f"🚀 <b>Upload TikTok Thành Công!</b>\n\n📌 <b>Video:</b> {video_title}\n🔗 <b>Link:</b> {tiktok_url}"
        return self.send_message(msg)

    def notify_error(self, step: str, err: str):
        if not self.enabled:
            return False
        msg = f"⚠ <b>Lỗi Hệ Thống TCD VIP:</b>\n\n⚙ <b>Giai đoạn:</b> {step}\n❌ <b>Chi tiết:</b> {err}"
        return self.send_message(msg)

    def save_telegram_map(self, filepath: str = "telegram_config.json") -> bool:
        try:
            data = {
                "bot_token": self.bot_token,
                "bot_username": self.bot_username,
                "telegram_chat_ids": self.telegram_chat_ids,
                "enabled": self.enabled
            }
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            return True
        except Exception as e:
            logger.error(f"Failed to save telegram config: {e}")
            return False

    def load_telegram_map(self, filepath: str = "telegram_config.json") -> bool:
        target = filepath
        if not os.path.exists(target):
            cfg_cand = os.path.join("config", os.path.basename(filepath))
            if os.path.exists(cfg_cand):
                target = cfg_cand
            else:
                return False
        try:
            with open(target, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.bot_token = data.get("bot_token", "")
            self.bot_username = data.get("bot_username", "")
            self.telegram_chat_ids = data.get("telegram_chat_ids", [])
            self.enabled = data.get("enabled", True)
            return True
        except Exception as e:
            logger.error(f"Failed to load telegram config: {e}")
            return False


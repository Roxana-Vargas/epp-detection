"""Envío de alertas a Telegram con imagen anotada y control anti-spam."""
import time

import requests

from .config import settings

_last_alert_ts = 0.0


def send_alert(caption: str, image_bytes: bytes | None = None,
               force: bool = False) -> dict:
    """Envía la alerta. Respeta un cooldown para no spamear el chat.

    force=True ignora el cooldown (útil en procesamiento por lotes, donde
    cada imagen es una inspección deliberada y queremos una alerta por cada una).
    """
    global _last_alert_ts

    if not settings.telegram_enabled:
        return {"sent": False, "reason": "Telegram no configurado"}

    now = time.time()
    if not force and now - _last_alert_ts < settings.ALERT_COOLDOWN_SECONDS:
        return {"sent": False, "reason": "cooldown activo"}

    base = f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}"
    try:
        if image_bytes:
            resp = requests.post(
                f"{base}/sendPhoto",
                data={
                    "chat_id": settings.TELEGRAM_CHAT_ID,
                    "caption": caption,
                    "parse_mode": "Markdown",
                },
                files={"photo": ("annotated.jpg", image_bytes, "image/jpeg")},
                timeout=20,
            )
        else:
            resp = requests.post(
                f"{base}/sendMessage",
                data={
                    "chat_id": settings.TELEGRAM_CHAT_ID,
                    "text": caption,
                    "parse_mode": "Markdown",
                },
                timeout=20,
            )
        resp.raise_for_status()
    except requests.RequestException as exc:
        return {"sent": False, "reason": f"error Telegram: {exc}"}

    _last_alert_ts = now
    return {"sent": True}

"""Envío de alertas a Telegram con imagen anotada, control anti-spam y reintentos."""
import time

import requests

from .config import settings

_last_alert_ts = 0.0
_MAX_RETRIES = 3


def _post(base: str, caption: str, image_bytes: bytes | None):
    if image_bytes:
        return requests.post(
            f"{base}/sendPhoto",
            data={
                "chat_id": settings.TELEGRAM_CHAT_ID,
                "caption": caption,
                "parse_mode": "Markdown",
            },
            files={"photo": ("annotated.jpg", image_bytes, "image/jpeg")},
            timeout=20,
        )
    return requests.post(
        f"{base}/sendMessage",
        data={
            "chat_id": settings.TELEGRAM_CHAT_ID,
            "text": caption,
            "parse_mode": "Markdown",
        },
        timeout=20,
    )


def send_alert(caption: str, image_bytes: bytes | None = None,
               force: bool = False) -> dict:
    """Envía la alerta. Respeta un cooldown para no spamear el chat.

    force=True ignora el cooldown (útil en procesamiento por lotes, donde
    cada imagen es una inspección deliberada y queremos una alerta por cada una).

    Reintenta hasta 3 veces ante errores de red o límite de tasa de Telegram (429).
    """
    global _last_alert_ts

    if not settings.telegram_enabled:
        return {"sent": False, "reason": "Telegram no configurado"}

    now = time.time()
    if not force and now - _last_alert_ts < settings.ALERT_COOLDOWN_SECONDS:
        return {"sent": False, "reason": "cooldown activo"}

    base = f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}"
    last_reason = ""
    for intento in range(1, _MAX_RETRIES + 1):
        try:
            resp = _post(base, caption, image_bytes)
            # Telegram limita ~1 msg/seg por chat: ante 429 espera y reintenta.
            if resp.status_code == 429:
                retry_after = 2
                try:
                    retry_after = resp.json().get("parameters", {}).get("retry_after", 2)
                except ValueError:
                    pass
                last_reason = f"límite de tasa (429), reintentando en {retry_after}s"
                time.sleep(min(retry_after, 15))
                continue
            resp.raise_for_status()
            _last_alert_ts = time.time()
            return {"sent": True}
        except requests.RequestException as exc:
            last_reason = f"error Telegram: {exc}"
            if intento < _MAX_RETRIES:
                time.sleep(1.5 * intento)

    return {"sent": False, "reason": last_reason}

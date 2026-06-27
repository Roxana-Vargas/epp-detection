"""Verifica la configuración de Telegram enviando un mensaje de prueba.

Uso:
    python test_telegram.py
"""
from app.config import settings
from app.telegram_alert import send_alert


def main() -> None:
    print("Bot token configurado :", "sí" if settings.TELEGRAM_BOT_TOKEN else "NO")
    print("Chat ID configurado   :", "sí" if settings.TELEGRAM_CHAT_ID else "NO")

    if not settings.telegram_enabled:
        print("\n❌ Falta TELEGRAM_BOT_TOKEN o TELEGRAM_CHAT_ID en el .env")
        return

    # send_alert tiene cooldown; lo ignoramos para esta prueba.
    import app.telegram_alert as t
    t._last_alert_ts = 0.0

    result = send_alert(
        "✅ *Prueba de conexión*\nTu sistema de detección de EPP ya puede "
        "enviarte alertas por Telegram."
    )
    if result.get("sent"):
        print("\n✅ ¡Mensaje enviado! Revisa tu Telegram.")
    else:
        print("\n❌ No se envió. Motivo:", result.get("reason"))
        print("Revisa que: 1) le escribiste primero al bot, "
              "2) el token y chat_id son correctos.")


if __name__ == "__main__":
    main()

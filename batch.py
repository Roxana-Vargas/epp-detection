"""Procesamiento por lotes: analiza todas las imágenes de una carpeta.

Uso:
    python batch.py ./imagenes
"""
import sys
from pathlib import Path

from app import database
from app.annotate import annotate
from app.config import settings
from app.detector import detect
from app.rules import build_alert_message, evaluate
from app.telegram_alert import send_alert

EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}


def main(folder: str) -> None:
    database.init_db()
    storage = Path(settings.STORAGE_DIR)
    imgs = [p for p in Path(folder).iterdir() if p.suffix.lower() in EXTS]
    if not imgs:
        print("No se encontraron imágenes en", folder)
        return

    print(f"Procesando {len(imgs)} imágenes…\n")
    for p in imgs:
        data = p.read_bytes()
        try:
            raw = detect(data)
        except Exception as exc:  # noqa: BLE001
            print(f"[ERROR] {p.name}: {exc}")
            continue
        preds = raw.get("predictions", [])
        result = evaluate(preds)
        annotated_bytes = annotate(data, preds)
        out = storage / f"batch_{p.stem}.jpg"
        out.write_bytes(annotated_bytes)

        alert_sent = False
        if not result["compliant"]:
            # force=True: en un lote queremos una alerta por cada imagen que incumple.
            status = send_alert(
                build_alert_message(result, p.name), annotated_bytes, force=True
            )
            alert_sent = status.get("sent", False)
        database.save_detection(p.name, result, alert_sent, str(out))

        estado = "OK ✅" if result["compliant"] else "VIOLACIÓN ❌"
        falta = ", ".join(result["missing_required"]) or "-"
        sin = ", ".join(result["violations_detected"]) or "-"
        print(f"{p.name:28s} {estado:14s} falta: {falta:22s} sin EPP: {sin}")

    print("\nEstadísticas:", database.get_stats())


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(1)
    main(sys.argv[1])

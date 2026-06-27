"""Procesamiento por lotes: analiza todas las imágenes de una carpeta y genera
un reporte detallado en consola.

Uso:
    python batch.py ./imagenes
    python batch.py ./imagenes --required "hardhat,safety vest"
    python batch.py ./imagenes --required "hardhat,safety vest" --confidence 45

Con --required defines qué EPP es obligatorio SOLO para esta corrida (no toca
la configuración global). Si no se da --violations, se derivan las clases
negativas "no-<epp>" automáticamente.
"""
import os
import sys
import time
from collections import Counter
from pathlib import Path

os.system("")  # habilita colores ANSI en la consola de Windows
try:
    sys.stdout.reconfigure(encoding="utf-8")  # caja y emojis en Windows (cp1252)
except (AttributeError, ValueError):
    pass

from app import database
from app.annotate import annotate
from app.config import settings
from app.detector import detect
from app.rules import build_alert_message, evaluate
from app.telegram_alert import send_alert

EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}


class C:
    """Códigos de color ANSI."""
    R = "\033[0m"; B = "\033[1m"; DIM = "\033[2m"
    RED = "\033[91m"; GRN = "\033[92m"; YEL = "\033[93m"
    CYN = "\033[96m"; MAG = "\033[95m"; BLU = "\033[94m"; GRY = "\033[90m"


def bar(pct: float, width: int = 24, color: str = C.GRN) -> str:
    filled = round(width * pct / 100)
    return f"{color}{'█' * filled}{C.GRY}{'░' * (width - filled)}{C.R}"


def rule(char: str = "─", width: int = 64) -> str:
    return f"{C.GRY}{char * width}{C.R}"


def header() -> None:
    print()
    print(f"{C.CYN}{C.B}╔{'═' * 62}╗{C.R}")
    title = "🦺  REPORTE DE DETECCIÓN DE EPP"
    print(f"{C.CYN}{C.B}║{C.R}  {C.B}{title}{C.R}{' ' * (62 - len(title) - 3)}{C.CYN}{C.B}║{C.R}")
    print(f"{C.CYN}{C.B}╚{'═' * 62}╝{C.R}")
    tg = f"{C.GRN}activo{C.R}" if settings.telegram_enabled else f"{C.YEL}desactivado{C.R}"
    print(f"  {C.GRY}Modelo:{C.R}       {C.B}{settings.ROBOFLOW_MODEL_ID}{C.R}")
    print(f"  {C.GRY}EPP obligat.:{C.R} {', '.join(settings.REQUIRED_PPE)}")
    print(f"  {C.GRY}Confianza:{C.R}    {settings.CONFIDENCE_THRESHOLD:.0f}%   "
          f"{C.GRY}Telegram:{C.R} {tg}")
    print()


def image_block(idx: int, total: int, name: str, result: dict,
                preds: list, elapsed: float, alert_sent: bool,
                alert_reason: str = "", error: str = "") -> None:
    print(f"{C.B}[{idx}/{total}]{C.R} {C.B}{name}{C.R}")
    if error:
        print(f"   └─ {C.RED}✖ ERROR{C.R}  {C.DIM}{error}{C.R}\n")
        return

    ok = result["compliant"]
    badge = f"{C.GRN}✅ CUMPLE{C.R}" if ok else f"{C.RED}❌ VIOLACIÓN{C.R}"
    personas = sum(1 for p in preds if p.get("class", "").lower() == "person")
    confs = [p.get("confidence", 0) for p in preds]
    avg = f"{sum(confs) / len(confs) * 100:.0f}%" if confs else "—"

    print(f"   └─ {badge}  {C.GRY}·{C.R}  👷 {personas} pers.  {C.GRY}·{C.R}  "
          f"🎯 {len(preds)} obj.  {C.GRY}·{C.R}  📊 conf. {avg}  {C.GRY}·{C.R}  ⏱ {elapsed:.1f}s")

    if ok:
        det = ", ".join(result["detected_classes"]) or "—"
        print(f"      {C.GRY}Detectado        :{C.R} {C.GRN}{det}{C.R}")
    else:
        if result["missing_required"]:
            print(f"      {C.GRY}Falta obligatorio:{C.R} {C.YEL}{', '.join(result['missing_required'])}{C.R}")
        if result["violations_detected"]:
            print(f"      {C.GRY}Sin protección   :{C.R} {C.RED}{', '.join(result['violations_detected'])}{C.R}")
        if alert_sent:
            tg = f"{C.GRN}🔔 enviada{C.R}"
        else:
            tg = f"{C.YEL}⚠ no enviada{C.R}" + (f" {C.GRY}({alert_reason}){C.R}" if alert_reason else "")
        print(f"      {C.GRY}Telegram         :{C.R} {tg}")
    print()


def summary(total: int, ok: int, errors: int, alerts: int,
            infringido: Counter, elapsed_total: float) -> None:
    analizadas = total - errors
    viol = analizadas - ok
    pct = (100 * ok / analizadas) if analizadas else 0
    color = C.GRN if pct >= 80 else (C.YEL if pct >= 50 else C.RED)

    print(rule("═"))
    print(f"{C.B}{C.CYN}  RESUMEN{C.R}")
    print(rule())
    print(f"  📁 Imágenes procesadas : {C.B}{analizadas}{C.R}"
          + (f"   {C.RED}({errors} con error){C.R}" if errors else ""))
    print(f"  ✅ Cumplen             : {C.GRN}{ok}{C.R}")
    print(f"  ❌ Violaciones         : {C.RED}{viol}{C.R}")
    print(f"  🔔 Alertas enviadas    : {alerts}")
    print(f"  ⏱  Tiempo total        : {elapsed_total:.1f}s  "
          f"{C.GRY}({elapsed_total / max(analizadas, 1):.1f}s/imagen){C.R}")
    print()
    print(f"  {C.GRY}Cumplimiento:{C.R}  {bar(pct, 24, color)}  {color}{C.B}{pct:.0f}%{C.R}")

    if infringido:
        print()
        print(f"  {C.B}EPP más infringido:{C.R}")
        top = infringido.most_common(5)
        maxv = top[0][1]
        for i, (cls, n) in enumerate(top, 1):
            b = bar(100 * n / maxv, 16, C.RED)
            print(f"    {i}. {cls:<18s} {b} {C.B}{n}{C.R}")
    print(rule("═"))
    print()


def _csv(text: str) -> list[str]:
    return [x.strip().lower() for x in text.split(",") if x.strip()]


def main(folder: str, required: str | None = None,
         violations: str | None = None, confidence: float | None = None) -> None:
    database.init_db()

    # Overrides solo para esta corrida (no modifican la config global).
    if required is not None:
        settings.REQUIRED_PPE = _csv(required)
    if violations is not None:
        settings.VIOLATION_CLASSES = _csv(violations)
    elif required is not None:
        # Si solo te importan ciertos EPP obligatorios, deriva sus clases
        # "negativas" (no-<epp>) para que el modelo también pueda marcarlas.
        settings.VIOLATION_CLASSES = [f"no-{x}" for x in settings.REQUIRED_PPE]
    if confidence is not None:
        settings.CONFIDENCE_THRESHOLD = confidence

    storage = Path(settings.STORAGE_DIR)
    folder_path = Path(folder)
    if not folder_path.is_dir():
        print(f"{C.RED}La carpeta no existe:{C.R} {folder}")
        return
    imgs = sorted(p for p in folder_path.iterdir() if p.suffix.lower() in EXTS)
    if not imgs:
        print(f"{C.YEL}No se encontraron imágenes en{C.R} {folder}")
        return

    header()
    print(f"  {C.DIM}Analizando {len(imgs)} imágenes…{C.R}\n")
    print(rule())

    ok_count = errors = alerts = 0
    infringido: Counter = Counter()
    t0 = time.perf_counter()

    for i, p in enumerate(imgs, 1):
        data = p.read_bytes()
        t_img = time.perf_counter()
        try:
            raw = detect(data)
        except Exception as exc:  # noqa: BLE001
            errors += 1
            image_block(i, len(imgs), p.name, {}, [], 0, False, error=str(exc))
            continue

        preds = raw.get("predictions", [])
        result = evaluate(preds)
        annotated_bytes = annotate(data, preds)
        (storage / f"batch_{p.stem}.jpg").write_bytes(annotated_bytes)

        alert_sent = False
        alert_reason = ""
        if result["compliant"]:
            ok_count += 1
        else:
            for c in result["missing_required"] + result["violations_detected"]:
                infringido[c] += 1
            status = send_alert(build_alert_message(result, p.name), annotated_bytes, force=True)
            alert_sent = status.get("sent", False)
            alert_reason = status.get("reason", "")
            if alert_sent:
                alerts += 1

        database.save_detection(p.name, result, alert_sent, str(storage / f"batch_{p.stem}.jpg"))
        image_block(i, len(imgs), p.name, result, preds,
                    time.perf_counter() - t_img, alert_sent, alert_reason)

    summary(len(imgs), ok_count, errors, alerts, infringido, time.perf_counter() - t0)
    print(f"  {C.DIM}Imágenes anotadas guardadas en:{C.R} {storage}/")
    print(f"  {C.DIM}Ver detalle en el panel web:{C.R} http://localhost:8000\n")


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser(
        description="Analiza por lotes las imágenes de una carpeta y reporta el EPP.",
        epilog='Ejemplo: python batch.py ./imagenes '
               '--required "hardhat,safety vest"',
    )
    ap.add_argument("folder", help="Carpeta con las imágenes a analizar")
    ap.add_argument("--required", metavar="EPP",
                    help='EPP obligatorio, separado por comas. '
                         'Ej: "hardhat,safety vest". Solo se marca violación si falta alguno.')
    ap.add_argument("--violations", metavar="CLASES",
                    help='Clases de violación a considerar, separadas por comas. '
                         'Ej: "no-hardhat,no-safety vest". '
                         'Si se omite, se derivan de --required.')
    ap.add_argument("--confidence", type=float, metavar="0-100",
                    help="Umbral de confianza de la inferencia (sobrescribe la config).")
    args = ap.parse_args()
    main(args.folder, args.required, args.violations, args.confidence)

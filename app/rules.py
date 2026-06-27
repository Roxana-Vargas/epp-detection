"""Lógica de negocio: a partir de las detecciones decide si hay cumplimiento de EPP."""
from .config import settings


def evaluate(predictions: list[dict]) -> dict:
    """Evalúa cumplimiento de EPP.

    Reglas:
      - Una clase de VIOLATION_CLASSES detectada => violación directa.
      - Cada EPP de REQUIRED_PPE debe aparecer entre las clases detectadas;
        si falta => violación.

    Devuelve un dict con el veredicto y el detalle.
    """
    detected = [
        (p.get("class", "").lower(), float(p.get("confidence", 0)))
        for p in predictions
    ]
    detected_classes = {c for c, _ in detected}

    # 1) Clases negativas explícitas del modelo (ej: "no-helmet")
    violations_detected = sorted(detected_classes & set(settings.VIOLATION_CLASSES))

    # 2) EPP requerido que NO aparece
    missing_required = sorted(
        item for item in settings.REQUIRED_PPE if item not in detected_classes
    )

    compliant = not violations_detected and not missing_required

    return {
        "compliant": compliant,
        "missing_required": missing_required,
        "violations_detected": violations_detected,
        "detected_classes": sorted(detected_classes),
        "required_ppe": settings.REQUIRED_PPE,
        "num_detections": len(predictions),
    }


def build_alert_message(result: dict, filename: str) -> str:
    """Mensaje legible para la alerta de Telegram."""
    lines = ["🚨 *ALERTA EPP* 🚨", f"Imagen: `{filename}`", ""]
    if result["missing_required"]:
        lines.append("❌ Falta EPP obligatorio: " + ", ".join(result["missing_required"]))
    if result["violations_detected"]:
        lines.append("⚠️ Detectado sin protección: " + ", ".join(result["violations_detected"]))
    detected = result["detected_classes"] or ["(nada)"]
    lines.append("")
    lines.append("✅ Detectado: " + ", ".join(detected))
    return "\n".join(lines)

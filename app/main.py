"""API REST de detección de EPP con alertas por Telegram y panel web."""
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Body, FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from . import database
from .annotate import annotate
from .config import settings
from .detector import DetectorError, detect
from .rules import build_alert_message, evaluate
from .telegram_alert import send_alert

_BASE = Path(__file__).parent.parent
_STATIC = _BASE / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    database.init_db()
    yield


app = FastAPI(
    title="Sistema de Detección de EPP",
    description="Detecta Equipo de Protección Personal en fotos (modelo Roboflow) "
                "y alerta por Telegram cuando falta EPP obligatorio.",
    version="2.0.0",
    lifespan=lifespan,
)

_STORAGE = Path(settings.STORAGE_DIR)


# ============================ Sistema ============================
@app.get("/health", tags=["sistema"])
def health() -> dict:
    return {
        "status": "ok",
        "roboflow_configurado": bool(settings.ROBOFLOW_API_KEY and settings.ROBOFLOW_MODEL_ID),
        "telegram_configurado": settings.telegram_enabled,
        "epp_obligatorio": settings.REQUIRED_PPE,
        "modelo": settings.ROBOFLOW_MODEL_ID,
    }


# ============================ Detección ============================
@app.post("/detect", tags=["deteccion"])
async def detect_endpoint(file: UploadFile = File(...)) -> JSONResponse:
    """Sube una foto, detecta EPP y alerta si falta protección obligatoria."""
    if not (file.content_type or "").startswith("image/"):
        raise HTTPException(400, "El archivo debe ser una imagen.")

    image_bytes = await file.read()
    if not image_bytes:
        raise HTTPException(400, "Imagen vacía.")

    try:
        raw = detect(image_bytes)
    except DetectorError as exc:
        raise HTTPException(502, str(exc)) from exc

    predictions = raw.get("predictions", [])
    result = evaluate(predictions)

    annotated_bytes = annotate(image_bytes, predictions)
    rec_uuid = uuid.uuid4().hex[:12]
    annotated_path = _STORAGE / f"{rec_uuid}.jpg"
    annotated_path.write_bytes(annotated_bytes)

    alert_status = {"sent": False, "reason": "cumple EPP"}
    if not result["compliant"]:
        caption = build_alert_message(result, file.filename or "foto")
        alert_status = send_alert(caption, annotated_bytes)

    rec_id = database.save_detection(
        file.filename or "foto", result, alert_status.get("sent", False),
        str(annotated_path),
    )

    return JSONResponse(
        {
            "id": rec_id,
            "filename": file.filename,
            **result,
            "predictions": predictions,
            "alerta_telegram": alert_status,
            "imagen_anotada": f"/annotated/{rec_id}",
        }
    )


@app.get("/annotated/{rec_id}", tags=["deteccion"])
def annotated(rec_id: int):
    rec = database.get_record(rec_id)
    if not rec or not rec.get("annotated_path"):
        raise HTTPException(404, "No encontrado.")
    path = Path(rec["annotated_path"])
    if not path.exists():
        raise HTTPException(404, "Imagen no disponible.")
    return FileResponse(path, media_type="image/jpeg")


# ============================ Historial / Stats ============================
@app.get("/history", tags=["historial"])
def history(limit: int = 50) -> list[dict]:
    return database.get_history(limit)


@app.delete("/history", tags=["historial"])
def clear_history() -> dict:
    n = database.clear_history()
    return {"borradas": n}


@app.get("/stats", tags=["historial"])
def stats() -> dict:
    return database.get_stats()


@app.get("/stats/timeseries", tags=["historial"])
def stats_timeseries(days: int = 14) -> dict:
    return database.get_timeseries(days)


@app.get("/stats/by-class", tags=["historial"])
def stats_by_class() -> dict:
    return database.get_class_breakdown()


# ============================ Configuración ============================
@app.get("/config", tags=["configuracion"])
def get_config() -> dict:
    return settings.public_config()


@app.put("/config", tags=["configuracion"])
def put_config(data: dict = Body(...)) -> dict:
    applied = settings.update(data)
    return {"ok": True, "aplicado": applied, "config": settings.public_config()}


@app.get("/classes", tags=["configuracion"])
def get_classes() -> dict:
    """Clases disponibles para poblar los selectores de la web."""
    items = sorted(set(settings.available_classes()) | set(database.get_observed_classes()))
    negatives = [c for c in items if c.startswith("no-") or c in settings.VIOLATION_CLASSES]
    positives = [c for c in items if c not in negatives]
    return {"all": items, "positives": positives, "negatives": negatives}


@app.post("/telegram/test", tags=["configuracion"])
def telegram_test() -> dict:
    if not settings.telegram_enabled:
        raise HTTPException(400, "Telegram no configurado (token o chat_id vacíos).")
    return send_alert(
        "✅ *Prueba de conexión*\nTu sistema de detección de EPP ya puede "
        "enviarte alertas por Telegram.",
        force=True,
    )


# ============================ Web ============================
@app.get("/", include_in_schema=False)
def index():
    return FileResponse(_STATIC / "index.html")


app.mount("/static", StaticFiles(directory=_STATIC), name="static")

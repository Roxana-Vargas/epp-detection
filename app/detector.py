"""Inferencia contra el modelo de Roboflow vía API REST (sin dependencias pesadas)."""
import base64
import time

import requests

from .config import settings

_MAX_RETRIES = 3
_RETRY_BACKOFF = 2.0  # segundos: 2, 4, 6...


class DetectorError(Exception):
    pass


def detect(image_bytes: bytes) -> dict:
    """Envía la imagen a Roboflow y devuelve el JSON de predicciones.

    Respuesta típica:
        {
          "predictions": [
            {"x":.., "y":.., "width":.., "height":.., "confidence":.., "class":"helmet"},
            ...
          ],
          "image": {"width":.., "height":..}
        }
    """
    if not settings.ROBOFLOW_API_KEY or not settings.ROBOFLOW_MODEL_ID:
        raise DetectorError(
            "Falta ROBOFLOW_API_KEY o ROBOFLOW_MODEL_ID en el .env"
        )

    url = f"{settings.ROBOFLOW_API_URL}/{settings.ROBOFLOW_MODEL_ID}"
    params = {
        "api_key": settings.ROBOFLOW_API_KEY,
        "confidence": settings.CONFIDENCE_THRESHOLD,
        "overlap": settings.OVERLAP_THRESHOLD,
        "format": "json",
    }
    encoded = base64.b64encode(image_bytes)

    last_exc: Exception | None = None
    for intento in range(1, _MAX_RETRIES + 1):
        try:
            resp = requests.post(
                url,
                params=params,
                data=encoded,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                timeout=30,
            )
            resp.raise_for_status()
            return resp.json()
        except requests.RequestException as exc:
            last_exc = exc
            if intento < _MAX_RETRIES:
                time.sleep(_RETRY_BACKOFF * intento)  # backoff incremental

    raise DetectorError(
        f"Error llamando a Roboflow tras {_MAX_RETRIES} intentos: {last_exc}"
    )

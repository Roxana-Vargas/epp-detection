"""Configuración central: lee del .env y permite overrides en caliente (config.json)."""
import json
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

CONFIG_OVERRIDE_PATH = os.getenv("CONFIG_OVERRIDE_PATH", "config.json")


def _csv(name: str, default: str = "") -> list[str]:
    raw = os.getenv(name, default)
    return [x.strip().lower() for x in raw.split(",") if x.strip()]


# Campos que la interfaz web puede editar en caliente, con su tipo.
EDITABLE_FIELDS: dict[str, str] = {
    "ROBOFLOW_MODEL_ID": "str",
    "CONFIDENCE_THRESHOLD": "float",
    "OVERLAP_THRESHOLD": "float",
    "PPE_CLASSES": "list",
    "REQUIRED_PPE": "list",
    "VIOLATION_CLASSES": "list",
    "TELEGRAM_BOT_TOKEN": "str",
    "TELEGRAM_CHAT_ID": "str",
    "ALERT_COOLDOWN_SECONDS": "int",
}

# Campos sensibles: no se devuelven completos a la web (solo si están puestos).
SECRET_FIELDS = {"TELEGRAM_BOT_TOKEN"}

# Catálogo de clases conocidas por modelo (en minúscula), para poblar los
# selectores de la web. Se complementa con las clases vistas en el historial.
KNOWN_MODEL_CLASSES: dict[str, list[str]] = {
    "construction-site-safety/27": [
        "hardhat", "mask", "no-hardhat", "no-mask", "no-safety vest",
        "person", "safety cone", "safety vest", "machinery", "vehicle",
    ],
}


class Settings:
    # Roboflow
    ROBOFLOW_API_KEY: str = os.getenv("ROBOFLOW_API_KEY", "")
    ROBOFLOW_MODEL_ID: str = os.getenv("ROBOFLOW_MODEL_ID", "")
    ROBOFLOW_API_URL: str = os.getenv("ROBOFLOW_API_URL", "https://serverless.roboflow.com")
    CONFIDENCE_THRESHOLD: float = float(os.getenv("CONFIDENCE_THRESHOLD", "40"))
    OVERLAP_THRESHOLD: float = float(os.getenv("OVERLAP_THRESHOLD", "30"))

    # Reglas de EPP
    PPE_CLASSES: list[str] = _csv("PPE_CLASSES", "helmet,vest")
    REQUIRED_PPE: list[str] = _csv("REQUIRED_PPE", "helmet,vest")
    VIOLATION_CLASSES: list[str] = _csv("VIOLATION_CLASSES", "no-helmet,no-vest")

    # Telegram
    TELEGRAM_BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
    TELEGRAM_CHAT_ID: str = os.getenv("TELEGRAM_CHAT_ID", "")
    ALERT_COOLDOWN_SECONDS: int = int(os.getenv("ALERT_COOLDOWN_SECONDS", "60"))

    # App
    DATABASE_PATH: str = os.getenv("DATABASE_PATH", "epp.db")
    STORAGE_DIR: str = os.getenv("STORAGE_DIR", "storage")

    @property
    def telegram_enabled(self) -> bool:
        return bool(self.TELEGRAM_BOT_TOKEN and self.TELEGRAM_CHAT_ID)

    # ---- Persistencia de overrides editables desde la web ----
    def _coerce(self, field: str, value):
        kind = EDITABLE_FIELDS[field]
        if kind == "float":
            return max(0.0, min(100.0, float(value)))
        if kind == "int":
            return max(0, int(value))
        if kind == "list":
            if isinstance(value, str):
                items = value.split(",")
            else:
                items = list(value)
            return [str(x).strip().lower() for x in items if str(x).strip()]
        return str(value).strip()

    def load_overrides(self) -> None:
        path = Path(CONFIG_OVERRIDE_PATH)
        if not path.exists():
            return
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return
        for field, value in data.items():
            if field in EDITABLE_FIELDS:
                setattr(self, field, self._coerce(field, value))

    def update(self, data: dict) -> dict:
        """Aplica cambios validados y los persiste en config.json."""
        applied = {}
        for field, value in data.items():
            if field not in EDITABLE_FIELDS:
                continue
            coerced = self._coerce(field, value)
            setattr(self, field, coerced)
            applied[field] = coerced

        # Persistir el conjunto completo de campos editables actuales.
        snapshot = {f: getattr(self, f) for f in EDITABLE_FIELDS}
        Path(CONFIG_OVERRIDE_PATH).write_text(
            json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        return applied

    def available_classes(self) -> list[str]:
        """Clases conocidas para el modelo actual + las definidas en la config."""
        base = set(KNOWN_MODEL_CLASSES.get(self.ROBOFLOW_MODEL_ID.lower(), []))
        base |= set(self.PPE_CLASSES) | set(self.VIOLATION_CLASSES) | set(self.REQUIRED_PPE)
        return sorted(base)

    def public_config(self) -> dict:
        """Config editable para la web (oculta el valor de los secretos)."""
        out = {}
        for field, kind in EDITABLE_FIELDS.items():
            value = getattr(self, field)
            if field in SECRET_FIELDS:
                out[field] = {"set": bool(value), "type": kind}  # nunca el valor real
            else:
                out[field] = {"value": value, "type": kind}
        out["_meta"] = {
            "roboflow_api_url": self.ROBOFLOW_API_URL,
            "roboflow_key_set": bool(self.ROBOFLOW_API_KEY),
            "telegram_enabled": self.telegram_enabled,
        }
        return out


settings = Settings()
settings.load_overrides()
Path(settings.STORAGE_DIR).mkdir(parents=True, exist_ok=True)

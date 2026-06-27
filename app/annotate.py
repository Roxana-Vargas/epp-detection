"""Dibuja las cajas de detección sobre la imagen original con Pillow."""
import io

from PIL import Image, ImageDraw, ImageFont

from .config import settings

_OK_COLOR = (34, 197, 94)       # verde
_BAD_COLOR = (239, 68, 68)      # rojo
_NEUTRAL_COLOR = (59, 130, 246)  # azul


def _color_for(cls: str) -> tuple:
    cls = cls.lower()
    if cls in settings.VIOLATION_CLASSES:
        return _BAD_COLOR
    if cls in settings.PPE_CLASSES:
        return _OK_COLOR
    return _NEUTRAL_COLOR


def annotate(image_bytes: bytes, predictions: list[dict]) -> bytes:
    img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype("arial.ttf", max(14, img.width // 60))
    except OSError:
        font = ImageFont.load_default()

    for p in predictions:
        cls = p.get("class", "?")
        conf = float(p.get("confidence", 0))
        x, y = float(p["x"]), float(p["y"])
        w, h = float(p["width"]), float(p["height"])
        left, top = x - w / 2, y - h / 2
        right, bottom = x + w / 2, y + h / 2
        color = _color_for(cls)

        draw.rectangle([left, top, right, bottom], outline=color, width=3)
        label = f"{cls} {conf:.0%}"
        tb = draw.textbbox((0, 0), label, font=font)
        tw, th = tb[2] - tb[0], tb[3] - tb[1]
        draw.rectangle([left, top - th - 4, left + tw + 6, top], fill=color)
        draw.text((left + 3, top - th - 3), label, fill="white", font=font)

    out = io.BytesIO()
    img.save(out, format="JPEG", quality=90)
    return out.getvalue()

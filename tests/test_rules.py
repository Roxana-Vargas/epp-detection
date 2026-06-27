"""Tests de la lógica de reglas de EPP (no requieren red ni Roboflow)."""
from app.config import settings
from app import rules


def setup_function() -> None:
    settings.REQUIRED_PPE = ["helmet", "vest"]
    settings.VIOLATION_CLASSES = ["no-helmet"]
    settings.PPE_CLASSES = ["helmet", "vest"]


def test_cumple_con_todo_el_epp():
    preds = [
        {"class": "helmet", "confidence": 0.9},
        {"class": "vest", "confidence": 0.8},
    ]
    r = rules.evaluate(preds)
    assert r["compliant"] is True
    assert r["missing_required"] == []


def test_falta_un_epp_obligatorio():
    preds = [{"class": "helmet", "confidence": 0.9}]
    r = rules.evaluate(preds)
    assert r["compliant"] is False
    assert "vest" in r["missing_required"]


def test_clase_negativa_es_violacion():
    preds = [
        {"class": "helmet", "confidence": 0.9},
        {"class": "vest", "confidence": 0.9},
        {"class": "no-helmet", "confidence": 0.7},
    ]
    r = rules.evaluate(preds)
    assert r["compliant"] is False
    assert "no-helmet" in r["violations_detected"]


def test_imagen_sin_detecciones_no_cumple():
    r = rules.evaluate([])
    assert r["compliant"] is False
    assert set(r["missing_required"]) == {"helmet", "vest"}


def test_mensaje_de_alerta_contiene_lo_que_falta():
    r = rules.evaluate([{"class": "helmet", "confidence": 0.9}])
    msg = rules.build_alert_message(r, "obrero.jpg")
    assert "vest" in msg
    assert "obrero.jpg" in msg

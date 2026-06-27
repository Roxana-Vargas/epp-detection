"""Persistencia ligera en SQLite: historial de inspecciones y estadísticas."""
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from .config import settings

_DB = settings.DATABASE_PATH


def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(_DB)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with _conn() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS detections (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT NOT NULL,
                filename TEXT,
                compliant INTEGER NOT NULL,
                missing TEXT,
                violations TEXT,
                detected TEXT,
                num_detections INTEGER,
                alert_sent INTEGER DEFAULT 0,
                annotated_path TEXT
            )
            """
        )


def save_detection(filename: str, result: dict, alert_sent: bool,
                   annotated_path: str | None) -> int:
    with _conn() as conn:
        cur = conn.execute(
            """
            INSERT INTO detections
              (created_at, filename, compliant, missing, violations,
               detected, num_detections, alert_sent, annotated_path)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                datetime.now(timezone.utc).isoformat(),
                filename,
                int(result["compliant"]),
                json.dumps(result["missing_required"]),
                json.dumps(result["violations_detected"]),
                json.dumps(result["detected_classes"]),
                result["num_detections"],
                int(alert_sent),
                annotated_path,
            ),
        )
        return cur.lastrowid


def get_history(limit: int = 50) -> list[dict]:
    with _conn() as conn:
        rows = conn.execute(
            "SELECT * FROM detections ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
        return [dict(r) for r in rows]


def get_record(rec_id: int) -> dict | None:
    with _conn() as conn:
        row = conn.execute(
            "SELECT * FROM detections WHERE id = ?", (rec_id,)
        ).fetchone()
        return dict(row) if row else None


def get_stats() -> dict:
    with _conn() as conn:
        total = conn.execute("SELECT COUNT(*) c FROM detections").fetchone()["c"]
        compliant = conn.execute(
            "SELECT COUNT(*) c FROM detections WHERE compliant = 1"
        ).fetchone()["c"]
        alerts = conn.execute(
            "SELECT COUNT(*) c FROM detections WHERE alert_sent = 1"
        ).fetchone()["c"]
    rate = round(100 * compliant / total, 1) if total else 0.0
    return {
        "total_inspecciones": total,
        "cumplimientos": compliant,
        "violaciones": total - compliant,
        "alertas_enviadas": alerts,
        "porcentaje_cumplimiento": rate,
    }


def get_timeseries(days: int = 14) -> dict:
    """Cumplimientos vs violaciones agrupados por día (para gráfico de líneas)."""
    with _conn() as conn:
        rows = conn.execute(
            """
            SELECT date(created_at) AS dia,
                   SUM(compliant) AS cumplen,
                   COUNT(*) - SUM(compliant) AS violan,
                   COUNT(*) AS total
            FROM detections
            WHERE created_at >= date('now', ?)
            GROUP BY dia ORDER BY dia
            """,
            (f"-{int(days)} days",),
        ).fetchall()
    return {
        "labels": [r["dia"] for r in rows],
        "cumplen": [r["cumplen"] for r in rows],
        "violan": [r["violan"] for r in rows],
        "total": [r["total"] for r in rows],
    }


def get_class_breakdown() -> dict:
    """Ranking de EPP faltante/infringido (para gráfico de barras/dona)."""
    counts: dict[str, int] = {}
    with _conn() as conn:
        rows = conn.execute("SELECT missing, violations FROM detections").fetchall()
    for r in rows:
        for col in ("missing", "violations"):
            try:
                for item in json.loads(r[col] or "[]"):
                    counts[item] = counts.get(item, 0) + 1
            except (json.JSONDecodeError, TypeError):
                continue
    ordered = sorted(counts.items(), key=lambda kv: kv[1], reverse=True)
    return {
        "labels": [k for k, _ in ordered],
        "values": [v for _, v in ordered],
    }


def get_observed_classes() -> list[str]:
    """Clases que han aparecido en el historial (detectadas, faltantes, violaciones)."""
    out: set[str] = set()
    with _conn() as conn:
        rows = conn.execute("SELECT detected, missing, violations FROM detections").fetchall()
    for r in rows:
        for col in ("detected", "missing", "violations"):
            try:
                for item in json.loads(r[col] or "[]"):
                    out.add(item)
            except (json.JSONDecodeError, TypeError):
                continue
    return sorted(out)


def clear_history() -> int:
    with _conn() as conn:
        n = conn.execute("SELECT COUNT(*) c FROM detections").fetchone()["c"]
        conn.execute("DELETE FROM detections")
    return n

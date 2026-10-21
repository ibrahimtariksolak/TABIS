"""
TimescaleDB'den okuma yapan sorgu katmanı.

Satırlar sözlüğe elle (indeksle) çevirmek yerine `dict_row` satır fabrikasıyla
döndürülür; kolon sırası değiştiğinde sessizce yanlış alan eşleşmesi olmasın diye.
"""

from __future__ import annotations

from typing import Any

from psycopg.rows import dict_row

from battery_platform.db.connection import get_connection

PACK_READING_FIELDS = """
    time, pack_id, pack_voltage, pack_soc,
    max_temperature_c, cell_voltage_delta,
    soh_percent, thermal_state, current_a
"""


def _isoformat_time(row: dict[str, Any]) -> dict[str, Any]:
    if row.get("time") is not None:
        row["time"] = row["time"].isoformat()
    return row


def get_latest_pack_reading(pack_id: str) -> dict | None:
    with get_connection() as conn, conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            f"""
            SELECT {PACK_READING_FIELDS}
            FROM pack_reading
            WHERE pack_id = %s
            ORDER BY time DESC
            LIMIT 1;
            """,
            (pack_id,),
        )
        row = cur.fetchone()

    return _isoformat_time(row) if row else None


def get_pack_history(pack_id: str, limit: int = 100) -> list[dict]:
    """
    En yeniden eskiye doğru `limit` satır döner.

    Not: yoğun bir zaman aralığı için bu ham satırları çekmek yerine
    TimescaleDB continuous aggregate'leri kullanmak daha uygundur;
    bkz. docs/architecture.md "Bilinen Sınırlamalar".
    """
    with get_connection() as conn, conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            f"""
            SELECT {PACK_READING_FIELDS}
            FROM pack_reading
            WHERE pack_id = %s
            ORDER BY time DESC
            LIMIT %s;
            """,
            (pack_id, limit),
        )
        rows = cur.fetchall()

    return [_isoformat_time(r) for r in rows]


def get_latest_cell_status(pack_id: str) -> list[dict]:
    """
    Belirli bir pack'in en son zaman damgasındaki tüm hücrelerinin
    durumunu (SoC, voltaj, sıcaklık, dengeleme aktif mi) döner.
    """
    with get_connection() as conn, conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            WITH latest_time AS (
                SELECT MAX(cr.time) AS t
                FROM cell_reading cr
                JOIN session s ON cr.session_id = s.session_id
                WHERE s.pack_id = %s
            )
            SELECT cr.cell_id, cr.soc, cr.voltage, cr.temperature_c, cr.balancing_active
            FROM cell_reading cr
            JOIN session s ON cr.session_id = s.session_id
            CROSS JOIN latest_time
            WHERE s.pack_id = %s AND cr.time = latest_time.t
            ORDER BY cr.cell_id;
            """,
            (pack_id, pack_id),
        )
        return cur.fetchall()


def get_latest_session_id(pack_id: str) -> str | None:
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT session_id FROM session
            WHERE pack_id = %s
            ORDER BY started_at DESC
            LIMIT 1;
            """,
            (pack_id,),
        )
        row = cur.fetchone()
    return str(row[0]) if row else None


def get_session_current_temp_series(session_id: str) -> tuple[list[float], list[float]]:
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT current_a, max_temperature_c
            FROM pack_reading
            WHERE session_id = %s AND current_a IS NOT NULL
            ORDER BY time ASC;
            """,
            (session_id,),
        )
        rows = cur.fetchall()

    currents = [r[0] for r in rows]
    temps = [r[1] for r in rows]
    return currents, temps


def get_events(pack_id: str, limit: int = 50) -> list[dict]:
    """Bir pack için en yeni olay kayıtlarını döner."""
    with get_connection() as conn, conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            SELECT time, session_id, pack_id, event_type, severity, message, details
            FROM event
            WHERE pack_id = %s
            ORDER BY time DESC
            LIMIT %s;
            """,
            (pack_id, limit),
        )
        rows = cur.fetchall()

    for row in rows:
        _isoformat_time(row)
        row["session_id"] = str(row["session_id"]) if row["session_id"] else None
    return rows


def list_packs() -> list[dict]:
    """
    Veritabanında kaydı olan tüm pack'leri ve son görülme zamanlarını döner.
    Filo görünümü için ilk adım; PACK-1'in her yere gömülü olmasını bitirir.
    """
    with get_connection() as conn, conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            SELECT pack_id,
                   MAX(time) AS last_seen,
                   COUNT(*)  AS reading_count
            FROM pack_reading
            GROUP BY pack_id
            ORDER BY pack_id;
            """
        )
        rows = cur.fetchall()

    for row in rows:
        if row.get("last_seen") is not None:
            row["last_seen"] = row["last_seen"].isoformat()
    return rows

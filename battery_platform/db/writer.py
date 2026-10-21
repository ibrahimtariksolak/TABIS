"""
Simülatörden gelen batarya verisini TimescaleDB'ye yazan modül.
Performans için tekil INSERT yerine toplu (batch) INSERT kullanır.

Bağlantılar havuzdan ödünç alınır; `pool.connection()` bloğu başarıyla biterse
commit, hata fırlarsa rollback otomatik yapılır - bu yüzden burada açık
commit/close çağrısı yoktur.
"""

from __future__ import annotations

import logging
from typing import Any

from psycopg import sql
from psycopg.types.json import Jsonb

from battery_platform.db.connection import get_connection

logger = logging.getLogger(__name__)

PACK_COLUMNS = (
    "time", "session_id", "pack_id", "pack_voltage", "pack_soc",
    "max_temperature_c", "cell_voltage_delta", "soh_percent",
    "thermal_state", "current_a",
)

CELL_COLUMNS = (
    "time", "session_id", "cell_id", "soc", "voltage",
    "temperature_c", "balancing_active",
)


def _insert_statement(table: str, columns: tuple[str, ...]) -> sql.Composed:
    return sql.SQL("INSERT INTO {table} ({cols}) VALUES ({vals})").format(
        table=sql.Identifier(table),
        cols=sql.SQL(", ").join(sql.Identifier(c) for c in columns),
        vals=sql.SQL(", ").join(sql.Placeholder() * len(columns)),
    )


def create_session(pack_id: str, driving_style: str) -> str:
    """Yeni bir sürüş oturumu başlatır, session_id döner."""
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute(
            "INSERT INTO session (pack_id, driving_style) VALUES (%s, %s) RETURNING session_id;",
            (pack_id, driving_style),
        )
        session_id = cur.fetchone()[0]
    return str(session_id)


def end_session(session_id: str):
    """Oturumu bitiş zamanıyla kapatır."""
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("UPDATE session SET ended_at = now() WHERE session_id = %s;", (session_id,))


def log_batch(session_id: str, pack_rows: list[tuple], cell_rows: list[tuple]):
    """
    pack_rows: (time, pack_id, pack_voltage, pack_soc, max_temp, cell_delta,
                soh_percent, thermal_state, current_a) listesi
    cell_rows: (time, cell_id, soc, voltage, temp, balancing_active) listesi

    session_id her satırın ikinci kolonuna burada eklenir; çağıran tarafın
    oturum kimliğini tekrar tekrar taşıması gerekmez.
    """
    expected_pack_len = len(PACK_COLUMNS) - 1   # session_id hariç
    expected_cell_len = len(CELL_COLUMNS) - 1

    for row in pack_rows:
        if len(row) != expected_pack_len:
            raise ValueError(
                f"pack_rows satırı {expected_pack_len} alan içermeli, {len(row)} geldi: {row!r}"
            )
    for row in cell_rows:
        if len(row) != expected_cell_len:
            raise ValueError(
                f"cell_rows satırı {expected_cell_len} alan içermeli, {len(row)} geldi: {row!r}"
            )

    if not pack_rows and not cell_rows:
        return

    with get_connection() as conn, conn.cursor() as cur:
        if pack_rows:
            cur.executemany(
                _insert_statement("pack_reading", PACK_COLUMNS),
                [(row[0], session_id, *row[1:]) for row in pack_rows],
            )
        if cell_rows:
            cur.executemany(
                _insert_statement("cell_reading", CELL_COLUMNS),
                [(row[0], session_id, *row[1:]) for row in cell_rows],
            )


def log_event(
    session_id: str,
    pack_id: str,
    event_type: str,
    severity: str,
    message: str,
    details: dict[str, Any] | None = None,
) -> None:
    """
    Kalıcı bir olay kaydı yazar (termal durum geçişi, arıza enjeksiyonu,
    profil değişikliği...).

    Eskiden termal durum yalnızca `pack_reading` satırındaki anlık bir kolondu;
    SHUTDOWN'a girip çıkıldığında geriye dönük hiçbir iz kalmıyordu. Bu tablo,
    "ne zaman ne oldu" sorusunu cevaplanabilir kılar.
    """
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO event (time, session_id, pack_id, event_type, severity, message, details)
            VALUES (now(), %s, %s, %s, %s, %s, %s);
            """,
            (session_id, pack_id, event_type, severity, message, Jsonb(details or {})),
        )

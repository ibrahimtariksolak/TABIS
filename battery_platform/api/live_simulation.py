"""
Arka planda sürekli çalışan batarya simülasyonu.
Her adımda: 1) pack fiziğini ilerletir 2) WebSocket ile canlı yayınlar
3) belirli aralıklarla veritabanına toplu yazar.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

from battery_platform.api.simulation_state import sim_state
from battery_platform.config import settings
from battery_platform.db.connection import run_db
from battery_platform.db.writer import create_session, end_session, log_batch
from battery_platform.simulator.driving_profile import DrivingStyle, generate_current_profile
from battery_platform.simulator.pack import BatteryPack

logger = logging.getLogger(__name__)

DT = settings.sim_dt_seconds
FLUSH_EVERY = settings.db_flush_every_n_steps


async def run_live_simulation(manager, pack_id: str, style_value: str, *, enable_db: bool = True):
    style = DrivingStyle(style_value)
    pack = BatteryPack.create(pack_id=pack_id, cell_count=settings.default_cell_count)

    session_id: str | None = None
    if enable_db:
        session_id = await run_db(create_session, pack_id=pack_id, driving_style=style.value)
        logger.info("Oturum başlatıldı: %s", session_id)

    sim_state.set_pack(pack, session_id or "", style)

    pack_rows: list[tuple] = []
    cell_rows: list[tuple] = []
    profile_iter: iter = iter([])

    try:
        while True:
            new_style = sim_state.consume_style_change()
            if new_style is not None:
                style = new_style
                profile_iter = iter([])
                logger.info("Profil değişti: %s", style.value)

            try:
                current = next(profile_iter)
            except StopIteration:
                profile_iter = iter(generate_current_profile(30, style=style))
                current = next(profile_iter)

            pack.step(current_a=current, dt_seconds=DT)
            sim_state.increment_step()
            now = datetime.now(timezone.utc)

            await manager.broadcast(pack.to_dict())

            if enable_db:
                pack_rows.append((
                    now, pack.pack_id, pack.pack_voltage, pack.pack_soc,
                    pack.max_temperature, pack.cell_voltage_delta,
                    pack.soh_estimator.soh_percent,
                    pack.thermal_protection.state.value,
                    current,
                ))
                for cell in pack.cells:
                    cell_rows.append((
                        now, cell.cell_id, cell.soc, cell.voltage,
                        cell.temperature_c, cell.balancing_active,
                    ))

                if sim_state.step_count % FLUSH_EVERY == 0:
                    rows_p, rows_c = pack_rows, cell_rows
                    pack_rows, cell_rows = [], []
                    await run_db(log_batch, session_id, rows_p, rows_c)

            await asyncio.sleep(DT)

    except asyncio.CancelledError:
        if enable_db and (pack_rows or cell_rows):
            await run_db(log_batch, session_id, pack_rows, cell_rows)
        if enable_db and session_id:
            await run_db(end_session, session_id)
            logger.info("Oturum kapatıldı: %s", session_id)
        raise

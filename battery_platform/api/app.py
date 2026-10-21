"""
Batarya telemetri backend API'si.
FastAPI ile hem REST endpoint'leri hem de WebSocket ile canlı veri akışı sunar.
"""

from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from battery_platform import __version__
from battery_platform.api.live_simulation import run_live_simulation
from battery_platform.api.routes import bms, events, ml, simulation, telemetry
from battery_platform.api.schemas import HealthCheck
from battery_platform.api.ws_manager import ConnectionManager
from battery_platform.config import settings
from battery_platform.db.connection import close_pool

logger = logging.getLogger(__name__)

manager = ConnectionManager()
_simulation_task: asyncio.Task | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _simulation_task

    enable_db = settings.database_url is not None
    if not enable_db:
        logger.warning("DATABASE_URL tanımlı değil — simülasyon DB'siz çalışacak.")

    _simulation_task = asyncio.create_task(
        run_live_simulation(
            manager,
            pack_id=settings.default_pack_id,
            style_value=settings.default_driving_style,
            enable_db=enable_db,
        )
    )
    yield
    if _simulation_task:
        _simulation_task.cancel()
        try:
            await _simulation_task
        except asyncio.CancelledError:
            pass
    close_pool()


app = FastAPI(
    title="Batarya Sağlık ve Telemetri API",
    description="Savunma sanayii ve İKA uygulamaları için batarya izleme sistemi",
    version=__version__,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(telemetry.router)
app.include_router(bms.router)
app.include_router(ml.router)
app.include_router(simulation.router)
app.include_router(events.router)


@app.get("/healthz", response_model=HealthCheck, tags=["system"])
def healthz():
    return {"status": "ok", "version": __version__}


@app.websocket("/ws/telemetry")
async def websocket_telemetry(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)

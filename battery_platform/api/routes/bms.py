from fastapi import APIRouter, HTTPException, Query

from battery_platform.api.schemas import BmsStatus
from battery_platform.db.reader import get_latest_cell_status, get_latest_pack_reading

router = APIRouter(prefix="/bms", tags=["bms"])


@router.get("/status", response_model=BmsStatus)
def bms_status(pack_id: str = Query(..., description="Pack ID, ör. PACK-1")):
    reading = get_latest_pack_reading(pack_id)
    if reading is None:
        raise HTTPException(status_code=404, detail=f"'{pack_id}' için veri bulunamadı.")
    cells = get_latest_cell_status(pack_id)
    return {
        "pack_id": pack_id,
        "time": reading["time"],
        "soh_percent": reading["soh_percent"],
        "thermal_state": reading["thermal_state"],
        "cell_voltage_delta": reading["cell_voltage_delta"],
        "cells": cells,
    }

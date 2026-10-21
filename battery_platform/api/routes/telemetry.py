from fastapi import APIRouter, HTTPException, Query

from battery_platform.api.schemas import PackReadingDB
from battery_platform.db.reader import get_latest_pack_reading, get_pack_history

router = APIRouter(prefix="/telemetry", tags=["telemetry"])


@router.get("/latest", response_model=PackReadingDB)
def telemetry_latest(pack_id: str = Query(..., description="Pack ID, ör. PACK-1")):
    reading = get_latest_pack_reading(pack_id)
    if reading is None:
        raise HTTPException(status_code=404, detail=f"'{pack_id}' için veri bulunamadı.")
    return reading


@router.get("/history", response_model=list[PackReadingDB])
def telemetry_history(
    pack_id: str = Query(..., description="Pack ID, ör. PACK-1"),
    limit: int = Query(100, ge=1, le=5000),
):
    return get_pack_history(pack_id, limit)

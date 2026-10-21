from fastapi import APIRouter, Query

from battery_platform.api.schemas import EventRecord
from battery_platform.db.reader import get_events

router = APIRouter(prefix="/events", tags=["events"])


@router.get("/", response_model=list[EventRecord])
def list_events(
    pack_id: str = Query(..., description="Pack ID, ör. PACK-1"),
    limit: int = Query(50, ge=1, le=500),
):
    return get_events(pack_id, limit)

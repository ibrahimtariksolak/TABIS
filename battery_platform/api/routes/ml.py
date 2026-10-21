from fastapi import APIRouter, HTTPException, Query

from battery_platform.api.schemas import DrivingStyleResult
from battery_platform.db.reader import get_latest_session_id, get_session_current_temp_series
from battery_platform.ml.predict import generate_recommendation, predict_driving_style

router = APIRouter(prefix="/ml", tags=["ml"])


@router.get("/driving-style", response_model=DrivingStyleResult)
def driving_style(pack_id: str = Query(..., description="Pack ID, ör. PACK-1")):
    session_id = get_latest_session_id(pack_id)
    if session_id is None:
        raise HTTPException(status_code=404, detail=f"'{pack_id}' için oturum bulunamadı.")

    currents, temps = get_session_current_temp_series(session_id)
    if len(currents) < 30:
        raise HTTPException(
            status_code=400,
            detail=f"Analiz için yeterli veri yok ({len(currents)} okuma, en az 30 gerekli).",
        )

    prediction = predict_driving_style(currents, temps)
    recommendation = generate_recommendation(prediction)

    return {
        "pack_id": pack_id,
        "session_id": session_id,
        "sample_count": len(currents),
        "driving_style": prediction["style"],
        "features": prediction["features"],
        "recommendation": recommendation,
    }

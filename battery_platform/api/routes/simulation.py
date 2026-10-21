"""
Canlı simülasyona runtime müdahale endpoint'leri.

Arıza enjeksiyonu, profil değiştirme ve simülasyon durumu sorgulama.
"""

from fastapi import APIRouter, HTTPException

from battery_platform.api.schemas import (
    ChangeProfileRequest,
    ClearFaultRequest,
    InjectFaultRequest,
    SimState,
)
from battery_platform.api.simulation_state import sim_state
from battery_platform.simulator.driving_profile import DrivingStyle
from battery_platform.simulator.faults import FaultSpec, FaultType

router = APIRouter(prefix="/sim", tags=["simulation"])


def _require_pack():
    pack = sim_state.pack
    if pack is None:
        raise HTTPException(status_code=503, detail="Simülasyon henüz başlamadı.")
    return pack


@router.get("/state", response_model=SimState)
def get_sim_state():
    pack = _require_pack()
    return {
        "pack_id": pack.pack_id,
        "driving_style": sim_state.driving_style.value,
        "step_count": sim_state.step_count,
        "faults": pack.fault_injector.to_dict(),
        "thermal_state": pack.thermal_protection.state.value,
        "pack_soc": pack.pack_soc,
        "max_temperature_c": pack.max_temperature,
        "soh_percent": pack.soh_estimator.soh_percent,
    }


@router.post("/fault")
def inject_fault(req: InjectFaultRequest):
    pack = _require_pack()
    try:
        ft = FaultType(req.fault_type)
    except ValueError:
        valid = [t.value for t in FaultType]
        raise HTTPException(status_code=400, detail=f"Geçersiz arıza tipi. Geçerli: {valid}") from None

    try:
        spec = FaultSpec(fault_type=ft, severity=req.severity, cell_index=req.cell_index)
        pack.inject_fault(spec)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from None

    return {"status": "injected", "fault": spec.to_dict(), "all_faults": pack.fault_injector.to_dict()}


@router.delete("/fault")
def clear_fault(req: ClearFaultRequest | None = None):
    pack = _require_pack()
    ft = None
    if req and req.fault_type:
        try:
            ft = FaultType(req.fault_type)
        except ValueError:
            valid = [t.value for t in FaultType]
            raise HTTPException(status_code=400, detail=f"Geçersiz arıza tipi. Geçerli: {valid}") from None

    cleared = pack.clear_faults(ft)
    return {"status": "cleared", "cleared_count": cleared, "all_faults": pack.fault_injector.to_dict()}


@router.post("/profile")
def change_profile(req: ChangeProfileRequest):
    _require_pack()
    try:
        style = DrivingStyle(req.driving_style)
    except ValueError:
        valid = [s.value for s in DrivingStyle]
        raise HTTPException(status_code=400, detail=f"Geçersiz stil. Geçerli: {valid}") from None

    sim_state.change_style(style)
    return {"status": "changed", "driving_style": style.value}


@router.post("/reset-thermal")
def reset_thermal():
    pack = _require_pack()
    pack.reset_thermal_protection()
    return {"status": "reset", "thermal_state": pack.thermal_protection.state.value}

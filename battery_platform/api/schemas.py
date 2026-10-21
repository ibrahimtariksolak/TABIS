"""Pydantic response/request şemaları — /docs otomatik doldurulur."""

from __future__ import annotations

from pydantic import BaseModel, Field

# ---- Telemetri ----

class CellStatus(BaseModel):
    cell_id: str
    soc: float
    voltage: float
    temperature_c: float
    balancing_active: bool


class FaultInfo(BaseModel):
    fault_type: str
    severity: float
    cell_index: int | None = None
    elapsed_seconds: float = 0.0


class FaultsOverview(BaseModel):
    active_fault_count: int
    sensor_dropout: bool
    faults: list[FaultInfo]


class PackReading(BaseModel):
    pack_id: str
    timestamp: str
    pack_voltage: float
    pack_soc: float
    max_temperature_c: float
    reported_temperature_c: float
    seconds_since_last_reading: float
    cell_voltage_delta: float
    soh_percent: float
    thermal_state: str
    faults: FaultsOverview
    cells: list[CellStatus]


class PackReadingDB(BaseModel):
    time: str
    pack_id: str
    pack_voltage: float | None
    pack_soc: float | None
    max_temperature_c: float | None
    cell_voltage_delta: float | None
    soh_percent: float | None
    thermal_state: str | None
    current_a: float | None = None


# ---- BMS ----

class BmsStatus(BaseModel):
    pack_id: str
    time: str
    soh_percent: float | None
    thermal_state: str | None
    cell_voltage_delta: float | None
    cells: list[CellStatus]


# ---- ML ----

class DrivingFeatures(BaseModel):
    mean_current: float
    std_current: float
    spike_count: int
    temp_rise: float


class DrivingStyleResult(BaseModel):
    pack_id: str
    session_id: str
    sample_count: int
    driving_style: str
    features: DrivingFeatures
    recommendation: str


# ---- Simülasyon kontrol ----

class InjectFaultRequest(BaseModel):
    fault_type: str = Field(
        ...,
        description="cooling_failure | internal_resistance | self_discharge | cell_short | sensor_dropout",
    )
    severity: float = Field(1.0, ge=0.0, le=1.0)
    cell_index: int | None = Field(None, ge=0)


class ClearFaultRequest(BaseModel):
    fault_type: str | None = Field(None, description="Boşsa tüm arızalar temizlenir")


class ChangeProfileRequest(BaseModel):
    driving_style: str = Field(..., description="eco | normal | aggressive")


class SimState(BaseModel):
    pack_id: str
    driving_style: str
    step_count: int
    faults: FaultsOverview
    thermal_state: str
    pack_soc: float
    max_temperature_c: float
    soh_percent: float


# ---- Olay kaydı ----

class EventRecord(BaseModel):
    time: str
    session_id: str | None
    pack_id: str
    event_type: str
    severity: str
    message: str
    details: dict | None = None


# ---- Genel ----

class HealthCheck(BaseModel):
    status: str
    version: str

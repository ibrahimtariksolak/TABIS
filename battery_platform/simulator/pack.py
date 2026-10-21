"""
Batarya paketi ve hücre seviyesinde fizik tabanlı simülatör.
Gerçek bir BMS'in temel davranışını (SoC, sıcaklık, voltaj, pasif dengeleme)
küçük ölçekte taklit eder. Herhangi bir veritabanı veya API'ye bağımlı değildir,
bağımsız test edilebilir.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from datetime import datetime, timezone

from battery_platform.simulator.bms_logic import SoHEstimator, ThermalProtection
from battery_platform.simulator.faults import CellDerating, FaultInjector, FaultSpec, FaultType

# ---- Sabitler (küçük ölçekli bir EV/İKA pack'i baz alınarak) ----
NOMINAL_CELL_CAPACITY_AH = 50.0           # hücre (grubu) başına anma kapasitesi
CELL_FULL_VOLTAGE = 4.2                   # tam dolu OCV
CELL_EMPTY_VOLTAGE = 3.0                  # tam boş OCV
CELL_NOMINAL_INTERNAL_RESISTANCE = 0.015  # ohm - EV ölçeği hücre grubu için daha düşük
AMBIENT_TEMP_C = 25.0
THERMAL_MASS = 150.0                      # sıcaklık değişimini yumuşatan katsayı (J/C benzeri)
COOLING_COEFFICIENT = 0.01                # ortam ile ısı alışverişi hızı
# Bu iki değer, eco/normal/aggressive sürüş profilleriyle 1 saatlik test
# sonucunda sırasıyla ~26C / ~28.5C / ~40C max sıcaklık veren değerler olarak
# küçük bir tarama ile kalibre edildi (bkz. tests/test_pack_physics.py).

_NEUTRAL_DERATING = CellDerating()


def ocv_from_soc(soc: float) -> float:
    """
    SoC (0-1) değerinden açık devre voltajını (OCV) tahmin eder.
    Basitleştirilmiş doğrusal model; gerçek hücrelerde bu eğri S şeklindedir
    ama simülasyon amacıyla doğrusal yaklaşım yeterlidir.
    """
    soc = max(0.0, min(1.0, soc))
    return CELL_EMPTY_VOLTAGE + soc * (CELL_FULL_VOLTAGE - CELL_EMPTY_VOLTAGE)


@dataclass
class Cell:
    cell_id: str
    capacity_ah: float
    internal_resistance: float
    soc: float = 1.0                      # 1.0 = %100 dolu
    temperature_c: float = AMBIENT_TEMP_C
    balancing_active: bool = False
    voltage: float = field(init=False)

    def __post_init__(self):
        self.voltage = round(ocv_from_soc(self.soc), 4)

    def step(
        self,
        current_a: float,
        dt_seconds: float,
        derating: CellDerating = _NEUTRAL_DERATING,
    ):
        """
        current_a > 0 : deşarj (akım çekiliyor)
        current_a < 0 : şarj

        derating: aktif arızaların bu hücreye etkisi (iç direnç çarpanı, soğutma
        kaybı, kaçak akım). Arıza yokken nötr değerlerle çağrılır ve davranış
        arızasız fizikle birebir aynıdır.
        """
        effective_resistance = self.internal_resistance * derating.resistance_multiplier
        # Kaçak akım, hücreyi yükten bağımsız olarak boşaltır; ısıya da katkı verir.
        total_current = current_a + derating.leakage_current_a

        capacity_as = self.capacity_ah * 3600.0
        delta_soc = -(total_current * dt_seconds) / capacity_as
        self.soc = max(0.0, min(1.0, self.soc + delta_soc))

        ocv = ocv_from_soc(self.soc)
        self.voltage = round(ocv - current_a * effective_resistance, 4)

        heat_generated = (total_current ** 2) * effective_resistance
        cooling = (
            COOLING_COEFFICIENT
            * derating.cooling_multiplier
            * (self.temperature_c - AMBIENT_TEMP_C)
        )
        d_temp = (heat_generated / THERMAL_MASS - cooling) * dt_seconds
        self.temperature_c = round(self.temperature_c + d_temp, 3)

    def to_dict(self) -> dict:
        return {
            "cell_id": self.cell_id,
            "soc": round(self.soc, 4),
            "voltage": self.voltage,
            "temperature_c": self.temperature_c,
            "balancing_active": self.balancing_active,
        }


@dataclass
class BatteryPack:
    pack_id: str
    cells: list[Cell]
    balance_threshold_v: float = 0.05     # bu farkın üstünde pasif dengeleme tetiklenir
    soh_estimator: SoHEstimator = field(init=False)
    thermal_protection: ThermalProtection = field(init=False)
    fault_injector: FaultInjector = field(init=False)

    def __post_init__(self):
        self.soh_estimator = SoHEstimator(rated_capacity_ah=NOMINAL_CELL_CAPACITY_AH)
        self.thermal_protection = ThermalProtection()
        self.fault_injector = FaultInjector()
        # Sensör kopması sırasında BMS'in gördüğü son geçerli okuma ve o okumanın
        # üstünden geçen süre. Fail-safe kararı bu ikisine dayanır.
        self._last_valid_temperature_c = self.max_temperature
        self._seconds_since_last_reading = 0.0

    @classmethod
    def create(cls, pack_id: str, cell_count: int = 8, seed: int | None = None) -> BatteryPack:
        rng = random.Random(seed)
        cells = []
        for i in range(cell_count):
            capacity = NOMINAL_CELL_CAPACITY_AH * rng.uniform(0.97, 1.03)
            resistance = CELL_NOMINAL_INTERNAL_RESISTANCE * rng.uniform(0.9, 1.1)
            initial_soc = rng.uniform(0.95, 1.0)
            cells.append(Cell(
                cell_id=f"{pack_id}-C{i + 1}",
                capacity_ah=capacity,
                internal_resistance=resistance,
                soc=initial_soc,
            ))
        return cls(pack_id=pack_id, cells=cells)

    # ---- arıza yönetimi ----

    def inject_fault(self, spec: FaultSpec) -> FaultSpec:
        return self.fault_injector.inject(spec, cell_count=len(self.cells))

    def clear_faults(self, fault_type: FaultType | None = None) -> int:
        cleared = self.fault_injector.clear(fault_type)
        if not self.fault_injector.is_sensor_dropout_active:
            # Sensör geri geldi: sayaç sıfırlanır, ama SHUTDOWN kalıcıdır -
            # ondan çıkış yalnızca açık bir reset ile olur.
            self._seconds_since_last_reading = 0.0
        return cleared

    # ---- simülasyon ----

    def step(self, current_a: float, dt_seconds: float):
        """
        Paketi bir adım ilerletir: hücre fiziği -> pasif dengeleme -> SoH ->
        termal koruma. Sensör kopması aktifse termal korumaya bayat okuma ve
        artan bir "son okumadan beri geçen süre" gider; bu da timeout eşiğini
        aştığında fail-safe SHUTDOWN tetiklenir.
        """
        self.fault_injector.tick(dt_seconds)

        for index, cell in enumerate(self.cells):
            cell.balancing_active = False
            cell.step(current_a, dt_seconds, self.fault_injector.derating_for(index))

        self._apply_passive_balancing()
        self.soh_estimator.update(current_a, dt_seconds)

        if self.fault_injector.is_sensor_dropout_active:
            self._seconds_since_last_reading += dt_seconds
        else:
            self._last_valid_temperature_c = self.max_temperature
            self._seconds_since_last_reading = 0.0

        self.thermal_protection.update(
            self._last_valid_temperature_c,
            self._seconds_since_last_reading,
        )

    def reset_thermal_protection(self):
        """Kalıcı SHUTDOWN durumundan manuel müdahaleyle çıkışı temsil eder."""
        self._seconds_since_last_reading = 0.0
        self._last_valid_temperature_c = self.max_temperature
        self.thermal_protection.reset()

    def _apply_passive_balancing(self):
        voltages = [c.voltage for c in self.cells]
        v_max, v_min = max(voltages), min(voltages)
        if (v_max - v_min) > self.balance_threshold_v:
            max_cell = max(self.cells, key=lambda c: c.voltage)
            max_cell.soc = max(0.0, max_cell.soc - 0.0005)
            max_cell.voltage = round(ocv_from_soc(max_cell.soc), 4)
            max_cell.balancing_active = True

    # ---- türetilmiş ölçümler ----

    @property
    def pack_voltage(self) -> float:
        return round(sum(c.voltage for c in self.cells), 3)

    @property
    def pack_soc(self) -> float:
        return round(min(c.soc for c in self.cells), 4)

    @property
    def max_temperature(self) -> float:
        return round(max(c.temperature_c for c in self.cells), 3)

    @property
    def reported_temperature(self) -> float:
        """
        BMS'in gördüğü sıcaklık. Sensör sağlamken `max_temperature` ile aynıdır;
        kopma sırasında son geçerli okumada donar.
        """
        return self._last_valid_temperature_c

    @property
    def seconds_since_last_reading(self) -> float:
        return round(self._seconds_since_last_reading, 3)

    @property
    def cell_voltage_delta(self) -> float:
        voltages = [c.voltage for c in self.cells]
        return round(max(voltages) - min(voltages), 4)

    def to_dict(self) -> dict:
        return {
            "pack_id": self.pack_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "pack_voltage": self.pack_voltage,
            "pack_soc": self.pack_soc,
            "max_temperature_c": self.max_temperature,
            "reported_temperature_c": self.reported_temperature,
            "seconds_since_last_reading": self.seconds_since_last_reading,
            "cell_voltage_delta": self.cell_voltage_delta,
            "soh_percent": self.soh_estimator.soh_percent,
            "thermal_state": self.thermal_protection.state.value,
            "faults": self.fault_injector.to_dict(),
            "cells": [c.to_dict() for c in self.cells],
        }

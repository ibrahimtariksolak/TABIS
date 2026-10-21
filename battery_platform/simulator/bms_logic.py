"""
Temel BMS (Battery Management System) mantigi: SoH tahmini ve termal koruma
state machine'i. Bu modul BatteryPack'ten bagimsizdir, saf mantik icerir -
boylece ayri test edilebilir (bkz. tests/test_bms_logic.py).
"""

from enum import Enum


class ThermalState(str, Enum):
    NORMAL = "normal"
    WARNING = "warning"
    CRITICAL = "critical"
    SHUTDOWN = "shutdown"


class ThermalProtection:
    """
    Histerezisli bir state machine: sicaklik esiklerine gore durum degistirir.
    Ayni esikte ileri-geri salinmayi (flapping) onlemek icin giris ve cikis
    esikleri kasitli olarak farkli tutulur.
    """

    # Not: bu esikler, kalibre edilmis simulatorun urettigi gercekci sicaklik
    # araligina (Eko ~26C, Normal ~28.5C, Agresif ~40C) gore ayarlanmistir -
    # gercek Li-ion hucrelerin veri sayfalarindaki degerlerden cok daha dusuktur,
    # cunku bu kucuk olcekli simulasyon o kadar yuksek sicakliklara ulasmiyor.
    WARNING_ENTER_C = 35.0
    WARNING_EXIT_C = 32.0
    CRITICAL_ENTER_C = 45.0
    CRITICAL_EXIT_C = 40.0
    SHUTDOWN_ENTER_C = 55.0

    SENSOR_TIMEOUT_SECONDS = 5.0

    def __init__(self):
        self.state = ThermalState.NORMAL

    def update(self, max_temperature_c: float, seconds_since_last_reading: float = 0.0) -> ThermalState:
        """
        Yeni bir sicaklik okumasiyla state machine'i ilerletir.
        seconds_since_last_reading: son gecerli okumadan bu yana gecen sure -
        sensor timeout'u asarsa fail-safe (SHUTDOWN) durumuna gecilir.
        """
        if seconds_since_last_reading > self.SENSOR_TIMEOUT_SECONDS:
            self.state = ThermalState.SHUTDOWN
            return self.state

        if self.state == ThermalState.SHUTDOWN:
            return self.state

        if max_temperature_c >= self.SHUTDOWN_ENTER_C:
            self.state = ThermalState.SHUTDOWN
        elif self.state in (ThermalState.NORMAL, ThermalState.WARNING):
            if max_temperature_c >= self.CRITICAL_ENTER_C:
                self.state = ThermalState.CRITICAL
            elif max_temperature_c >= self.WARNING_ENTER_C:
                self.state = ThermalState.WARNING
            elif max_temperature_c <= self.WARNING_EXIT_C:
                self.state = ThermalState.NORMAL
        elif self.state == ThermalState.CRITICAL:
            if max_temperature_c <= self.CRITICAL_EXIT_C:
                self.state = ThermalState.WARNING

        return self.state

    def reset(self):
        """SHUTDOWN durumundan manuel/harici mudahale ile cikisi temsil eder."""
        self.state = ThermalState.NORMAL


class SoHEstimator:
    """
    Coulomb counting ile toplam akim gecisini (Ah throughput) izler ve
    basit bir ampirik yaslanma modeliyle SoH (State of Health) tahmini uretir.
    """

    FADE_PERCENT_PER_EQUIVALENT_CYCLE = 0.05

    def __init__(self, rated_capacity_ah: float):
        self.rated_capacity_ah = rated_capacity_ah
        self.cumulative_throughput_ah = 0.0

    def update(self, current_a: float, dt_seconds: float):
        self.cumulative_throughput_ah += abs(current_a) * dt_seconds / 3600.0

    @property
    def equivalent_cycles(self) -> float:
        return self.cumulative_throughput_ah / (2 * self.rated_capacity_ah)

    @property
    def soh_percent(self) -> float:
        fade = self.equivalent_cycles * self.FADE_PERCENT_PER_EQUIVALENT_CYCLE
        return round(max(0.0, 100.0 - fade), 4)

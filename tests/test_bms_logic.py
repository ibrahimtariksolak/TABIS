"""
ThermalProtection state machine ve SoHEstimator birim testleri.

docs/architecture.md'deki "ayri test edilebilir" iddiasi bu dosyayla desteklenir.
"""

import pytest

from battery_platform.simulator.bms_logic import (
    SoHEstimator,
    ThermalProtection,
    ThermalState,
)


class TestThermalProtection:
    def test_starts_normal(self):
        tp = ThermalProtection()
        assert tp.state == ThermalState.NORMAL

    def test_enters_warning(self):
        tp = ThermalProtection()
        tp.update(36.0)
        assert tp.state == ThermalState.WARNING

    def test_hysteresis_prevents_flapping(self):
        tp = ThermalProtection()
        tp.update(36.0)
        assert tp.state == ThermalState.WARNING
        tp.update(34.0)
        assert tp.state == ThermalState.WARNING
        tp.update(31.0)
        assert tp.state == ThermalState.NORMAL

    def test_enters_critical(self):
        tp = ThermalProtection()
        tp.update(46.0)
        assert tp.state == ThermalState.CRITICAL

    def test_critical_exits_to_warning(self):
        tp = ThermalProtection()
        tp.update(46.0)
        assert tp.state == ThermalState.CRITICAL
        tp.update(39.0)
        assert tp.state == ThermalState.WARNING

    def test_shutdown_is_permanent(self):
        tp = ThermalProtection()
        tp.update(56.0)
        assert tp.state == ThermalState.SHUTDOWN
        tp.update(20.0)
        assert tp.state == ThermalState.SHUTDOWN

    def test_manual_reset_exits_shutdown(self):
        tp = ThermalProtection()
        tp.update(56.0)
        tp.reset()
        assert tp.state == ThermalState.NORMAL

    def test_sensor_timeout_triggers_shutdown(self):
        tp = ThermalProtection()
        tp.update(25.0, seconds_since_last_reading=6.0)
        assert tp.state == ThermalState.SHUTDOWN


class TestSoHEstimator:
    def test_starts_at_100(self):
        est = SoHEstimator(rated_capacity_ah=50.0)
        assert est.soh_percent == 100.0

    def test_degrades_with_throughput(self):
        est = SoHEstimator(rated_capacity_ah=50.0)
        for _ in range(3600):
            est.update(current_a=50.0, dt_seconds=1.0)
        assert est.equivalent_cycles == pytest.approx(0.5, rel=0.01)
        assert est.soh_percent < 100.0

    def test_never_goes_below_zero(self):
        est = SoHEstimator(rated_capacity_ah=50.0)
        for _ in range(10_000_000):
            est.update(current_a=100.0, dt_seconds=1.0)
        assert est.soh_percent == 0.0

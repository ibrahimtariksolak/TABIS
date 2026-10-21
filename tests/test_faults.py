"""
Arıza enjeksiyonu birim testleri.

Her arıza tipinin simülatör fiziğine beklenen etkiyi yaptığını doğrular.
"""

import pytest

from battery_platform.simulator.faults import FaultInjector, FaultSpec, FaultType
from battery_platform.simulator.pack import BatteryPack


def _run_steps(pack: BatteryPack, current: float = 15.0, steps: int = 60):
    for _ in range(steps):
        pack.step(current_a=current, dt_seconds=1.0)


class TestFaultSpec:
    def test_cell_scoped_requires_index(self):
        with pytest.raises(ValueError, match="cell_index zorunlu"):
            FaultSpec(fault_type=FaultType.INTERNAL_RESISTANCE, cell_index=None)

    def test_pack_scoped_rejects_index(self):
        with pytest.raises(ValueError, match="cell_index kabul etmez"):
            FaultSpec(fault_type=FaultType.COOLING_FAILURE, cell_index=0)

    def test_severity_bounds(self):
        with pytest.raises(ValueError, match="0-1"):
            FaultSpec(fault_type=FaultType.COOLING_FAILURE, severity=1.5)


class TestCoolingFailure:
    def test_temperature_rises_faster(self):
        healthy = BatteryPack.create("H", 4, seed=1)
        faulty = BatteryPack.create("F", 4, seed=1)
        faulty.inject_fault(FaultSpec(FaultType.COOLING_FAILURE, severity=1.0))

        _run_steps(healthy, current=25.0, steps=120)
        _run_steps(faulty, current=25.0, steps=120)

        assert faulty.max_temperature > healthy.max_temperature + 3.0


class TestInternalResistance:
    def test_affected_cell_heats_up_more(self):
        pack = BatteryPack.create("IR", 4, seed=1)
        pack.inject_fault(FaultSpec(FaultType.INTERNAL_RESISTANCE, severity=0.8, cell_index=0))
        _run_steps(pack, current=20.0, steps=120)

        temps = [c.temperature_c for c in pack.cells]
        assert temps[0] > max(temps[1:]) + 1.0


class TestSelfDischarge:
    def test_affected_cell_drains_faster(self):
        healthy = BatteryPack.create("H", 4, seed=1)
        faulty = BatteryPack.create("F", 4, seed=1)
        faulty.inject_fault(FaultSpec(FaultType.SELF_DISCHARGE, severity=1.0, cell_index=1))

        _run_steps(healthy, current=10.0, steps=300)
        _run_steps(faulty, current=10.0, steps=300)

        assert faulty.cells[1].soc < healthy.cells[1].soc - 0.005


class TestCellShort:
    def test_causes_rapid_heating_and_drain(self):
        pack = BatteryPack.create("CS", 4, seed=1)
        pack.inject_fault(FaultSpec(FaultType.CELL_SHORT, severity=1.0, cell_index=2))
        _run_steps(pack, current=10.0, steps=120)

        assert pack.cells[2].temperature_c > pack.cells[0].temperature_c + 10.0
        assert pack.cells[2].soc < pack.cells[0].soc


class TestSensorDropout:
    def test_triggers_shutdown_after_timeout(self):
        pack = BatteryPack.create("SEN", 4, seed=1)
        pack.inject_fault(FaultSpec(FaultType.SENSOR_DROPOUT, severity=1.0))

        for _ in range(10):
            pack.step(current_a=10.0, dt_seconds=1.0)

        assert pack.thermal_protection.state.value == "shutdown"
        assert pack.seconds_since_last_reading >= 5.0

    def test_clearing_does_not_auto_exit_shutdown(self):
        pack = BatteryPack.create("SEN2", 4, seed=1)
        pack.inject_fault(FaultSpec(FaultType.SENSOR_DROPOUT, severity=1.0))
        for _ in range(10):
            pack.step(10.0, 1.0)
        pack.clear_faults()
        assert pack.thermal_protection.state.value == "shutdown"

    def test_manual_reset_exits_shutdown(self):
        pack = BatteryPack.create("SEN3", 4, seed=1)
        pack.inject_fault(FaultSpec(FaultType.SENSOR_DROPOUT, severity=1.0))
        for _ in range(10):
            pack.step(10.0, 1.0)
        pack.clear_faults()
        pack.reset_thermal_protection()
        assert pack.thermal_protection.state.value == "normal"


class TestFaultInjector:
    def test_duplicate_fault_updates_severity(self):
        fi = FaultInjector()
        fi.inject(FaultSpec(FaultType.COOLING_FAILURE, severity=0.5), cell_count=4)
        fi.inject(FaultSpec(FaultType.COOLING_FAILURE, severity=0.8), cell_count=4)
        assert len(fi.active_faults) == 1
        assert fi.active_faults[0].severity == 0.8

    def test_clear_by_type(self):
        fi = FaultInjector()
        fi.inject(FaultSpec(FaultType.COOLING_FAILURE, severity=0.5), cell_count=4)
        fi.inject(FaultSpec(FaultType.SELF_DISCHARGE, severity=0.3, cell_index=0), cell_count=4)
        fi.clear(FaultType.COOLING_FAILURE)
        assert len(fi.active_faults) == 1
        assert fi.active_faults[0].fault_type == FaultType.SELF_DISCHARGE

    def test_invalid_cell_index_rejected(self):
        fi = FaultInjector()
        with pytest.raises(ValueError, match="geçersiz"):
            fi.inject(FaultSpec(FaultType.INTERNAL_RESISTANCE, cell_index=10), cell_count=4)

"""
BatteryPack fizik simülasyonu doğrulama testleri.

Eko/Normal/Agresif profiller altında SoC düşüşü ve sıcaklık artışının
beklenen sıra ve aralıkta olduğunu doğrular (eski test_run.py'nin assert'leri).
"""

import pytest

from battery_platform.simulator.driving_profile import DrivingStyle, generate_current_profile
from battery_platform.simulator.pack import BatteryPack

DT = 1.0
STEPS = 3600


def _run_scenario(style: DrivingStyle) -> BatteryPack:
    pack = BatteryPack.create(pack_id="TEST", cell_count=8, seed=42)
    profile = generate_current_profile(STEPS, style=style, seed=42)
    for c in profile:
        pack.step(current_a=c, dt_seconds=DT)
    return pack


@pytest.fixture(scope="module")
def eco_pack():
    return _run_scenario(DrivingStyle.ECO)


@pytest.fixture(scope="module")
def normal_pack():
    return _run_scenario(DrivingStyle.NORMAL)


@pytest.fixture(scope="module")
def aggressive_pack():
    return _run_scenario(DrivingStyle.AGGRESSIVE)


def test_soc_ordering(eco_pack, normal_pack, aggressive_pack):
    assert eco_pack.pack_soc > normal_pack.pack_soc > aggressive_pack.pack_soc


def test_temperature_ordering(eco_pack, aggressive_pack):
    assert aggressive_pack.max_temperature > eco_pack.max_temperature


def test_eco_temperature_range(eco_pack):
    assert 24.0 < eco_pack.max_temperature < 30.0


def test_aggressive_temperature_range(aggressive_pack):
    assert 35.0 < aggressive_pack.max_temperature < 50.0


def test_soh_decreases(aggressive_pack):
    assert aggressive_pack.soh_estimator.soh_percent < 100.0


def test_cell_voltage_delta_reasonable(eco_pack):
    assert eco_pack.cell_voltage_delta < 0.5

"""
Canlı simülasyonun paylaşılan durumu.

Önceki sürümde `BatteryPack` nesnesi `live_simulation.py` içinde lokal
değişkendi — dışarıdan erişilemiyordu. Arıza enjeksiyonu ve profil
değiştirme gibi runtime kontroller pack nesnesine erişim gerektirir;
bu modül o referansı ve ilgili meta-veriyi tutar.
"""

from __future__ import annotations

import threading

from battery_platform.simulator.driving_profile import DrivingStyle
from battery_platform.simulator.pack import BatteryPack


class SimulationState:
    """Canlı simülasyonun thread-safe erişilebilir durumu."""

    def __init__(self):
        self._lock = threading.Lock()
        self.pack: BatteryPack | None = None
        self.driving_style: DrivingStyle = DrivingStyle.NORMAL
        self.session_id: str | None = None
        self.step_count: int = 0
        self._style_changed = False

    def set_pack(self, pack: BatteryPack, session_id: str, style: DrivingStyle):
        with self._lock:
            self.pack = pack
            self.session_id = session_id
            self.driving_style = style
            self.step_count = 0

    def change_style(self, style: DrivingStyle):
        with self._lock:
            self.driving_style = style
            self._style_changed = True

    def consume_style_change(self) -> DrivingStyle | None:
        with self._lock:
            if self._style_changed:
                self._style_changed = False
                return self.driving_style
            return None

    def increment_step(self):
        self.step_count += 1


sim_state = SimulationState()

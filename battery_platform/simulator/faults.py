"""
Arıza enjeksiyonu (fault injection) modülü.

Neden gerekli: simülatör sadece "normal" sürüş profiliyle çalıştığında tepe
sıcaklık ~28.5 C civarında kalıyor, termal korumanın WARNING (35 C) eşiği bile
aşılmıyordu. Yani `ThermalProtection` içindeki CRITICAL / SHUTDOWN dalları ve
sensör timeout fail-safe'i canlı sistemde hiçbir zaman tetiklenmiyor, dolayısıyla
gözlemlenebilir de doğrulanabilir de değildi.

Bu modül, pack fiziğine kontrollü bozulmalar enjekte ederek o kolları
çalıştırılabilir hale getirir. Her arıza, gerçek bir batarya arıza moduna karşılık
gelir:

- ``cooling_failure``       : soğutma devresi/fan arızası -> ısı atılamıyor, sıcaklık kaçıyor
- ``internal_resistance``   : hücre yaşlanması/temas direnci -> daha fazla ısı, voltaj çökmesi
- ``self_discharge``        : hücre içi kaçak akım -> paket dengesizliği büyür
- ``cell_short``            : hücre içi kısa devre -> direnç çöker, hızlı ısınma (en sert mod)
- ``sensor_dropout``        : sıcaklık sensörü hattının kopması -> fail-safe SHUTDOWN

Arızalar saf veri olarak tutulur (``FaultSpec``); fiziği uygulayan taraf
``FaultInjector``dır. Böylece hem API'den serileştirilebilir hem de pack'ten
bağımsız test edilebilir.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class FaultType(str, Enum):
    COOLING_FAILURE = "cooling_failure"
    INTERNAL_RESISTANCE = "internal_resistance"
    SELF_DISCHARGE = "self_discharge"
    CELL_SHORT = "cell_short"
    SENSOR_DROPOUT = "sensor_dropout"


#: Hücre hedefi gerektiren arızalar. Diğerleri paket seviyesinde etki eder.
CELL_SCOPED_FAULTS = frozenset(
    {FaultType.INTERNAL_RESISTANCE, FaultType.SELF_DISCHARGE, FaultType.CELL_SHORT}
)


@dataclass
class FaultSpec:
    """
    Tek bir aktif arıza.

    severity: 0 (etkisiz) - 1 (en sert) arası normalize şiddet. Her arıza tipi
    bunu kendi fiziksel ölçeğine çevirir; böylece API tarafı tek bir anlaşılır
    parametreyle çalışır.

    cell_index: hücre bazlı arızalarda hangi hücrenin bozulduğu (0 tabanlı).
    Paket seviyesindeki arızalarda None.
    """

    fault_type: FaultType
    severity: float = 1.0
    cell_index: int | None = None
    elapsed_seconds: float = field(default=0.0, init=False)

    def __post_init__(self):
        self.fault_type = FaultType(self.fault_type)
        if not 0.0 <= self.severity <= 1.0:
            raise ValueError(f"severity 0-1 aralığında olmalı, {self.severity} verildi.")
        if self.fault_type in CELL_SCOPED_FAULTS:
            if self.cell_index is None:
                raise ValueError(f"'{self.fault_type.value}' arızası için cell_index zorunlu.")
            if self.cell_index < 0:
                raise ValueError("cell_index negatif olamaz.")
        elif self.cell_index is not None:
            raise ValueError(
                f"'{self.fault_type.value}' paket seviyesinde bir arıza, cell_index kabul etmez."
            )

    def to_dict(self) -> dict:
        return {
            "fault_type": self.fault_type.value,
            "severity": round(self.severity, 4),
            "cell_index": self.cell_index,
            "elapsed_seconds": round(self.elapsed_seconds, 1),
        }


@dataclass
class CellDerating:
    """Bir hücreye tek adımda uygulanacak arıza etkileri."""

    resistance_multiplier: float = 1.0
    cooling_multiplier: float = 1.0
    leakage_current_a: float = 0.0


class FaultInjector:
    """
    Aktif arızaları tutar ve her simülasyon adımında hücre bazlı etki katsayıları
    üretir. Fiziği kendisi uygulamaz, sadece "ne kadar bozulmuş" bilgisini verir -
    uygulama BatteryPack'te olur.
    """

    # severity=1 iken ulaşılacak uç değerler. Simülatörün kalibre edilmiş
    # sıcaklık aralığı (eko ~26 C ... agresif ~40 C) göz önüne alınarak,
    # her eşiği sırayla aşabilecek şekilde seçildi.
    MAX_RESISTANCE_MULTIPLIER = 6.0
    SHORT_RESISTANCE_MULTIPLIER = 12.0
    MAX_LEAKAGE_A = 5.0
    SHORT_LEAKAGE_A = 15.0

    def __init__(self):
        self._faults: list[FaultSpec] = []

    # ---- yönetim ----

    def inject(self, spec: FaultSpec, cell_count: int) -> FaultSpec:
        """
        Yeni bir arıza ekler. Aynı tip + aynı hedef için ikinci kez çağrılırsa
        mevcut kaydı günceller (kopya arıza birikmesin diye).
        """
        if spec.cell_index is not None and spec.cell_index >= cell_count:
            raise ValueError(
                f"cell_index {spec.cell_index} geçersiz: paket {cell_count} hücreden oluşuyor "
                f"(geçerli aralık 0-{cell_count - 1})."
            )

        for existing in self._faults:
            if existing.fault_type == spec.fault_type and existing.cell_index == spec.cell_index:
                existing.severity = spec.severity
                return existing

        self._faults.append(spec)
        return spec

    def clear(self, fault_type: FaultType | None = None) -> int:
        """
        Arızaları temizler. fault_type verilmezse hepsini siler.
        Silinen arıza sayısını döner.
        """
        before = len(self._faults)
        if fault_type is None:
            self._faults.clear()
        else:
            wanted = FaultType(fault_type)
            self._faults = [f for f in self._faults if f.fault_type != wanted]
        return before - len(self._faults)

    @property
    def active_faults(self) -> list[FaultSpec]:
        return list(self._faults)

    @property
    def is_sensor_dropout_active(self) -> bool:
        return any(f.fault_type == FaultType.SENSOR_DROPOUT for f in self._faults)

    def tick(self, dt_seconds: float):
        """Aktif arızaların yaşını ilerletir (teşhis/raporlama için)."""
        for fault in self._faults:
            fault.elapsed_seconds += dt_seconds

    # ---- etki hesabı ----

    def derating_for(self, cell_index: int) -> CellDerating:
        """Verilen hücreye bu adımda uygulanacak toplam arıza etkisini hesaplar."""
        derating = CellDerating()

        for fault in self._faults:
            targets_this_cell = fault.cell_index is None or fault.cell_index == cell_index
            if not targets_this_cell:
                continue

            s = fault.severity

            if fault.fault_type == FaultType.COOLING_FAILURE:
                # severity=1 -> soğutma tamamen durur (ısı atılamaz)
                derating.cooling_multiplier *= max(0.0, 1.0 - s)

            elif fault.fault_type == FaultType.INTERNAL_RESISTANCE:
                derating.resistance_multiplier *= 1.0 + s * (self.MAX_RESISTANCE_MULTIPLIER - 1.0)

            elif fault.fault_type == FaultType.SELF_DISCHARGE:
                derating.leakage_current_a += s * self.MAX_LEAKAGE_A

            elif fault.fault_type == FaultType.CELL_SHORT:
                # Kısa devre iki etkiyi birlikte yapar: direnç kaynaklı aşırı ısınma
                # ve hücrenin hızla boşalması.
                derating.resistance_multiplier *= 1.0 + s * (self.SHORT_RESISTANCE_MULTIPLIER - 1.0)
                derating.leakage_current_a += s * self.SHORT_LEAKAGE_A

            # SENSOR_DROPOUT fiziği değiştirmez, sadece ölçümü kesintiye uğratır.

        return derating

    def to_dict(self) -> dict:
        return {
            "active_fault_count": len(self._faults),
            "sensor_dropout": self.is_sensor_dropout_active,
            "faults": [f.to_dict() for f in self._faults],
        }

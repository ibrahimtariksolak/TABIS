"""
Suruş/kullanim senaryolarina gore akim cekis profili ureten yardimci modul.
(Faz 4) K-Means ile siniflandirilacak "Eko / Normal / Agresif" etiketleri
burada zaten temel davranis olarak simule edilir; boylece ML modulu gercekci
ozellikler uzerinde calisir.
"""

import random
from enum import Enum


class DrivingStyle(str, Enum):
    ECO = "eco"
    NORMAL = "normal"
    AGGRESSIVE = "aggressive"


_STYLE_PARAMS = {
    DrivingStyle.ECO: dict(base_current=8.0, noise=1.5, spike_prob=0.02, spike_size=10.0),
    DrivingStyle.NORMAL: dict(base_current=15.0, noise=4.0, spike_prob=0.06, spike_size=20.0),
    DrivingStyle.AGGRESSIVE: dict(base_current=25.0, noise=8.0, spike_prob=0.15, spike_size=40.0),
}


def generate_current_profile(
    duration_steps: int,
    style: DrivingStyle = DrivingStyle.NORMAL,
    seed: int = None,
) -> list[float]:
    """
    Belirli bir suruş stiline gore, her adim icin cekilen akimi (Amper) uretir.
    Pozitif deger desarj (akim cekiliyor) anlamina gelir.
    """
    rng = random.Random(seed)
    params = _STYLE_PARAMS[style]
    profile = []
    current = params["base_current"]

    for _ in range(duration_steps):
        if rng.random() < params["spike_prob"]:
            current = params["base_current"] + params["spike_size"] * rng.uniform(0.5, 1.0)
        else:
            current += (params["base_current"] - current) * 0.3
            current += rng.uniform(-params["noise"], params["noise"])

        current = max(0.0, current)
        profile.append(round(current, 2))

    return profile

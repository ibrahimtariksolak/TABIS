"""
Bir suruş oturumundan K-Means icin ozellik vektoru cikaran modul.
Egitim ve tahmin asamalari ayni tanimini paylasir.
"""

import statistics

SPIKE_THRESHOLD_A = 8.0


def extract_features(current_readings: list, max_temperature_readings: list) -> dict:
    if len(current_readings) < 2:
        raise ValueError("Ozellik cikarimi icin en az 2 okuma gerekli.")

    mean_current = statistics.mean(current_readings)
    std_current = statistics.pstdev(current_readings)

    spike_count = 0
    for i in range(1, len(current_readings)):
        if abs(current_readings[i] - current_readings[i - 1]) > SPIKE_THRESHOLD_A:
            spike_count += 1

    temp_rise = max_temperature_readings[-1] - max_temperature_readings[0]

    return {
        "mean_current": mean_current,
        "std_current": std_current,
        "spike_count": spike_count,
        "temp_rise": temp_rise,
    }


FEATURE_ORDER = ["mean_current", "std_current", "spike_count", "temp_rise"]


def features_to_vector(features: dict) -> list:
    return [features[k] for k in FEATURE_ORDER]

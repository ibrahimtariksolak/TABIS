"""
Egitilmis K-Means modelini yukleyip bir oturumun suruş stilini tahmin eden
ve buna gore kural tabanli bir oneri mesaji ureten modul.
"""

import os

import joblib

from battery_platform.ml.features import extract_features, features_to_vector

_MODEL_CACHE = None
_DEFAULT_MODEL_PATH = os.path.join(os.path.dirname(__file__), "models", "driving_style_model.pkl")


def load_model(path: str = None):
    global _MODEL_CACHE
    if _MODEL_CACHE is None:
        _MODEL_CACHE = joblib.load(path or _DEFAULT_MODEL_PATH)
    return _MODEL_CACHE


def predict_driving_style(current_readings: list, max_temperature_readings: list) -> dict:
    model = load_model()
    feats = extract_features(current_readings, max_temperature_readings)
    vector = features_to_vector(feats)
    vector_scaled = model["scaler"].transform([vector])
    cluster_id = int(model["kmeans"].predict(vector_scaled)[0])
    style = model["cluster_to_style"][cluster_id]

    return {"style": style, "features": feats, "cluster_id": cluster_id}


def generate_recommendation(prediction: dict) -> str:
    style = prediction["style"]
    feats = prediction["features"]

    if style == "aggressive":
        msg = (
            f"Son oturumda agresif bir suruş tarzi tespit edildi "
            f"(ortalama akim {feats['mean_current']:.1f}A, {feats['spike_count']} ani sicrama). "
        )
        if feats["temp_rise"] > 5:
            msg += (
                f"Bu durum batarya sicakligini {feats['temp_rise']:.1f}°C artirdi, "
                f"menzili olumsuz etkileyebilir."
            )
        else:
            msg += "Sicaklik artisi henuz sinirli, ama bu tarz surdurulursa termal yuk birikebilir."
    elif style == "eco":
        msg = (
            f"Ekonomik bir suruş tarzi tespit edildi "
            f"(ortalama akim {feats['mean_current']:.1f}A). "
            f"Bu tarz batarya sagligini korumak icin en uygun kullanim seklidir."
        )
    else:
        msg = (
            f"Normal/dengeli bir suruş tarzi tespit edildi "
            f"(ortalama akim {feats['mean_current']:.1f}A). "
            f"Batarya uzerinde asiri bir yuk olusturmuyor."
        )

    return msg

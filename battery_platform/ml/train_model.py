"""
Sentetik suruş oturumlari uretip K-Means modelini egiten script.
Calistirmak icin: proje kokunde `python -m battery_platform.ml.train_model`
(veya paket kuruluysa `bhp-train`).
"""

import os

import joblib
import numpy as np
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score
from sklearn.preprocessing import StandardScaler

from battery_platform.ml.features import FEATURE_ORDER, extract_features, features_to_vector
from battery_platform.simulator.driving_profile import DrivingStyle, generate_current_profile
from battery_platform.simulator.pack import BatteryPack

SESSION_DURATION_S = 1800
SESSIONS_PER_STYLE = 40

MODEL_DIR = os.path.join(os.path.dirname(__file__), "models")
MODEL_PATH = os.path.join(MODEL_DIR, "driving_style_model.pkl")


def generate_training_data():
    X = []
    true_labels = []

    for style in DrivingStyle:
        for i in range(SESSIONS_PER_STYLE):
            seed = hash((style.value, i)) % (2**31)
            pack = BatteryPack.create(pack_id="TRAIN", cell_count=8, seed=seed)
            profile = generate_current_profile(SESSION_DURATION_S, style=style, seed=seed)

            currents = []
            max_temps = []
            for c in profile:
                pack.step(c, 1.0)
                currents.append(c)
                max_temps.append(pack.max_temperature)

            feats = extract_features(currents, max_temps)
            X.append(features_to_vector(feats))
            true_labels.append(style.value)

    return np.array(X), true_labels


def main():
    os.makedirs(MODEL_DIR, exist_ok=True)

    print("Egitim verisi uretiliyor...")
    X, true_labels = generate_training_data()
    print(f"Toplam {len(X)} oturum uretildi. Ozellikler: {FEATURE_ORDER}")

    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    print("\n--- k secimi icin silhouette skorlari ---")
    for k in [2, 3, 4, 5]:
        km = KMeans(n_clusters=k, random_state=42, n_init=10)
        labels = km.fit_predict(X_scaled)
        score = silhouette_score(X_scaled, labels)
        print(f"k={k} -> silhouette={score:.4f}")

    kmeans = KMeans(n_clusters=3, random_state=42, n_init=10)
    cluster_labels = kmeans.fit_predict(X_scaled)

    cluster_to_style = {}
    for cluster_id in range(3):
        styles_in_cluster = [
            true_labels[i] for i in range(len(true_labels)) if cluster_labels[i] == cluster_id
        ]
        majority_style = max(set(styles_in_cluster), key=styles_in_cluster.count)
        cluster_to_style[cluster_id] = majority_style
        purity = styles_in_cluster.count(majority_style) / len(styles_in_cluster)
        print(f"Kume {cluster_id} -> '{majority_style}' (saflik: {purity:.2%}, "
              f"{len(styles_in_cluster)} ornek)")

    correct = sum(
        1 for i in range(len(true_labels))
        if cluster_to_style[cluster_labels[i]] == true_labels[i]
    )
    accuracy = correct / len(true_labels)
    print(f"\nGenel kume-etiket uyum orani: {accuracy:.2%}")

    joblib.dump({
        "scaler": scaler,
        "kmeans": kmeans,
        "cluster_to_style": cluster_to_style,
        "feature_order": FEATURE_ORDER,
    }, MODEL_PATH)
    print(f"\nModel kaydedildi: {MODEL_PATH}")


if __name__ == "__main__":
    main()

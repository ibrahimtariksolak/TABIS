"""ML özellik çıkarımı testleri."""

import pytest

from battery_platform.ml.features import FEATURE_ORDER, extract_features, features_to_vector


def test_extract_basic():
    currents = [10.0, 12.0, 15.0, 10.0, 25.0]
    temps = [25.0, 25.1, 25.3, 25.5, 26.0]
    feats = extract_features(currents, temps)

    assert feats["mean_current"] == pytest.approx(14.4)
    assert feats["temp_rise"] == pytest.approx(1.0)
    assert feats["spike_count"] >= 0


def test_extract_requires_minimum_readings():
    with pytest.raises(ValueError, match="en az 2"):
        extract_features([10.0], [25.0])


def test_features_to_vector_preserves_order():
    feats = {"mean_current": 1, "std_current": 2, "spike_count": 3, "temp_rise": 4}
    vec = features_to_vector(feats)
    assert vec == [feats[k] for k in FEATURE_ORDER]

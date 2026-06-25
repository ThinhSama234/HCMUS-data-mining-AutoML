"""US4 by-characteristics tests (T025) — tier bucketing + grouped ranking on the fixture."""
import os

from analysis.by_characteristics import (
    balance_tier,
    dim_tier,
    grouped_rankings,
    size_tier,
    with_characteristics,
)
from analysis.load_results import load_results

FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures", "results_sample.csv")


def test_tier_thresholds():
    assert size_tier(1000) == "small"
    assert size_tier(5000) == "medium"
    assert size_tier(2_000_000) == "large"
    assert dim_tier(18) == "low"
    assert dim_tier(20) == "mid"
    assert dim_tier(200) == "high"
    assert balance_tier(0.14) == "imbalanced"
    assert balance_tier(0.30) == "balanced"
    assert balance_tier(None) == "n/a"


def test_with_characteristics_maps_known_tasks():
    df = with_characteristics(load_results(FIXTURE))
    row = df[df["task"] == "credit-g"].iloc[0]
    assert row["size_tier"] == "small"
    assert row["dim_tier"] == "mid"          # 20 features
    assert row["balance_tier"] == "balanced"  # minority 0.30


def test_grouped_rankings_shape_and_groups():
    g = grouped_rankings(load_results(FIXTURE), by="size_tier")
    assert list(g.columns) == ["size_tier", "framework", "avg_rank"]
    # all three fixture datasets are small → a single 'small' group containing every framework
    assert set(g["size_tier"].unique()) == {"small"}
    assert "AutoGluon" in set(g["framework"])


def test_grouped_rankings_rejects_unknown_characteristic():
    import pytest
    with pytest.raises(ValueError):
        grouped_rankings(load_results(FIXTURE), by="bogus")

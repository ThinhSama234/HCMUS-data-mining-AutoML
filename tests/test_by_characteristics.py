"""US4 by-characteristics tests (T025) — tier bucketing + grouped ranking on the fixture."""
import os

import pandas as pd

from analysis.by_characteristics import (
    TASK_META,
    balance_tier,
    dim_tier,
    grouped_rankings,
    load_task_meta,
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
    # pin the curated baseline explicitly so this stays hermetic (default now reads the catalog)
    df = with_characteristics(load_results(FIXTURE), meta=TASK_META)
    row = df[df["task"] == "credit-g"].iloc[0]
    assert row["size_tier"] == "small"
    assert row["dim_tier"] == "mid"          # 20 features
    assert row["balance_tier"] == "balanced"  # minority 0.30


def test_grouped_rankings_shape_and_groups():
    g = grouped_rankings(load_results(FIXTURE), by="size_tier", meta=TASK_META)
    assert list(g.columns) == ["size_tier", "framework", "avg_rank"]
    # all three fixture datasets are small → a single 'small' group containing every framework
    assert set(g["size_tier"].unique()) == {"small"}
    assert "AutoGluon" in set(g["framework"])


def test_grouped_rankings_rejects_unknown_characteristic():
    import pytest
    with pytest.raises(ValueError):
        grouped_rankings(load_results(FIXTURE), by="bogus")


# --- Phase 2: catalog-sourced task metadata (replaces the 5-task hardcode) -----------------

def _fake_catalog(rows):
    """A zero-arg source callable returning a datasets-like DataFrame."""
    return lambda: pd.DataFrame(rows)


def test_load_task_meta_from_injected_catalog_scales_beyond_five():
    src = _fake_catalog([
        {"name": "adult_income", "n_instances": 32561, "n_features": 13, "minority_fraction": 0.24},
        {"name": "forest_cover", "n_instances": 581012, "n_features": 54, "minority_fraction": None},
        {"name": "abalone", "n_instances": 4177, "n_features": 8, "minority_fraction": None},
    ])
    meta = load_task_meta(source=src)
    # catalog datasets are present alongside the curated baseline (no 5-task ceiling)
    assert meta["adult_income"] == (32561, 13, 0.24)
    assert meta["forest_cover"] == (581012, 54, None)
    assert "credit-g" in meta                       # curated baseline still available


def test_load_task_meta_null_chars_keep_curated_baseline():
    # a catalog row with NULL characteristics must not wipe the curated value
    src = _fake_catalog([{"name": "credit-g", "n_instances": None,
                          "n_features": None, "minority_fraction": None}])
    meta = load_task_meta(source=src)
    assert meta["credit-g"] == (1000, 20, 0.30)


def test_load_task_meta_falls_back_on_source_error():
    def boom():
        raise RuntimeError("no DB")
    meta = load_task_meta(source=boom)
    assert meta["credit-g"] == (1000, 20, 0.30)      # bundled TASK_META fallback


def test_with_characteristics_covers_catalog_datasets_offline():
    meta = {"adult_income": (32561, 13, 0.24),
            "forest_cover": (581012, 54, None),
            "abalone": (4177, 8, None)}
    df = pd.DataFrame({"task": ["adult_income", "forest_cover", "abalone"]})
    out = with_characteristics(df, meta=meta).set_index("task")
    assert out.loc["adult_income", "size_tier"] == "medium"   # 32,561 ∈ [2k, 50k)
    assert out.loc["forest_cover", "size_tier"] == "large"    # 581k
    assert out.loc["abalone", "dim_tier"] == "low"            # 8 features
    assert "unknown" not in set(out["size_tier"])             # every dataset resolved

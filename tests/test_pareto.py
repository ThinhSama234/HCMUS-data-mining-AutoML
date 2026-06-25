"""US3 Pareto trade-off tests (T021) — verify frontier selection on the fixture."""
import os

from analysis.load_results import load_results
from analysis.pareto import _pareto_mask, pareto_table

FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures", "results_sample.csv")


def test_pareto_mask_basic():
    # (rank, time), both lower=better. B dominates C; A and B and D on the frontier.
    rank = [1.0, 2.0, 3.0, 4.0]
    time = [0.5, 0.1, 0.2, 0.01]
    assert _pareto_mask(rank, time) == [True, True, False, True]


def test_pareto_table_columns_and_frontier():
    df = load_results(FIXTURE)
    tbl = pareto_table(df).set_index("framework")
    assert {"avg_rank", "predict_s", "pareto"}.issubset(set(pareto_table(df).columns))
    # AutoGluon = most accurate (rank 1) → on frontier; H2OAutoML is dominated by faster+
    # better-ranked flaml → off frontier; constant = fastest → on frontier.
    assert bool(tbl.loc["AutoGluon", "pareto"]) is True
    assert bool(tbl.loc["flaml", "pareto"]) is True
    assert bool(tbl.loc["constantpredictor", "pareto"]) is True
    assert bool(tbl.loc["H2OAutoML", "pareto"]) is False


def test_time_axis_is_median_predict_duration():
    df = load_results(FIXTURE)
    tbl = pareto_table(df).set_index("framework")
    # flaml predict_duration is 0.10 across its tasks → median 0.10
    assert abs(float(tbl.loc["flaml", "predict_s"]) - 0.10) < 1e-9

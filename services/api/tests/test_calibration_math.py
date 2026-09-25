from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from app.services import calibration as cal
from app.services.calibration import (
    Prediction,
    bias,
    bins,
    brier,
    brier_skill,
    brier_unchecked,
    ece,
    overconfidence,
    summary,
    trend,
    worst_calls,
)

T0 = datetime(2026, 1, 1, tzinfo=UTC)
USER = uuid4()


def P(prob, outcome, project_id=None, closed_at=T0, tags=()):
    o = {"yes": 1.0, "no": 0.0, "partial": 0.5}[outcome]
    return Prediction(
        p=prob / 100,
        o=o,
        probability=prob,
        impact=3,
        risk_id=uuid4(),
        project_id=project_id or uuid4(),
        closed_at=closed_at,
        tags=list(tags),
        user_id=USER,
    )


EXAMPLE = [P(80, "yes"), P(30, "no"), P(60, "partial"), P(90, "no"), P(20, "yes")]


def test_brier_unchecked_worked_example():
    assert brier_unchecked(EXAMPLE) == pytest.approx(0.318)


def test_brier_null_under_min_n():
    assert brier(EXAMPLE) is None
    assert brier(EXAMPLE * 2) == pytest.approx(0.318)


def test_brier_skill_against_base_rate():
    # base rate 0.5 -> BS_ref = 0.25 for every outcome in {0,1}; partial contributes 0.
    preds = EXAMPLE * 2
    ref = sum((0.5 - x.o) ** 2 for x in preds) / len(preds)
    assert brier_skill(preds, 0.5) == pytest.approx(1 - 0.318 / ref)
    assert brier_skill(EXAMPLE, 0.5) is None  # under MIN_SCORE_N
    assert brier_skill([P(50, "yes")] * 10, 1.0) is None  # BS_ref == 0


def test_bias_worked_example():
    value, label = bias(EXAMPLE * 2)
    assert value == pytest.approx(0.06)
    assert label == "over_estimates_risk"
    assert bias(EXAMPLE) == (None, None)
    v, lbl = bias([P(20, "yes")] * 10)
    assert v == pytest.approx(-0.8) and lbl == "under_estimates_risk"
    v, lbl = bias([P(50, "partial")] * 10)
    assert v == pytest.approx(0.0) and lbl == "calibrated"


def test_bins_always_ten_and_reliability():
    b = bins(EXAMPLE)
    assert len(b) == 10
    assert [x.index for x in b] == list(range(10))
    assert b[0].range == (0, 9) and b[9].range == (90, 100)
    assert all(not x.reliable for x in b)
    assert b[8].n == 1 and b[8].observed is None and b[8].mean_predicted == pytest.approx(0.8)
    assert b[0].n == 0 and b[0].mean_predicted is None


def test_bins_reliable_when_enough_samples():
    b = bins([P(80, "yes")] * 4 + [P(85, "no")])
    assert b[8].n == 5 and b[8].reliable is True
    assert b[8].observed == pytest.approx(0.8)
    assert b[8].mean_predicted == pytest.approx(0.81)


def test_bins_edge_100_goes_to_last_bin():
    assert bins([P(100, "yes")])[9].n == 1


def test_ece_and_overconfidence_worked_example(monkeypatch):
    monkeypatch.setattr(cal, "MIN_BIN_N", 1)
    b = bins(EXAMPLE)
    assert ece(b) == pytest.approx(0.46)
    value, label = overconfidence(b)
    assert value == pytest.approx(0.26, abs=1e-6)
    assert label == "overconfident"


def test_ece_null_without_reliable_bins():
    b = bins(EXAMPLE)
    assert ece(b) is None
    assert overconfidence(b) == (None, None)


def test_underconfident_label(monkeypatch):
    monkeypatch.setattr(cal, "MIN_BIN_N", 1)
    # Hedging toward 50% while outcomes are extreme.
    b = bins([P(60, "yes")] * 5 + [P(40, "no")] * 5)
    value, label = overconfidence(b)
    assert value < 0 and label == "underconfident"


def test_partial_counts_half():
    assert brier_unchecked([P(50, "partial")]) == 0.0


def test_worst_calls_sorted_by_squared_error():
    worst = worst_calls(EXAMPLE, k=2)
    assert [w.probability for w in worst] == [90, 20]


def _project_preds(err: float, k: int, n: int = 10):
    pid = uuid4()
    closed = T0 + timedelta(days=30 * k)
    prob = round((1 - err) * 100)
    return [P(prob, "yes", project_id=pid, closed_at=closed) for _ in range(n)]


def test_trend_insufficient_then_improving():
    three = sum((_project_preds(e, k) for k, e in enumerate([0.5, 0.4, 0.3])), [])
    t = trend(three)
    assert t.direction == "insufficient_data" and len(t.points) == 3
    assert t.points[0].brier_project == pytest.approx(0.25)
    assert t.points[0].n_rolling == 10 and t.points[0].brier_rolling == pytest.approx(0.25)

    six = sum((_project_preds(e, k) for k, e in enumerate([0.5, 0.4, 0.3, 0.2, 0.1, 0.05])), [])
    t = trend(six)
    assert t.direction == "improving" and t.slope < 0
    assert [pt.n_project for pt in t.points] == [10] * 6
    assert t.points[-1].n_rolling == 30  # capped at ROLLING_N
    assert t.points[-1].brier_cumulative == pytest.approx(brier_unchecked(six))


def test_trend_worsening_and_flat():
    six = sum((_project_preds(e, k) for k, e in enumerate([0.05, 0.1, 0.2, 0.3, 0.4, 0.5])), [])
    assert trend(six).direction == "worsening"
    flat = sum((_project_preds(0.3, k) for k in range(6)), [])
    assert trend(flat).direction == "flat"


def test_trend_orders_by_closed_at_not_input_order():
    late = _project_preds(0.1, 5)
    early = _project_preds(0.5, 0)
    t = trend(late + early)
    assert t.points[0].brier_project == pytest.approx(0.25)


def test_summary_bundles_everything():
    s = summary(EXAMPLE * 2, base_rate=0.5)
    assert s.sample.n_graded == 10 and s.sample.sufficient is True and s.sample.needed == 10
    assert s.brier == pytest.approx(0.318)
    assert s.bias_label == "over_estimates_risk"
    assert len(s.bins) == 10
    assert s.trend.direction == "insufficient_data"
    empty = summary([], base_rate=0.0)
    assert empty.sample.n_graded == 0 and empty.brier is None and empty.bins[0].n == 0

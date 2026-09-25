"""Pure calibration scoring over graded predictions. No database access here.

A "graded prediction" is one participant's probability on one canonical risk whose outcome is
known: p in [0, 1] is what they said, o in {0, 0.5, 1} is what happened (partial counts half).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from statistics import fmean

from app.schemas.calibration import (
    BiasLabel,
    Bin,
    CalibrationSummary,
    ConfidenceLabel,
    Sample,
    Trend,
    TrendPoint,
)

# Thresholds live here, not as magic numbers in the functions.
MIN_SCORE_N = 10  # graded predictions before a Brier score is shown
MIN_BIN_N = 5  # samples per calibration bin before its observed frequency is shown
MIN_TAG_N = 10  # graded predictions per tag before per-tag stats are shown
BIN_COUNT = 10
ROLLING_N = 30  # predictions in the rolling Brier window
TREND_MIN_PTS = 4  # rolling points needed before a trend direction is claimed
TREND_EPS = 0.005  # OLS slope magnitude below which the trend is "flat"
CALIBRATED_EPS = 0.05  # |bias| or |overconfidence| below which we say "calibrated"
BLIND_SPOT_MAX_P = 0.30  # materialized risks predicted below this are blind spots
FALSE_ALARM_MIN_P = 0.70  # non-materialized risks predicted above this are false alarms
CHRONIC_TAG_BIAS = 0.10


@dataclass
class Prediction:
    p: float
    o: float
    probability: int
    impact: int
    risk_id: uuid.UUID
    project_id: uuid.UUID
    closed_at: datetime | None
    tags: list[str] = field(default_factory=list)
    user_id: uuid.UUID | None = None
    statement: str | None = None
    project_title: str | None = None


def brier_unchecked(preds: list[Prediction]) -> float:
    if not preds:
        raise ValueError("brier_unchecked needs at least one prediction")
    return fmean((x.p - x.o) ** 2 for x in preds)


def brier(preds: list[Prediction]) -> float | None:
    return brier_unchecked(preds) if len(preds) >= MIN_SCORE_N else None


def brier_skill(preds: list[Prediction], base_rate: float) -> float | None:
    if len(preds) < MIN_SCORE_N:
        return None
    ref = fmean((base_rate - x.o) ** 2 for x in preds)
    if ref == 0:
        return None
    return 1 - brier_unchecked(preds) / ref


def bin_index(probability: int) -> int:
    return min(probability // 10, BIN_COUNT - 1)


def bins(preds: list[Prediction]) -> list[Bin]:
    groups: dict[int, list[Prediction]] = {i: [] for i in range(BIN_COUNT)}
    for x in preds:
        groups[bin_index(x.probability)].append(x)
    out: list[Bin] = []
    for i in range(BIN_COUNT):
        members = groups[i]
        n = len(members)
        reliable = n >= MIN_BIN_N
        out.append(
            Bin(
                index=i,
                range=(i * 10, 100 if i == BIN_COUNT - 1 else i * 10 + 9),
                n=n,
                mean_predicted=fmean(x.p for x in members) if n else None,
                observed=fmean(x.o for x in members) if reliable else None,
                reliable=reliable,
            )
        )
    return out


def bias(preds: list[Prediction]) -> tuple[float | None, BiasLabel | None]:
    if len(preds) < MIN_SCORE_N:
        return None, None
    value = fmean(x.p for x in preds) - fmean(x.o for x in preds)
    if value > CALIBRATED_EPS:
        return value, "over_estimates_risk"
    if value < -CALIBRATED_EPS:
        return value, "under_estimates_risk"
    return value, "calibrated"


def _reliable(bins_: list[Bin]) -> list[Bin]:
    return [
        b for b in bins_ if b.reliable and b.mean_predicted is not None and b.observed is not None
    ]


def ece(bins_: list[Bin]) -> float | None:
    rel = _reliable(bins_)
    if not rel:
        return None
    total = sum(b.n for b in rel)
    return sum((b.n / total) * abs((b.mean_predicted or 0.0) - (b.observed or 0.0)) for b in rel)


def overconfidence(bins_: list[Bin]) -> tuple[float | None, ConfidenceLabel | None]:
    rel = _reliable(bins_)
    if not rel:
        return None, None
    total = sum(b.n for b in rel)
    value = 0.0
    for b in rel:
        mp = b.mean_predicted or 0.0
        gap = mp - (b.observed or 0.0)
        sign = 1.0 if mp > 0.5 else (-1.0 if mp < 0.5 else 0.0)
        value += (b.n / total) * gap * sign
    if value > CALIBRATED_EPS:
        return value, "overconfident"
    if value < -CALIBRATED_EPS:
        return value, "underconfident"
    return value, "calibrated"


def _ols_slope(values: list[float]) -> float:
    n = len(values)
    xs = list(range(n))
    mx, my = fmean(xs), fmean(values)
    var = sum((x - mx) ** 2 for x in xs)
    if var == 0:
        return 0.0
    return sum((x - mx) * (y - my) for x, y in zip(xs, values, strict=True)) / var


def trend(preds: list[Prediction]) -> Trend:
    by_project: dict[uuid.UUID, list[Prediction]] = {}
    for x in preds:
        by_project.setdefault(x.project_id, []).append(x)
    # Closed projects in closing order; projects graded while still active sort last.
    epoch = datetime.min.replace(tzinfo=UTC)
    ordered = sorted(
        by_project.items(),
        key=lambda kv: (
            kv[1][0].closed_at is None,
            kv[1][0].closed_at or epoch,
            str(kv[0]),
        ),
    )
    history: list[Prediction] = []
    points: list[TrendPoint] = []
    for pid, members in ordered:
        history.extend(members)
        window = history[-ROLLING_N:]
        rolling = brier_unchecked(window) if len(window) >= MIN_SCORE_N else None
        points.append(
            TrendPoint(
                project_id=pid,
                project_title=members[0].project_title,
                closed_at=members[0].closed_at,
                n_project=len(members),
                brier_project=brier_unchecked(members),
                n_rolling=len(window),
                brier_rolling=rolling,
                brier_cumulative=brier_unchecked(history),
            )
        )
    series = [pt.brier_rolling for pt in points if pt.brier_rolling is not None]
    if len(series) < TREND_MIN_PTS:
        return Trend(direction="insufficient_data", slope=None, points=points)
    slope = _ols_slope(series)
    if slope < -TREND_EPS:
        direction = "improving"
    elif slope > TREND_EPS:
        direction = "worsening"
    else:
        direction = "flat"
    return Trend(direction=direction, slope=slope, points=points)


def worst_calls(preds: list[Prediction], k: int = 5) -> list[Prediction]:
    return sorted(preds, key=lambda x: (x.p - x.o) ** 2, reverse=True)[:k]


def summary(preds: list[Prediction], base_rate: float) -> CalibrationSummary:
    bins_ = bins(preds)
    bias_value, bias_label = bias(preds)
    oc_value, oc_label = overconfidence(bins_)
    return CalibrationSummary(
        sample=Sample(
            n_graded=len(preds),
            n_projects=len({x.project_id for x in preds}),
            needed=MIN_SCORE_N,
            sufficient=len(preds) >= MIN_SCORE_N,
        ),
        brier=brier(preds),
        brier_skill=brier_skill(preds, base_rate),
        base_rate=base_rate,
        bias=bias_value,
        bias_label=bias_label,
        ece=ece(bins_),
        overconfidence=oc_value,
        confidence_label=oc_label,
        bins=bins_,
        trend=trend(preds),
    )

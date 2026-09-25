"""Database access for calibration dashboards. All reads go through the graded_predictions view."""

import uuid

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import GradingOutcome
from app.schemas.calibration import (
    BlindSpot,
    MemberStat,
    RecentSurprise,
    SurpriseStats,
    TagCalibration,
    WorkspaceSample,
)
from app.schemas.common import UserRef
from app.services import calibration as cal
from app.services.calibration import Prediction

OUTCOME_BY_VALUE = {1.0: GradingOutcome.yes, 0.5: GradingOutcome.partial, 0.0: GradingOutcome.no}


def outcome_of(o: float) -> GradingOutcome:
    return OUTCOME_BY_VALUE[float(o)]


async def load_predictions(
    db: AsyncSession, workspace_id: uuid.UUID, user_id: uuid.UUID | None = None
) -> list[Prediction]:
    sql = """
        SELECT gp.p, gp.o, gp.probability, gp.impact, gp.risk_id, gp.project_id, gp.closed_at,
               gp.tags, gp.user_id, r.statement, p.title
        FROM graded_predictions gp
        JOIN risks r ON r.id = gp.risk_id
        JOIN projects p ON p.id = gp.project_id
        WHERE gp.workspace_id = :ws
    """
    params: dict[str, object] = {"ws": workspace_id}
    if user_id is not None:
        sql += " AND gp.user_id = :uid"
        params["uid"] = user_id
    sql += " ORDER BY gp.closed_at NULLS LAST, gp.project_id, r.created_at, gp.vote_id"
    rows = await db.execute(text(sql), params)
    return [
        Prediction(
            p=float(p),
            o=float(o),
            probability=int(prob),
            impact=int(impact),
            risk_id=risk_id,
            project_id=project_id,
            closed_at=closed_at,
            tags=list(tags or []),
            user_id=uid,
            statement=statement,
            project_title=title,
        )
        for (
            p,
            o,
            prob,
            impact,
            risk_id,
            project_id,
            closed_at,
            tags,
            uid,
            statement,
            title,
        ) in rows.all()
    ]


async def workspace_base_rate(db: AsyncSession, workspace_id: uuid.UUID) -> float:
    value = await db.scalar(
        text("SELECT avg(o) FROM graded_predictions WHERE workspace_id = :ws"),
        {"ws": workspace_id},
    )
    return float(value) if value is not None else 0.0


async def workspace_sample(
    db: AsyncSession, workspace_id: uuid.UUID, preds: list[Prediction]
) -> WorkspaceSample:
    closed = await db.scalar(
        text(
            "SELECT count(*) FROM projects "
            "WHERE workspace_id = :ws AND status = 'closed' AND archived_at IS NULL"
        ),
        {"ws": workspace_id},
    )
    return WorkspaceSample(
        n_graded=len(preds),
        n_projects_closed=int(closed or 0),
        n_projects_graded=len({x.project_id for x in preds}),
        n_voters=len({x.user_id for x in preds}),
        needed=cal.MIN_SCORE_N,
        sufficient=len(preds) >= cal.MIN_SCORE_N,
    )


_SPOT_SQL = """
    SELECT id, project_id, title, statement, tags, mean_p, o FROM (
        SELECT r.id, r.project_id, p.title, r.statement,
               COALESCE(NULLIF(r.tags, '{{}}'::text[]), p.tags) AS tags,
               r.agg_mean_probability / 100.0 AS mean_p,
               CASE g.outcome WHEN 'yes' THEN 1.0 WHEN 'partial' THEN 0.5 ELSE 0.0 END AS o
        FROM risks r
        JOIN gradings g ON g.risk_id = r.id
        JOIN projects p ON p.id = r.project_id AND p.archived_at IS NULL
        WHERE r.workspace_id = :ws AND r.duplicate_of IS NULL AND r.origin <> 'surprise'
          AND r.agg_mean_probability IS NOT NULL
    ) t
    WHERE {condition}
    ORDER BY {order}
    LIMIT 10
"""


async def _spots(
    db: AsyncSession, workspace_id: uuid.UUID, condition: str, order: str
) -> list[BlindSpot]:
    rows = await db.execute(
        text(_SPOT_SQL.format(condition=condition, order=order)),
        {"ws": workspace_id, "max_p": cal.BLIND_SPOT_MAX_P, "min_p": cal.FALSE_ALARM_MIN_P},
    )
    return [
        BlindSpot(
            risk_id=rid,
            project_id=pid,
            project_title=title,
            statement=statement,
            tags=list(tags or []),
            mean_predicted=float(mean_p),
            outcome=outcome_of(float(o)),
            miss=float(o) - float(mean_p),
        )
        for rid, pid, title, statement, tags, mean_p, o in rows.all()
    ]


async def blind_spots(db: AsyncSession, workspace_id: uuid.UUID) -> list[BlindSpot]:
    return await _spots(db, workspace_id, "o >= 0.5 AND mean_p < :max_p", "(o - mean_p) DESC")


async def false_alarms(db: AsyncSession, workspace_id: uuid.UUID) -> list[BlindSpot]:
    return await _spots(db, workspace_id, "o = 0.0 AND mean_p >= :min_p", "(o - mean_p) ASC")


async def tag_stats(db: AsyncSession, workspace_id: uuid.UUID) -> list[TagCalibration]:
    rows = await db.execute(
        text(
            """
            SELECT tag, count(*) AS n, avg(p) AS mean_p, avg(o) AS observed,
                   avg((p - o) * (p - o)) AS brier
            FROM graded_predictions gp, unnest(gp.tags) AS tag
            WHERE gp.workspace_id = :ws
            GROUP BY tag
            HAVING count(*) >= :min_n
            ORDER BY n DESC, tag
            """
        ),
        {"ws": workspace_id, "min_n": cal.MIN_TAG_N},
    )
    out: list[TagCalibration] = []
    for tag, n, mean_p, observed, brier in rows.all():
        b = float(mean_p) - float(observed)
        chronic = (
            "under" if b < -cal.CHRONIC_TAG_BIAS else ("over" if b > cal.CHRONIC_TAG_BIAS else None)
        )
        out.append(
            TagCalibration(
                tag=tag,
                n=int(n),
                mean_predicted=float(mean_p),
                observed=float(observed),
                bias=b,
                brier=float(brier),
                chronic=chronic,
            )
        )
    return out


async def surprise_stats(db: AsyncSession, workspace_id: uuid.UUID) -> SurpriseStats:
    n_projects = await db.scalar(
        text(
            """
            SELECT count(DISTINCT p.id)
            FROM projects p
            JOIN premortem_sessions s ON s.project_id = p.id AND s.phase = 'sealed'
            JOIN gradings g ON g.project_id = p.id
            WHERE p.workspace_id = :ws AND p.status = 'closed' AND p.archived_at IS NULL
            """
        ),
        {"ws": workspace_id},
    )
    n_surprises = await db.scalar(
        text(
            """
            SELECT count(*) FROM risks r
            JOIN projects p ON p.id = r.project_id AND p.archived_at IS NULL
            WHERE r.workspace_id = :ws AND r.origin = 'surprise'
            """
        ),
        {"ws": workspace_id},
    )
    materialized = await db.scalar(
        text(
            """
            SELECT count(*) FROM risks r
            JOIN gradings g ON g.risk_id = r.id
            JOIN projects p ON p.id = r.project_id AND p.archived_at IS NULL
            WHERE r.workspace_id = :ws AND r.duplicate_of IS NULL AND r.origin <> 'surprise'
              AND g.outcome IN ('yes', 'partial')
            """
        ),
        {"ws": workspace_id},
    )
    recent_rows = await db.execute(
        text(
            """
            SELECT r.id, r.project_id, p.title, r.statement, r.tags
            FROM risks r JOIN projects p ON p.id = r.project_id AND p.archived_at IS NULL
            WHERE r.workspace_id = :ws AND r.origin = 'surprise'
            ORDER BY r.created_at DESC LIMIT 5
            """
        ),
        {"ws": workspace_id},
    )
    s, m, n_p = int(n_surprises or 0), int(materialized or 0), int(n_projects or 0)
    return SurpriseStats(
        rate_per_project=round(s / n_p, 4) if n_p else 0.0,
        share=(s / (s + m)) if (s + m) else None,
        n_surprises=s,
        n_projects=n_p,
        recent=[
            RecentSurprise(
                risk_id=rid,
                project_id=pid,
                project_title=title,
                statement=stmt,
                tags=list(tags or []),
            )
            for rid, pid, title, stmt, tags in recent_rows.all()
        ],
    )


async def member_stats(db: AsyncSession, workspace_id: uuid.UUID) -> list[MemberStat]:
    rows = await db.execute(
        text(
            """
            SELECT u.id, u.email, u.name, count(*) AS n,
                   avg((gp.p - gp.o) * (gp.p - gp.o)) AS brier, avg(gp.p) - avg(gp.o) AS bias
            FROM graded_predictions gp JOIN users u ON u.id = gp.user_id
            WHERE gp.workspace_id = :ws
            GROUP BY u.id, u.email, u.name
            ORDER BY n DESC, u.name
            """
        ),
        {"ws": workspace_id},
    )
    out: list[MemberStat] = []
    for uid, email, name, n, brier, bias in rows.all():
        enough = int(n) >= cal.MIN_SCORE_N
        out.append(
            MemberStat(
                user=UserRef(id=uid, email=email, name=name),
                n_graded=int(n),
                brier=float(brier) if enough else None,
                bias=float(bias) if enough else None,
            )
        )
    return out

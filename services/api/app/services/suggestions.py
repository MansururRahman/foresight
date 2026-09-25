"""History-grounded risk suggestions: similar past projects -> their graded risks -> clusters.

Deterministic by design: tag overlap (Jaccard) plus pg_trgm text similarity picks the source
projects; risks are weighted by how often they actually materialized; near-duplicate statements
are clustered so one suggestion carries its provenance across projects.
"""

from __future__ import annotations

import re
import uuid
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import OUTCOME_VALUE, GradingOutcome, RiskOrigin
from app.schemas.suggestion import (
    Suggestion,
    SuggestionSource,
    SuggestionsOut,
    SuggestionsQueryEcho,
)

W_TAG = 0.6
W_TEXT = 0.4
MIN_PROJECT_SIM = 0.15
MAX_SOURCE_PROJECTS = 20
ALPHA = 0.2  # floor so never-materialized risks can still surface at low weight
CLUSTER_SIM = 0.55
TRGM_PREFILTER_THRESHOLD = 0.1

_NON_WORD = re.compile(r"[^a-z0-9]+")


def _trigrams(s: str) -> set[str]:
    words = [w for w in _NON_WORD.split(s.lower()) if w]
    grams: set[str] = set()
    for w in words:
        padded = f"  {w} "
        for i in range(len(padded) - 2):
            grams.add(padded[i : i + 3])
    return grams


def trigram_similarity(a: str, b: str) -> float:
    """pg_trgm-compatible similarity: words padded '  w ', 3-grams, Jaccard over the sets."""
    ta, tb = _trigrams(a), _trigrams(b)
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


@dataclass
class SourceItem:
    risk_id: uuid.UUID
    project_id: uuid.UUID
    project_title: str
    project_similarity: float
    statement: str
    tags: list[str]
    o: float
    mean_predicted: float | None
    origin: str
    closed_at: datetime | None

    @property
    def weight(self) -> float:
        return self.project_similarity * (ALPHA + (1 - ALPHA) * self.o)


@dataclass
class Cluster:
    statement: str
    members: list[SourceItem] = field(default_factory=list)

    @property
    def occurrences(self) -> int:
        return len(self.members)

    @property
    def score(self) -> float:
        return sum(m.weight for m in self.members)

    @property
    def materialization_rate(self) -> float:
        return sum(m.o for m in self.members) / len(self.members)

    @property
    def mean_predicted(self) -> float | None:
        known = [m.mean_predicted for m in self.members if m.mean_predicted is not None]
        return sum(known) / len(known) if known else None

    @property
    def tags(self) -> list[str]:
        counts = Counter(t for m in self.members for t in m.tags)
        return [t for t, _ in counts.most_common(3)]

    @property
    def sources(self) -> list[SourceItem]:
        return sorted(self.members, key=lambda m: m.project_similarity, reverse=True)


def cluster(items: list[SourceItem]) -> list[Cluster]:
    """Greedy clustering by statement similarity; at most one member per project per cluster."""
    clusters: list[Cluster] = []
    for item in sorted(items, key=lambda it: it.weight, reverse=True):
        home = next(
            (c for c in clusters if trigram_similarity(item.statement, c.statement) >= CLUSTER_SIM),
            None,
        )
        if home is None:
            clusters.append(Cluster(statement=item.statement, members=[item]))
        elif all(m.project_id != item.project_id for m in home.members):
            home.members.append(item)
    return sorted(clusters, key=lambda c: c.score, reverse=True)


_SIMILAR_PROJECTS_SQL = """
    WITH q AS (SELECT CAST(:tags AS text[]) AS tags, CAST(:qtext AS text) AS qtext),
    cand AS (
      SELECT p.id, p.title, p.tags, p.closed_at,
             CASE WHEN cardinality(p.tags) = 0 AND cardinality(q.tags) = 0 THEN 0.0
                  ELSE cardinality(ARRAY(SELECT unnest(p.tags) INTERSECT SELECT unnest(q.tags)))::float
                       / NULLIF(cardinality(ARRAY(SELECT unnest(p.tags) UNION SELECT unnest(q.tags))), 0)
             END AS jaccard,
             CASE WHEN q.qtext = '' THEN 0.0 ELSE similarity(p.search_text, q.qtext) END AS text_sim
      FROM projects p, q
      WHERE p.workspace_id = :ws
        AND p.archived_at IS NULL
        AND p.status = 'closed'
        AND (CAST(:exclude AS uuid) IS NULL OR p.id <> CAST(:exclude AS uuid))
        AND (p.tags && q.tags OR (q.qtext <> '' AND p.search_text % q.qtext))
        AND EXISTS (SELECT 1 FROM gradings g WHERE g.project_id = p.id)
    )
    SELECT id, title, tags, closed_at, jaccard, text_sim,
           (:w_tag * COALESCE(jaccard, 0) + :w_text * COALESCE(text_sim, 0)) AS sim
    FROM cand
    WHERE (:w_tag * COALESCE(jaccard, 0) + :w_text * COALESCE(text_sim, 0)) >= :min_sim
    ORDER BY sim DESC, closed_at DESC
    LIMIT :max_projects
"""

_SOURCE_RISKS_SQL = """
    SELECT r.id, r.project_id, r.statement,
           COALESCE(NULLIF(r.tags, '{}'::text[]), p.tags) AS tags,
           r.origin::text, g.outcome::text, r.agg_mean_probability
    FROM risks r
    JOIN gradings g ON g.risk_id = r.id
    JOIN projects p ON p.id = r.project_id
    WHERE r.project_id = ANY(CAST(:project_ids AS uuid[])) AND r.duplicate_of IS NULL
    ORDER BY r.created_at
"""


async def suggest(
    db: AsyncSession,
    workspace_id: uuid.UUID,
    *,
    title: str,
    description: str,
    tags: list[str],
    exclude_project_id: uuid.UUID | None,
    limit: int,
) -> SuggestionsOut:
    qtext = " ".join(f"{title} {description}".split())
    if not qtext and not tags:
        return SuggestionsOut(
            query=SuggestionsQueryEcho(tags=[], matched_projects=0), suggestions=[]
        )

    await db.execute(text(f"SET LOCAL pg_trgm.similarity_threshold = {TRGM_PREFILTER_THRESHOLD}"))
    project_rows = (
        await db.execute(
            text(_SIMILAR_PROJECTS_SQL),
            {
                "tags": tags,
                "qtext": qtext,
                "ws": workspace_id,
                "exclude": exclude_project_id,
                "w_tag": W_TAG,
                "w_text": W_TEXT,
                "min_sim": MIN_PROJECT_SIM,
                "max_projects": MAX_SOURCE_PROJECTS,
            },
        )
    ).all()
    if not project_rows:
        return SuggestionsOut(
            query=SuggestionsQueryEcho(tags=tags, matched_projects=0), suggestions=[]
        )
    projects = {
        row.id: {"title": row.title, "sim": float(row.sim), "closed_at": row.closed_at}
        for row in project_rows
    }

    risk_rows = (
        await db.execute(text(_SOURCE_RISKS_SQL), {"project_ids": list(projects.keys())})
    ).all()
    items = [
        SourceItem(
            risk_id=rid,
            project_id=pid,
            project_title=projects[pid]["title"],
            project_similarity=projects[pid]["sim"],
            statement=statement,
            tags=list(rtags or []),
            o=OUTCOME_VALUE[GradingOutcome(outcome)],
            mean_predicted=float(mean_p) if mean_p is not None else None,
            origin=origin,
            closed_at=projects[pid]["closed_at"],
        )
        for rid, pid, statement, rtags, origin, outcome, mean_p in risk_rows
    ]

    def _outcome(o: float) -> GradingOutcome:
        return {1.0: GradingOutcome.yes, 0.5: GradingOutcome.partial}.get(o, GradingOutcome.no)

    suggestions = [
        Suggestion(
            statement=c.statement,
            score=round(c.score, 6),
            materialization_rate=c.materialization_rate,
            occurrences=c.occurrences,
            mean_predicted_probability=(
                round(c.mean_predicted, 2) if c.mean_predicted is not None else None
            ),
            tags=c.tags,
            sources=[
                SuggestionSource(
                    risk_id=m.risk_id,
                    project_id=m.project_id,
                    project_title=m.project_title,
                    project_similarity=round(m.project_similarity, 4),
                    outcome=_outcome(m.o),
                    mean_predicted_probability=m.mean_predicted,
                    origin=RiskOrigin(m.origin),
                    closed_at=m.closed_at,
                )
                for m in c.sources
            ],
        )
        for c in cluster(items)[:limit]
    ]
    return SuggestionsOut(
        query=SuggestionsQueryEcho(tags=tags, matched_projects=len(projects)),
        suggestions=suggestions,
    )

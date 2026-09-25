import uuid
from datetime import UTC, datetime, timedelta

import pytest

from tests.helpers import create_project, create_workspace


def test_trigram_similarity_matches_pg_trgm_semantics():
    from app.services.suggestions import trigram_similarity

    assert trigram_similarity("Vendor API not ready", "vendor api not ready") == pytest.approx(1.0)
    assert trigram_similarity("Vendor API not ready", "Vendor API not ready!") == pytest.approx(1.0)
    assert trigram_similarity("Vendor API not ready", "Marketing launch slips") < 0.2
    assert trigram_similarity("", "anything") == 0.0
    close = trigram_similarity(
        "Vendor API not ready by integration start", "Vendor API not ready at integration start"
    )
    assert close > 0.55


def test_cluster_merges_similar_statements_one_per_project():
    from app.services.suggestions import SourceItem, cluster

    p1, p2 = uuid.uuid4(), uuid.uuid4()

    def item(pid, statement, o, sim=1.0):
        return SourceItem(
            risk_id=uuid.uuid4(),
            project_id=pid,
            project_title="P",
            project_similarity=sim,
            statement=statement,
            tags=["vendor"],
            o=o,
            mean_predicted=40.0,
            origin="participant",
            closed_at=None,
        )

    clusters = cluster(
        [
            item(p1, "Vendor API not ready by integration start", 1.0),
            item(p2, "Vendor API not ready by the integration start", 0.0),
            # Same project, lower weight: dropped so one project counts once per cluster.
            item(p2, "Vendor API not ready by integration start (again)", 0.0, sim=0.5),
            item(p1, "Marketing launch slips", 0.0),
        ]
    )
    vendor = next(c for c in clusters if "Vendor" in c.statement)
    assert vendor.occurrences == 2
    assert vendor.materialization_rate == pytest.approx(0.5)
    assert {s.project_id for s in vendor.sources} == {p1, p2}
    assert len(clusters) == 2


@pytest.fixture
async def ws(client, user_a):
    return await create_workspace(client, user_a)


async def _closed_project(db, ws_id, uid, title, tags, closed_days_ago, risks):
    """risks: list of (statement, outcome, agg_mean or None, origin)."""
    from app.models import (
        Grading,
        GradingOutcome,
        PremortemSession,
        Project,
        ProjectStatus,
        Risk,
        RiskOrigin,
        SessionPhase,
    )

    closed_at = datetime.now(UTC) - timedelta(days=closed_days_ago)
    project = Project(
        workspace_id=ws_id,
        title=title,
        description="",
        tags=tags,
        created_by=uid,
        status=ProjectStatus.closed,
        closed_at=closed_at,
        closed_by=uid,
    )
    db.add(project)
    await db.flush()
    sess = PremortemSession(
        project_id=project.id,
        workspace_id=ws_id,
        created_by=uid,
        facilitator_id=uid,
        phase=SessionPhase.sealed,
        sealed_at=closed_at,
    )
    db.add(sess)
    await db.flush()
    ids = []
    for statement, outcome, agg_mean, origin in risks:
        is_surprise = origin == "surprise"
        risk = Risk(
            project_id=project.id,
            session_id=None if is_surprise else sess.id,
            workspace_id=ws_id,
            author_id=uid,
            origin=RiskOrigin(origin),
            statement=statement,
            submitted_statement=statement,
            tags=[],
            agg_vote_count=None if agg_mean is None else 2,
            agg_mean_probability=agg_mean,
        )
        db.add(risk)
        await db.flush()
        db.add(
            Grading(
                risk_id=risk.id,
                project_id=project.id,
                graded_by=uid,
                outcome=GradingOutcome(outcome),
            )
        )
        ids.append(risk.id)
    await db.flush()
    return project, ids


@pytest.fixture
async def history(db_session, ws, user_a):
    ws_id, uid = uuid.UUID(ws["id"]), uuid.UUID(user_a["id"])
    p1, r1 = await _closed_project(
        db_session,
        ws_id,
        uid,
        "Payments v2",
        ["vendor"],
        120,
        [
            ("Vendor API not ready by integration start", "yes", 35, "participant"),
            ("Rate limits during load test", "no", 65, "participant"),
        ],
    )
    p2, r2 = await _closed_project(
        db_session,
        ws_id,
        uid,
        "CRM sync",
        ["vendor", "crm"],
        80,
        [("Vendor API not ready by the integration start", "yes", 48, "participant")],
    )
    p3, r3 = await _closed_project(
        db_session,
        ws_id,
        uid,
        "Warehouse API",
        ["vendor", "external"],
        40,
        [
            ("Vendor API not ready at integration start", "no", 40, "participant"),
            ("Contract signature slipped by a month", "yes", None, "surprise"),
        ],
    )
    p4, r4 = await _closed_project(
        db_session,
        ws_id,
        uid,
        "Mobile Launch",
        ["mobile"],
        20,
        [("App store review rejects the build", "yes", 55, "participant")],
    )
    return {"p1": p1, "p2": p2, "p3": p3, "p4": p4, "r1": r1, "r2": r2, "r3": r3, "r4": r4}


async def test_suggestions_for_new_project(client, ws, history, user_a):
    r = await client.post(
        f"/v1/workspaces/{ws['id']}/suggestions",
        json={
            "title": "New vendor integration",
            "description": "Connect billing to a replacement vendor",
            "tags": ["Vendor"],
        },
        headers=user_a["headers"],
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["query"]["tags"] == ["vendor"]
    assert body["query"]["matched_projects"] == 3  # the mobile project is not similar

    top = body["suggestions"][0]
    assert top["statement"].startswith("Vendor API not ready")
    assert top["occurrences"] == 3
    assert top["materialization_rate"] == pytest.approx(2 / 3)
    assert top["mean_predicted_probability"] == pytest.approx((35 + 48 + 40) / 3, abs=0.01)
    assert top["tags"][0] == "vendor"  # most common project tag leads the top-3 list
    sims = [s["project_similarity"] for s in top["sources"]]
    assert sims == sorted(sims, reverse=True)
    assert (
        top["sources"][0]["project_title"] == "Payments v2"
        and top["sources"][0]["outcome"] == "yes"
    )
    assert {s["origin"] for s in top["sources"]} == {"participant"}

    statements = [s["statement"] for s in body["suggestions"]]
    assert "Contract signature slipped by a month" in statements
    surprise = next(s for s in body["suggestions"] if s["statement"].startswith("Contract"))
    assert surprise["sources"][0]["origin"] == "surprise"
    assert surprise["mean_predicted_probability"] is None
    assert "App store review rejects the build" not in statements

    # Materialized risks outrank never-materialized ones from the same projects.
    rate_limits = next(s for s in body["suggestions"] if s["statement"].startswith("Rate limits"))
    assert top["score"] > rate_limits["score"]


async def test_suggestions_exclude_the_project_itself(client, ws, history, user_a, db_session):
    p1 = history["p1"]
    r = await client.get(f"/v1/projects/{p1.id}/suggestions", headers=user_a["headers"])
    assert r.status_code == 200, r.text
    top = r.json()["suggestions"][0]
    assert top["occurrences"] == 2
    assert all(s["project_id"] != str(p1.id) for s in top["sources"])


async def test_suggestions_empty_input_and_no_matches(client, ws, history, user_a):
    r = await client.post(
        f"/v1/workspaces/{ws['id']}/suggestions",
        json={"title": "", "tags": []},
        headers=user_a["headers"],
    )
    assert r.status_code == 200
    assert r.json() == {"query": {"tags": [], "matched_projects": 0}, "suggestions": []}
    r = await client.post(
        f"/v1/workspaces/{ws['id']}/suggestions",
        json={"title": "Quarterly hackathon", "tags": ["fun"]},
        headers=user_a["headers"],
    )
    assert r.status_code == 200 and r.json()["suggestions"] == []


async def test_suggestions_ignore_open_and_archived_projects(
    client, ws, history, user_a, db_session
):
    from app.models import Project

    # An open project with the same tag contributes nothing (not closed, not graded).
    await create_project(client, ws, user_a, title="Open vendor thing", tags=["vendor"])
    # Archive Payments v2: it must drop out of the sources.
    p1 = await db_session.get(Project, history["p1"].id)
    p1.archived_at = datetime.now(UTC)
    await db_session.flush()
    r = await client.post(
        f"/v1/workspaces/{ws['id']}/suggestions",
        json={"title": "Vendor work", "tags": ["vendor"]},
        headers=user_a["headers"],
    )
    body = r.json()
    assert body["query"]["matched_projects"] == 2
    top = body["suggestions"][0]
    assert top["occurrences"] == 2 and all(
        s["project_title"] != "Payments v2" for s in top["sources"]
    )


async def test_suggestions_limit_and_non_member(client, ws, history, user_a, user_b):
    r = await client.post(
        f"/v1/workspaces/{ws['id']}/suggestions",
        json={"title": "Vendor work", "tags": ["vendor"], "limit": 1},
        headers=user_a["headers"],
    )
    assert len(r.json()["suggestions"]) == 1
    r = await client.post(
        f"/v1/workspaces/{ws['id']}/suggestions",
        json={"title": "Vendor work", "tags": ["vendor"]},
        headers=user_b["headers"],
    )
    assert r.status_code == 404

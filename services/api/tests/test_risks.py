import uuid
from datetime import UTC, datetime

import pytest

from tests.helpers import (
    add_member,
    add_risk,
    create_project,
    create_session,
    create_workspace,
    transition,
)


@pytest.fixture
async def ws(client, user_a, user_b, user_c):
    ws = await create_workspace(client, user_a)
    await add_member(client, ws, user_a, user_b)
    await add_member(client, ws, user_a, user_c)  # member, not a participant
    return ws


@pytest.fixture
async def project(client, ws, user_a):
    return await create_project(client, ws, user_a, tags=["vendor"])


@pytest.fixture
async def session_collect(client, project, user_a, user_b):
    return await create_session(client, project, user_a, participant_ids=[user_b["id"]])


async def _risks(client, session, user):
    return await client.get(f"/v1/sessions/{session['id']}/risks", headers=user["headers"])


async def test_collect_is_private_per_participant(client, session_collect, user_a, user_b):
    await add_risk(client, session_collect, user_b, "Finance unavailable for UAT")
    mine = await add_risk(client, session_collect, user_a, "Vendor API not ready")
    assert mine["author"]["id"] == user_a["id"]
    assert mine["origin"] == "participant"

    r = await _risks(client, session_collect, user_a)
    assert r.status_code == 200
    body = r.json()
    assert body["phase"] == "collect"
    assert [x["statement"] for x in body["items"]] == ["Vendor API not ready"]
    counts = {c["user"]["id"]: c["count"] for c in body["submission_counts"]}
    assert counts == {user_a["id"]: 1, user_b["id"]: 1}

    rb = await _risks(client, session_collect, user_b)
    assert [x["statement"] for x in rb.json()["items"]] == ["Finance unavailable for UAT"]
    assert rb.json()["submission_counts"] is None  # only the facilitator sees counts


async def test_non_participant_cannot_submit_or_view_in_collect(client, session_collect, user_c):
    r = await client.post(
        f"/v1/sessions/{session_collect['id']}/risks",
        json={"statement": "Sneaky"},
        headers=user_c["headers"],
    )
    assert r.status_code == 403 and r.json()["error"]["code"] == "not_participant"
    r = await _risks(client, session_collect, user_c)
    assert r.status_code == 403


async def test_statement_length_validated(client, session_collect, user_a):
    r = await client.post(
        f"/v1/sessions/{session_collect['id']}/risks",
        json={"statement": "ab"},
        headers=user_a["headers"],
    )
    assert r.status_code == 422


async def test_author_edits_own_risk_only_in_collect(client, session_collect, user_a, user_b):
    theirs = await add_risk(client, session_collect, user_a, "Vendor API not ready")
    r = await client.patch(
        f"/v1/risks/{theirs['id']}", json={"statement": "Hijacked"}, headers=user_b["headers"]
    )
    assert r.status_code == 404  # not visible to another participant in collect

    r = await client.patch(
        f"/v1/risks/{theirs['id']}",
        json={"statement": "Vendor API late"},
        headers=user_a["headers"],
    )
    assert r.status_code == 200 and r.json()["statement"] == "Vendor API late"

    r = await client.patch(
        f"/v1/risks/{theirs['id']}", json={"tags": ["vendor"]}, headers=user_a["headers"]
    )
    assert r.status_code == 400 and r.json()["error"]["code"] == "field_locked"

    r = await client.delete(f"/v1/risks/{theirs['id']}", headers=user_a["headers"])
    assert r.status_code == 204


async def test_merge_visibility_and_editing(client, session_collect, user_a, user_b):
    ra = await add_risk(client, session_collect, user_a, "Vendor API not ready")
    rb = await add_risk(client, session_collect, user_b, "Vendor API is late")
    await transition(client, session_collect, user_a, "merge")

    r = await _risks(client, session_collect, user_b)
    assert r.status_code == 403 and r.json()["error"]["code"] == "phase_not_visible"

    r = await _risks(client, session_collect, user_a)
    assert r.status_code == 200
    items = {x["id"]: x for x in r.json()["items"]}
    assert items[rb["id"]]["author"]["id"] == user_b["id"]

    # Facilitator edits wording and tags; the original wording is preserved server-side.
    r = await client.patch(
        f"/v1/risks/{rb['id']}",
        json={"statement": "Vendor API late", "tags": ["Vendor", "external"]},
        headers=user_a["headers"],
    )
    assert r.status_code == 200 and r.json()["tags"] == ["vendor", "external"]

    # A participant cannot edit during merge.
    r = await client.patch(
        f"/v1/risks/{ra['id']}", json={"statement": "Late edit attempt"}, headers=user_b["headers"]
    )
    assert r.status_code == 403


async def test_duplicate_marking_rules(client, session_collect, user_a):
    a = await add_risk(client, session_collect, user_a, "Vendor API not ready")
    b = await add_risk(client, session_collect, user_a, "Vendor API is late")
    c = await add_risk(client, session_collect, user_a, "Vendor slips the deadline")
    await transition(client, session_collect, user_a, "merge")

    self_ref = await client.patch(
        f"/v1/risks/{a['id']}", json={"duplicate_of": a["id"]}, headers=user_a["headers"]
    )
    assert self_ref.status_code == 400 and self_ref.json()["error"]["code"] == "invalid_duplicate"

    ok = await client.patch(
        f"/v1/risks/{b['id']}", json={"duplicate_of": a["id"]}, headers=user_a["headers"]
    )
    assert ok.status_code == 200 and ok.json()["duplicate_of"] == a["id"]

    cycle = await client.patch(
        f"/v1/risks/{a['id']}", json={"duplicate_of": b["id"]}, headers=user_a["headers"]
    )
    assert cycle.status_code == 400 and cycle.json()["error"]["code"] == "invalid_duplicate"

    # Chain flattening: C -> B (which is a dup of A) resolves to A.
    flat = await client.patch(
        f"/v1/risks/{c['id']}", json={"duplicate_of": b["id"]}, headers=user_a["headers"]
    )
    assert flat.status_code == 200 and flat.json()["duplicate_of"] == a["id"]

    # Un-mark.
    undo = await client.patch(
        f"/v1/risks/{c['id']}", json={"duplicate_of": None}, headers=user_a["headers"]
    )
    assert undo.status_code == 200 and undo.json()["duplicate_of"] is None

    foreign = await client.patch(
        f"/v1/risks/{c['id']}", json={"duplicate_of": str(uuid.uuid4())}, headers=user_a["headers"]
    )
    assert foreign.status_code == 400


async def test_vote_phase_freezes_and_hides_author(client, session_collect, user_a, user_b):
    a = await add_risk(client, session_collect, user_a, "Vendor API not ready")
    b = await add_risk(client, session_collect, user_b, "Vendor API is late")
    await transition(client, session_collect, user_a, "merge")
    await client.patch(
        f"/v1/risks/{b['id']}", json={"duplicate_of": a["id"]}, headers=user_a["headers"]
    )
    await transition(client, session_collect, user_a, "vote")

    locked = await client.patch(
        f"/v1/risks/{a['id']}", json={"statement": "Late edit attempt"}, headers=user_a["headers"]
    )
    assert locked.status_code == 409 and locked.json()["error"]["code"] == "phase_locked"
    assert (
        await client.delete(f"/v1/risks/{a['id']}", headers=user_a["headers"])
    ).status_code == 409

    r = await _risks(client, session_collect, user_b)
    assert r.status_code == 200
    items = r.json()["items"]
    assert [x["id"] for x in items] == [a["id"]]  # duplicates are not listed
    assert all(x["author"] is None for x in items)
    assert all(x["aggregates"] is None for x in items)
    assert "submission_counts" not in r.json() or r.json()["submission_counts"] is None

    # Facilitator also sees no authors in vote phase.
    rf = await _risks(client, session_collect, user_a)
    assert all(x["author"] is None for x in rf.json()["items"])


async def test_adopt_suggestion_in_merge(client, ws, session_collect, user_a, user_b, db_session):
    from app.models import (
        Grading,
        GradingOutcome,
        PremortemSession,
        Project,
        ProjectStatus,
        Risk,
        SessionPhase,
    )

    # A past, closed project in the same workspace with a graded canonical risk.
    wid, uid = uuid.UUID(ws["id"]), uuid.UUID(user_a["id"])
    past = Project(
        workspace_id=wid,
        title="Payments v2",
        tags=["vendor"],
        created_by=uid,
        status=ProjectStatus.closed,
        closed_at=datetime.now(UTC),
    )
    db_session.add(past)
    await db_session.flush()
    past_sess = PremortemSession(
        project_id=past.id,
        workspace_id=wid,
        created_by=uid,
        facilitator_id=uid,
        phase=SessionPhase.sealed,
        sealed_at=datetime.now(UTC),
    )
    db_session.add(past_sess)
    await db_session.flush()
    src = Risk(
        project_id=past.id,
        session_id=past_sess.id,
        workspace_id=wid,
        author_id=uid,
        statement="Vendor API not ready by integration start",
        submitted_statement="Vendor API not ready by integration start",
        tags=["vendor"],
    )
    db_session.add(src)
    await db_session.flush()
    db_session.add(
        Grading(risk_id=src.id, project_id=past.id, graded_by=uid, outcome=GradingOutcome.yes)
    )
    await db_session.flush()

    await add_risk(client, session_collect, user_a, "Something else")
    # Not allowed during collect.
    r = await client.post(
        f"/v1/sessions/{session_collect['id']}/risks/adopt",
        json={"source_risk_id": str(src.id)},
        headers=user_a["headers"],
    )
    assert r.status_code == 409

    await transition(client, session_collect, user_a, "merge")
    r = await client.post(
        f"/v1/sessions/{session_collect['id']}/risks/adopt",
        json={
            "source_risk_id": str(src.id),
            "statement": "Vendor API not ready for our start date",
        },
        headers=user_a["headers"],
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["origin"] == "suggestion"
    assert body["source_risk_id"] == str(src.id)
    assert body["tags"] == ["vendor"]  # inherited from the source when not given
    assert body["statement"] == "Vendor API not ready for our start date"

    # Participants cannot adopt.
    r = await client.post(
        f"/v1/sessions/{session_collect['id']}/risks/adopt",
        json={"source_risk_id": str(src.id)},
        headers=user_b["headers"],
    )
    assert r.status_code == 403

    # Unknown source.
    r = await client.post(
        f"/v1/sessions/{session_collect['id']}/risks/adopt",
        json={"source_risk_id": str(uuid.uuid4())},
        headers=user_a["headers"],
    )
    assert r.status_code == 404

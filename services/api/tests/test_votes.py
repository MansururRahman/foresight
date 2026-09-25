import json
import uuid

import pytest

from tests.helpers import (
    add_member,
    add_risk,
    create_project,
    create_session,
    create_workspace,
    put_votes,
    transition,
)


def test_aggregate_example():
    from app.services.votes import aggregate

    agg = aggregate([90, 70, 40, 40], [3, 4, 2, 5])
    assert agg is not None
    assert agg.vote_count == 4
    assert agg.mean_probability == pytest.approx(60.0)
    assert agg.median_probability == pytest.approx(55.0)
    assert agg.probability_stddev == pytest.approx(21.21, abs=0.01)  # population stddev
    assert agg.agreement == pytest.approx(0.58, abs=0.01)
    assert agg.mean_impact == pytest.approx(3.5)
    assert agg.risk_score == pytest.approx(2.1)


def test_aggregate_edge_cases():
    from app.services.votes import aggregate

    assert aggregate([], []) is None
    single = aggregate([100], [5])
    assert single is not None and single.probability_stddev == 0 and single.agreement == 1.0
    spread = aggregate([0, 100], [1, 5])
    assert spread is not None and spread.probability_stddev == 50 and spread.agreement == 0.0


@pytest.fixture
async def ws(client, user_a, user_b, user_c):
    ws = await create_workspace(client, user_a)
    await add_member(client, ws, user_a, user_b)
    await add_member(client, ws, user_a, user_c)
    return ws


@pytest.fixture
async def voting(client, ws, user_a, user_b):
    """Session in the vote phase with two canonical risks."""
    project = await create_project(client, ws, user_a)
    session = await create_session(client, project, user_a, participant_ids=[user_b["id"]])
    r1 = await add_risk(client, session, user_a, "Vendor API not ready")
    r2 = await add_risk(client, session, user_b, "Finance unavailable for UAT")
    assert (await transition(client, session, user_a, "merge")).status_code == 200
    assert (await transition(client, session, user_a, "vote")).status_code == 200
    return {"project": project, "session": session, "r1": r1, "r2": r2}


async def test_put_votes_partial_then_update_in_place(client, voting, user_a):
    s, r1, r2 = voting["session"], voting["r1"], voting["r2"]
    r = await put_votes(client, s, user_a, [{"risk_id": r1["id"], "probability": 45, "impact": 3}])
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["required"] == 2
    assert [(v["risk_id"], v["probability"], v["impact"]) for v in body["items"]] == [
        (r1["id"], 45, 3)
    ]

    r = await put_votes(
        client,
        s,
        user_a,
        [
            {"risk_id": r1["id"], "probability": 50, "impact": 4},
            {"risk_id": r2["id"], "probability": 20, "impact": 2},
        ],
    )
    assert r.status_code == 200
    items = {v["risk_id"]: v for v in r.json()["items"]}
    assert (
        len(items) == 2 and items[r1["id"]]["probability"] == 50 and items[r1["id"]]["impact"] == 4
    )

    me = await client.get(f"/v1/sessions/{s['id']}/votes/me", headers=user_a["headers"])
    assert me.status_code == 200 and len(me.json()["items"]) == 2

    sess = await client.get(f"/v1/sessions/{s['id']}", headers=user_a["headers"])
    assert sess.json()["me"]["votes_cast"] == 2 and sess.json()["me"]["votes_required"] == 2
    assert sess.json()["counts"]["voters_complete"] == 1


async def test_put_votes_validation(client, voting, user_a):
    s, r1 = voting["session"], voting["r1"]
    r = await put_votes(client, s, user_a, [{"risk_id": r1["id"], "probability": 101, "impact": 3}])
    assert r.status_code == 422
    r = await put_votes(client, s, user_a, [{"risk_id": r1["id"], "probability": 10, "impact": 0}])
    assert r.status_code == 422
    r = await put_votes(
        client, s, user_a, [{"risk_id": str(uuid.uuid4()), "probability": 10, "impact": 1}]
    )
    assert r.status_code == 400 and r.json()["error"]["code"] == "unknown_risk"


async def test_put_votes_wrong_phase_409(client, ws, user_a, user_b):
    project = await create_project(client, ws, user_a)
    session = await create_session(client, project, user_a, participant_ids=[user_b["id"]])
    r1 = await add_risk(client, session, user_a, "Vendor API not ready")
    r = await put_votes(
        client, session, user_a, [{"risk_id": r1["id"], "probability": 10, "impact": 1}]
    )
    assert r.status_code == 409 and r.json()["error"]["code"] == "phase_locked"


async def test_non_participant_cannot_vote_or_view_own_votes(client, voting, user_c):
    s, r1 = voting["session"], voting["r1"]
    r = await put_votes(client, s, user_c, [{"risk_id": r1["id"], "probability": 10, "impact": 1}])
    assert r.status_code == 403 and r.json()["error"]["code"] == "not_participant"
    r = await client.get(f"/v1/sessions/{s['id']}/votes/me", headers=user_c["headers"])
    assert r.status_code == 403


async def test_votes_are_private_between_participants(client, voting, user_a, user_b):
    s, r1, r2 = voting["session"], voting["r1"], voting["r2"]
    await put_votes(client, s, user_a, [{"risk_id": r1["id"], "probability": 90, "impact": 5}])
    await put_votes(client, s, user_b, [{"risk_id": r1["id"], "probability": 10, "impact": 1}])
    mine = await client.get(f"/v1/sessions/{s['id']}/votes/me", headers=user_b["headers"])
    assert [v["probability"] for v in mine.json()["items"]] == [10]
    risks = await client.get(f"/v1/sessions/{s['id']}/risks", headers=user_b["headers"])
    by_id = {x["id"]: x for x in risks.json()["items"]}
    assert by_id[r1["id"]]["my_vote"] == {"probability": 10, "impact": 1}
    assert by_id[r2["id"]]["my_vote"] is None
    assert '"probability": 90' not in json.dumps(risks.json())


async def test_seal_requires_votes(client, voting, user_a):
    r = await transition(client, voting["session"], user_a, "sealed")
    assert r.status_code == 409 and r.json()["error"]["code"] == "no_votes"


async def test_seal_aggregates_and_reports_incomplete_voters(client, voting, user_a, user_b):
    s, r1, r2 = voting["session"], voting["r1"], voting["r2"]
    await put_votes(
        client,
        s,
        user_a,
        [
            {"risk_id": r1["id"], "probability": 90, "impact": 3},
            {"risk_id": r2["id"], "probability": 40, "impact": 2},
        ],
    )
    await put_votes(client, s, user_b, [{"risk_id": r1["id"], "probability": 70, "impact": 4}])

    r = await transition(client, s, user_a, "sealed")
    assert r.status_code == 200, r.text
    assert r.json()["session"]["phase"] == "sealed"
    assert r.json()["session"]["sealed_at"] is not None
    assert [u["id"] for u in r.json()["incomplete_voters"]] == [user_b["id"]]

    locked = await put_votes(
        client, s, user_a, [{"risk_id": r1["id"], "probability": 1, "impact": 1}]
    )
    assert locked.status_code == 409 and locked.json()["error"]["code"] == "phase_locked"

    results = await client.get(f"/v1/sessions/{s['id']}/results", headers=user_b["headers"])
    assert results.status_code == 200
    body = results.json()
    by_id = {x["id"]: x for x in body["risks"]}
    agg1 = by_id[r1["id"]]["aggregates"]
    assert (
        agg1["vote_count"] == 2
        and agg1["mean_probability"] == 80
        and agg1["median_probability"] == 80
    )
    assert agg1["probability_stddev"] == 10 and agg1["agreement"] == pytest.approx(0.8)
    assert agg1["mean_impact"] == 3.5 and agg1["risk_score"] == pytest.approx(2.8)
    assert by_id[r1["id"]]["histogram"] == [0, 0, 0, 0, 0, 0, 0, 1, 0, 1]
    agg2 = by_id[r2["id"]]["aggregates"]
    assert agg2["vote_count"] == 1 and agg2["probability_stddev"] == 0 and agg2["agreement"] == 1.0
    assert body["participation"] == {
        "participants": 2,
        "voters_complete": 1,
        "voters_partial": 1,
        "voters_none": 0,
    }
    assert by_id[r1["id"]]["my_vote"] == {"probability": 70, "impact": 4}  # user_b's own vote
    assert by_id[r2["id"]]["my_vote"] is None


async def test_results_has_no_user_votes(client, voting, user_a, user_b, user_c):
    s, r1, r2 = voting["session"], voting["r1"], voting["r2"]
    await put_votes(client, s, user_a, [{"risk_id": r1["id"], "probability": 93, "impact": 5}])
    await put_votes(client, s, user_b, [{"risk_id": r1["id"], "probability": 17, "impact": 1}])
    await transition(client, s, user_a, "sealed")

    # A member who did not participate can see aggregates but no individual votes.
    results = await client.get(f"/v1/sessions/{s['id']}/results", headers=user_c["headers"])
    assert results.status_code == 200
    text = json.dumps(results.json())
    assert "user_id" not in text
    # Raw individual probabilities never appear as vote values.
    assert '"probability": 93' not in text and '"probability": 17' not in text
    by_id = {x["id"]: x for x in results.json()["risks"]}
    assert by_id[r1["id"]]["my_vote"] is None
    assert by_id[r1["id"]]["author"] is None

    # Before sealing, results are not available.
    project = await create_project(client, await create_workspace(client, user_a, "Other"), user_a)
    other = await create_session(client, project, user_a)
    r = await client.get(f"/v1/sessions/{other['id']}/results", headers=user_a["headers"])
    assert r.status_code == 409 and r.json()["error"]["code"] == "not_sealed"


async def test_seal_twice_409(client, voting, user_a, db_session):
    """A second sealer working from a stale phase loses the conditional update."""
    from app.models import PremortemSession, User, WorkspaceMember
    from app.services import sessions as sessions_service

    s, r1 = voting["session"], voting["r1"]
    await put_votes(client, s, user_a, [{"risk_id": r1["id"], "probability": 50, "impact": 3}])

    stale = await db_session.get(PremortemSession, uuid.UUID(s["id"]))
    assert stale is not None and stale.phase == "vote"
    user = await db_session.get(User, uuid.UUID(user_a["id"]))
    member = await db_session.get(WorkspaceMember, (stale.workspace_id, user.id))
    db_session.expunge(stale)  # detach: this copy will not see the seal below

    first = await transition(client, s, user_a, "sealed")
    assert first.status_code == 200

    # The stale object still believes the phase is `vote`; the guarded UPDATE must reject it.
    from app.core.errors import AppError

    with pytest.raises(AppError) as exc:
        await sessions_service.transition(db_session, stale, member, user, "sealed")
    assert exc.value.status == 409
    fresh = await client.get(f"/v1/sessions/{s['id']}", headers=user_a["headers"])
    assert fresh.json()["phase"] == "sealed"

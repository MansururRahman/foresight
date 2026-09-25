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


@pytest.fixture
async def ws(client, user_a, user_b, user_c):
    ws = await create_workspace(client, user_a)
    await add_member(client, ws, user_a, user_b)
    await add_member(client, ws, user_a, user_c, role="admin")
    return ws


async def _activate(client, project, user):
    r = await client.post(
        f"/v1/projects/{project['id']}/transition", json={"to": "active"}, headers=user["headers"]
    )
    assert r.status_code == 200, r.text


@pytest.fixture
async def voting(client, ws, user_a, user_b):
    project = await create_project(client, ws, user_a, tags=["vendor"])
    await _activate(client, project, user_a)
    session = await create_session(client, project, user_a, participant_ids=[user_b["id"]])
    r1 = await add_risk(client, session, user_a, "Vendor API not ready by integration start")
    r2 = await add_risk(client, session, user_a, "Finance unavailable for UAT")
    r3 = await add_risk(client, session, user_b, "Stripe sandbox differs from production")
    assert (await transition(client, session, user_a, "merge")).status_code == 200
    assert (await transition(client, session, user_a, "vote")).status_code == 200
    return {"project": project, "session": session, "risks": [r1, r2, r3]}


@pytest.fixture
async def sealed(client, voting, user_a, user_b):
    s, (r1, r2, r3) = voting["session"], voting["risks"]
    await put_votes(
        client,
        s,
        user_a,
        [
            {"risk_id": r1["id"], "probability": 50, "impact": 3},
            {"risk_id": r2["id"], "probability": 20, "impact": 2},
            {"risk_id": r3["id"], "probability": 80, "impact": 4},
        ],
    )
    await put_votes(
        client,
        s,
        user_b,
        [
            {"risk_id": r1["id"], "probability": 40, "impact": 3},
            {"risk_id": r2["id"], "probability": 30, "impact": 2},
            {"risk_id": r3["id"], "probability": 60, "impact": 4},
        ],
    )
    assert (await transition(client, s, user_a, "sealed")).status_code == 200
    return voting


def _g(risk, outcome, note=""):
    return {"risk_id": risk["id"], "outcome": outcome, "note": note}


async def test_grading_before_seal_409(client, voting, user_a):
    p, (r1, *_) = voting["project"], voting["risks"]
    r = await client.put(
        f"/v1/projects/{p['id']}/gradings",
        json={"gradings": [_g(r1, "yes")]},
        headers=user_a["headers"],
    )
    assert r.status_code == 409 and r.json()["error"]["code"] == "session_not_sealed"


async def test_grading_permissions(client, sealed, user_a, user_b, user_c):
    p, (r1, *_) = sealed["project"], sealed["risks"]
    r = await client.put(
        f"/v1/projects/{p['id']}/gradings",
        json={"gradings": [_g(r1, "yes")]},
        headers=user_b["headers"],
    )
    assert r.status_code == 403 and r.json()["error"]["code"] == "facilitator_required"
    r = await client.put(
        f"/v1/projects/{p['id']}/gradings",
        json={"gradings": [_g(r1, "yes")]},
        headers=user_c["headers"],
    )
    assert r.status_code == 200, r.text  # admins may grade


async def test_put_gradings_tracks_fully_graded(client, sealed, user_a):
    p, (r1, r2, r3) = sealed["project"], sealed["risks"]
    r = await client.put(
        f"/v1/projects/{p['id']}/gradings",
        json={"gradings": [_g(r1, "yes", "slipped 3 weeks"), _g(r2, "no")]},
        headers=user_a["headers"],
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["ungraded_count"] == 1
    assert body["session"]["fully_graded_at"] is None
    by_id = {x["id"]: x for x in body["risks"]}
    assert by_id[r1["id"]]["grading"]["outcome"] == "yes"
    assert by_id[r1["id"]]["grading"]["note"] == "slipped 3 weeks"
    assert by_id[r1["id"]]["grading"]["graded_by"]["id"] == user_a["id"]
    assert by_id[r3["id"]]["grading"] is None
    assert by_id[r1["id"]]["aggregates"]["mean_probability"] == 45

    r = await client.put(
        f"/v1/projects/{p['id']}/gradings",
        json={"gradings": [_g(r3, "partial")]},
        headers=user_a["headers"],
    )
    assert r.json()["ungraded_count"] == 0 and r.json()["session"]["fully_graded_at"] is not None

    # Re-grading overwrites in place.
    r = await client.put(
        f"/v1/projects/{p['id']}/gradings",
        json={"gradings": [_g(r1, "no")]},
        headers=user_a["headers"],
    )
    by_id = {x["id"]: x for x in r.json()["risks"]}
    assert by_id[r1["id"]]["grading"]["outcome"] == "no"

    d = await client.delete(f"/v1/gradings/{r3['id']}", headers=user_a["headers"])
    assert d.status_code == 204
    c = await client.get(f"/v1/projects/{p['id']}/closeout", headers=user_a["headers"])
    assert c.json()["ungraded_count"] == 1 and c.json()["session"]["fully_graded_at"] is None


async def test_put_gradings_rejects_unknown_risk(client, sealed, user_a):
    p = sealed["project"]
    r = await client.put(
        f"/v1/projects/{p['id']}/gradings",
        json={"gradings": [{"risk_id": str(uuid.uuid4()), "outcome": "yes"}]},
        headers=user_a["headers"],
    )
    assert r.status_code == 400 and r.json()["error"]["code"] == "unknown_risk"


async def test_surprises_lifecycle(client, sealed, user_a, user_b):
    p = sealed["project"]
    r = await client.post(
        f"/v1/projects/{p['id']}/surprises",
        json={
            "statement": "Legal blocked the data-residency clause",
            "tags": ["Legal", "external"],
        },
        headers=user_a["headers"],
    )
    assert r.status_code == 201, r.text
    s = r.json()
    assert s["origin"] == "surprise" and s["session_id"] is None
    assert s["tags"] == ["legal", "external"]
    assert s["grading"]["outcome"] == "yes"

    c = await client.get(f"/v1/projects/{p['id']}/closeout", headers=user_b["headers"])
    assert [x["id"] for x in c.json()["surprises"]] == [s["id"]]
    assert s["id"] not in {x["id"] for x in c.json()["risks"]}

    # Facilitator edits and removes a surprise through the risk endpoints.
    e = await client.patch(
        f"/v1/risks/{s['id']}",
        json={"statement": "Legal blocked the clause for 3 weeks"},
        headers=user_a["headers"],
    )
    assert e.status_code == 200 and e.json()["statement"] == "Legal blocked the clause for 3 weeks"
    forbidden = await client.patch(
        f"/v1/risks/{s['id']}", json={"statement": "Hijack surprise"}, headers=user_b["headers"]
    )
    assert forbidden.status_code == 403
    d = await client.delete(f"/v1/risks/{s['id']}", headers=user_a["headers"])
    assert d.status_code == 204
    c = await client.get(f"/v1/projects/{p['id']}/closeout", headers=user_a["headers"])
    assert c.json()["surprises"] == []

    # Members cannot add surprises.
    r = await client.post(
        f"/v1/projects/{p['id']}/surprises",
        json={"statement": "Nope nope"},
        headers=user_b["headers"],
    )
    assert r.status_code == 403


async def test_possible_duplicates_flags_near_identical_surprise(client, sealed, user_a):
    p, (r1, *_) = sealed["project"], sealed["risks"]
    r = await client.post(
        f"/v1/projects/{p['id']}/surprises",
        json={"statement": "Vendor API not ready by the integration start"},
        headers=user_a["headers"],
    )
    assert r.status_code == 201
    c = await client.get(f"/v1/projects/{p['id']}/closeout", headers=user_a["headers"])
    dups = c.json()["possible_duplicates"]
    assert len(dups) == 1
    assert dups[0]["surprise_id"] == r.json()["id"] and dups[0]["risk_id"] == r1["id"]
    assert dups[0]["similarity"] > 0.5


async def test_report_numbers(client, sealed, user_a):
    p, (r1, r2, r3) = sealed["project"], sealed["risks"]
    # means: r1 45%, r2 25%, r3 70%
    await client.put(
        f"/v1/projects/{p['id']}/gradings",
        json={"gradings": [_g(r1, "yes"), _g(r2, "no"), _g(r3, "partial")]},
        headers=user_a["headers"],
    )
    await client.post(
        f"/v1/projects/{p['id']}/surprises",
        json={"statement": "Legal blocked the clause"},
        headers=user_a["headers"],
    )
    rep = await client.get(f"/v1/projects/{p['id']}/report", headers=user_a["headers"])
    assert rep.status_code == 200, rep.text
    body = rep.json()
    summary = body["summary"]
    assert summary["n_canonical"] == 3 and summary["n_graded"] == 3 and summary["n_voters"] == 2
    assert summary["expected_materialized"] == pytest.approx(0.45 + 0.25 + 0.70)
    assert summary["actual_materialized"] == pytest.approx(1.5)
    assert summary["n_predictions"] == 6
    # Brier over the 6 votes: (0.5-1)^2+(0.4-1)^2+(0.2-0)^2+(0.3-0)^2+(0.8-0.5)^2+(0.6-0.5)^2 = 0.25+0.36+0.04+0.09+0.09+0.01 = 0.84 / 6
    assert summary["project_brier"] == pytest.approx(0.14, abs=1e-6)
    risks = {x["risk_id"]: x for x in body["risks"]}
    assert risks[r1["id"]]["miss"] == pytest.approx(1 - 0.45)
    assert risks[r2["id"]]["miss"] == pytest.approx(0 - 0.25)
    assert body["biggest_misses"][0]["risk_id"] == r1["id"]
    assert [s["statement"] for s in body["surprises"]] == ["Legal blocked the clause"]


async def test_close_project_warns_about_ungraded(client, sealed, user_a):
    p, (r1, *_) = sealed["project"], sealed["risks"]
    await client.put(
        f"/v1/projects/{p['id']}/gradings",
        json={"gradings": [_g(r1, "yes")]},
        headers=user_a["headers"],
    )
    r = await client.post(
        f"/v1/projects/{p['id']}/transition", json={"to": "closed"}, headers=user_a["headers"]
    )
    assert r.status_code == 200
    assert r.json()["warnings"] == [{"code": "ungraded_risks", "count": 2}]
    # Grading remains possible after close.
    r = await client.put(
        f"/v1/projects/{p['id']}/gradings",
        json={"gradings": [_g(sealed["risks"][1], "no")]},
        headers=user_a["headers"],
    )
    assert r.status_code == 200 and r.json()["ungraded_count"] == 1


async def test_closeout_for_project_without_session(client, ws, user_a):
    p = await create_project(client, ws, user_a)
    c = await client.get(f"/v1/projects/{p['id']}/closeout", headers=user_a["headers"])
    assert c.status_code == 200
    assert (
        c.json()["session"] is None and c.json()["risks"] == [] and c.json()["ungraded_count"] == 0
    )
    r = await client.put(
        f"/v1/projects/{p['id']}/gradings",
        json={"gradings": [{"risk_id": str(uuid.uuid4()), "outcome": "yes"}]},
        headers=user_a["headers"],
    )
    assert r.status_code == 409 and r.json()["error"]["code"] == "no_session"

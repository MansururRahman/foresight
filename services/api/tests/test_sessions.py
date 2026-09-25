import uuid

import pytest

from tests.helpers import (
    add_member,
    add_risk,
    create_project,
    create_session,
    create_workspace,
    register,
    transition,
)


@pytest.fixture
async def ws(client, user_a, user_b):
    ws = await create_workspace(client, user_a)
    await add_member(client, ws, user_a, user_b)
    return ws


@pytest.fixture
async def project(client, ws, user_a):
    return await create_project(client, ws, user_a)


@pytest.fixture
async def session_collect(client, project, user_a, user_b):
    return await create_session(client, project, user_a, participant_ids=[user_b["id"]])


async def test_create_session_auto_adds_facilitator(client, project, user_a, user_b):
    s = await create_session(client, project, user_a, participant_ids=[user_b["id"]])
    assert s["phase"] == "collect"
    assert s["facilitator"]["id"] == user_a["id"]
    assert {p["id"] for p in s["participants"]} == {user_a["id"], user_b["id"]}
    assert s["counts"] == {
        "risks_total": 0,
        "risks_canonical": 0,
        "participants": 2,
        "voters_complete": 0,
    }
    assert s["me"]["is_facilitator"] is True and s["me"]["is_participant"] is True
    got = await client.get(f"/v1/projects/{project['id']}", headers=user_a["headers"])
    assert got.json()["session"]["id"] == s["id"]


async def test_second_session_409(client, project, user_a, session_collect):
    r = await client.post(
        f"/v1/projects/{project['id']}/session", json={}, headers=user_a["headers"]
    )
    assert r.status_code == 409 and r.json()["error"]["code"] == "session_exists"


async def test_session_on_closed_project_409(client, ws, user_a):
    p = await create_project(client, ws, user_a)
    await client.post(
        f"/v1/projects/{p['id']}/transition", json={"to": "active"}, headers=user_a["headers"]
    )
    await client.post(
        f"/v1/projects/{p['id']}/transition", json={"to": "closed"}, headers=user_a["headers"]
    )
    r = await client.post(f"/v1/projects/{p['id']}/session", json={}, headers=user_a["headers"])
    assert r.status_code == 409 and r.json()["error"]["code"] == "project_closed"


async def test_participant_must_be_workspace_member(client, project, user_a, user_c):
    await register(client, user_c)
    r = await client.post(
        f"/v1/projects/{project['id']}/session",
        json={"participant_ids": [user_c["id"]]},
        headers=user_a["headers"],
    )
    assert r.status_code == 400 and r.json()["error"]["code"] == "not_a_member"


async def test_get_session_non_member_404(client, session_collect, user_c):
    r = await client.get(f"/v1/sessions/{session_collect['id']}", headers=user_c["headers"])
    assert r.status_code == 404


async def test_get_session_as_participant(client, session_collect, user_b):
    r = await client.get(f"/v1/sessions/{session_collect['id']}", headers=user_b["headers"])
    assert r.status_code == 200
    assert r.json()["me"] == {
        "is_facilitator": False,
        "is_participant": True,
        "risks_submitted": 0,
        "votes_cast": 0,
        "votes_required": 0,
    }


async def test_collect_to_merge_requires_risks(client, session_collect, user_a):
    r = await transition(client, session_collect, user_a, "merge")
    assert r.status_code == 409 and r.json()["error"]["code"] == "no_risks"
    await add_risk(client, session_collect, user_a, "Vendor API not ready")
    r = await transition(client, session_collect, user_a, "merge")
    assert r.status_code == 200
    assert r.json()["session"]["phase"] == "merge"
    assert r.json()["incomplete_voters"] == []


async def test_non_facilitator_cannot_transition(client, session_collect, user_a, user_b):
    await add_risk(client, session_collect, user_a, "Vendor API not ready")
    r = await transition(client, session_collect, user_b, "merge")
    assert r.status_code == 403 and r.json()["error"]["code"] == "facilitator_required"


async def test_transition_must_be_forward_and_sequential(client, session_collect, user_a):
    await add_risk(client, session_collect, user_a, "Vendor API not ready")
    r = await transition(client, session_collect, user_a, "vote")  # skipping merge
    assert r.status_code == 409 and r.json()["error"]["code"] == "invalid_transition"
    assert (await transition(client, session_collect, user_a, "merge")).status_code == 200
    r = await transition(client, session_collect, user_a, "merge")  # repeat
    assert r.status_code == 409 and r.json()["error"]["code"] == "invalid_transition"
    r = await transition(client, session_collect, user_a, "collect")  # backwards
    assert r.status_code in (409, 422)


async def test_merge_to_vote_needs_canonical_risk(client, session_collect, user_a):
    r1 = await add_risk(client, session_collect, user_a, "Vendor API not ready")
    r2 = await add_risk(client, session_collect, user_a, "Vendor API late")
    await transition(client, session_collect, user_a, "merge")
    # Mark both as duplicates of... cannot: marking r2 dup of r1 leaves r1 canonical, fine.
    await client.patch(
        f"/v1/risks/{r2['id']}", json={"duplicate_of": r1["id"]}, headers=user_a["headers"]
    )
    r = await transition(client, session_collect, user_a, "vote")
    assert r.status_code == 200 and r.json()["session"]["counts"]["risks_canonical"] == 1


async def test_delete_session_only_before_vote(client, session_collect, user_a):
    await add_risk(client, session_collect, user_a, "Vendor API not ready")
    await transition(client, session_collect, user_a, "merge")
    await transition(client, session_collect, user_a, "vote")
    r = await client.delete(f"/v1/sessions/{session_collect['id']}", headers=user_a["headers"])
    assert r.status_code == 409 and r.json()["error"]["code"] == "phase_locked"


async def test_delete_session_in_collect(client, project, session_collect, user_a, user_b):
    r = await client.delete(f"/v1/sessions/{session_collect['id']}", headers=user_b["headers"])
    assert r.status_code == 403
    r = await client.delete(f"/v1/sessions/{session_collect['id']}", headers=user_a["headers"])
    assert r.status_code == 204
    got = await client.get(f"/v1/projects/{project['id']}", headers=user_a["headers"])
    assert got.json()["session"] is None


async def test_admin_reassigns_facilitator(client, ws, session_collect, user_a, user_b, user_c):
    await add_member(client, ws, user_a, user_c)
    # user_c is a member but not a participant yet.
    r = await client.patch(
        f"/v1/sessions/{session_collect['id']}",
        json={"facilitator_id": user_c["id"]},
        headers=user_a["headers"],
    )
    assert r.status_code == 200
    assert r.json()["facilitator"]["id"] == user_c["id"]
    assert user_c["id"] in {p["id"] for p in r.json()["participants"]}
    await add_risk(client, session_collect, user_c, "Vendor API not ready")
    assert (await transition(client, session_collect, user_c, "merge")).status_code == 200
    # A plain member cannot reassign.
    r = await client.patch(
        f"/v1/sessions/{session_collect['id']}",
        json={"facilitator_id": user_b["id"]},
        headers=user_b["headers"],
    )
    assert r.status_code == 403


async def test_participants_add_and_remove(client, ws, session_collect, user_a, user_b, user_c):
    await add_member(client, ws, user_a, user_c)
    r = await client.post(
        f"/v1/sessions/{session_collect['id']}/participants",
        json={"user_ids": [user_c["id"], user_b["id"]]},  # user_b already present: ignored
        headers=user_a["headers"],
    )
    assert r.status_code == 200
    assert {p["id"] for p in r.json()["participants"]} == {user_a["id"], user_b["id"], user_c["id"]}

    r = await client.delete(
        f"/v1/sessions/{session_collect['id']}/participants/{user_a['id']}",
        headers=user_a["headers"],
    )
    assert r.status_code == 409 and r.json()["error"]["code"] == "cannot_remove_facilitator"

    r = await client.delete(
        f"/v1/sessions/{session_collect['id']}/participants/{user_c['id']}",
        headers=user_a["headers"],
    )
    assert r.status_code == 204
    r = await client.delete(
        f"/v1/sessions/{session_collect['id']}/participants/{uuid.uuid4()}",
        headers=user_a["headers"],
    )
    assert r.status_code == 404


async def test_archived_project_freezes_its_session(client, project, session_collect, user_a):
    await add_risk(client, session_collect, user_a, "Vendor API not ready")
    a = await client.post(f"/v1/projects/{project['id']}/archive", headers=user_a["headers"])
    assert a.status_code == 200
    r = await transition(client, session_collect, user_a, "merge")
    assert r.status_code == 409 and r.json()["error"]["code"] == "project_archived"
    r = await client.post(
        f"/v1/sessions/{session_collect['id']}/risks",
        json={"statement": "One more risk"},
        headers=user_a["headers"],
    )
    assert r.status_code == 409 and r.json()["error"]["code"] == "project_archived"
    r = await client.post(
        f"/v1/projects/{project['id']}/surprises",
        json={"statement": "Something happened"},
        headers=user_a["headers"],
    )
    assert r.status_code == 409 and r.json()["error"]["code"] == "project_archived"

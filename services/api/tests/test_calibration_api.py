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


async def _graded_project(client, ws, a, b, *, title, statements, probs_a, probs_b, outcomes, tags):
    """Drive one project from creation to a fully graded, closed state over HTTP."""
    project = await create_project(client, ws, a, title=title, tags=tags)
    r = await client.post(
        f"/v1/projects/{project['id']}/transition", json={"to": "active"}, headers=a["headers"]
    )
    assert r.status_code == 200, r.text
    session = await create_session(client, project, a, participant_ids=[b["id"]])
    risks = [await add_risk(client, session, a, s) for s in statements]
    assert (await transition(client, session, a, "merge")).status_code == 200
    # Tag the last risk "rare" so per-tag thresholds can be exercised.
    r = await client.patch(
        f"/v1/risks/{risks[-1]['id']}", json={"tags": ["rare"]}, headers=a["headers"]
    )
    assert r.status_code == 200, r.text
    assert (await transition(client, session, a, "vote")).status_code == 200
    r = await put_votes(
        client,
        session,
        a,
        [{"risk_id": x["id"], "probability": p, "impact": 3} for x, p in zip(risks, probs_a)],
    )
    assert r.status_code == 200, r.text
    r = await put_votes(
        client,
        session,
        b,
        [{"risk_id": x["id"], "probability": p, "impact": 3} for x, p in zip(risks, probs_b)],
    )
    assert r.status_code == 200, r.text
    assert (await transition(client, session, a, "sealed")).status_code == 200
    r = await client.put(
        f"/v1/projects/{project['id']}/gradings",
        json={"gradings": [{"risk_id": x["id"], "outcome": o} for x, o in zip(risks, outcomes)]},
        headers=a["headers"],
    )
    assert r.status_code == 200, r.text
    r = await client.post(
        f"/v1/projects/{project['id']}/transition", json={"to": "closed"}, headers=a["headers"]
    )
    assert r.status_code == 200, r.text
    return project, risks


@pytest.fixture
async def ws(client, user_a, user_b, user_c):
    ws = await create_workspace(client, user_a)
    await add_member(client, ws, user_a, user_b)
    await add_member(client, ws, user_a, user_c, role="admin")
    return ws


@pytest.fixture
async def history(client, ws, user_a, user_b):
    p1, r1 = await _graded_project(
        client,
        ws,
        user_a,
        user_b,
        title="Checkout Rewrite",
        statements=[
            "Vendor API not ready",
            "Scope creep from marketing",
            "Load test fails",
            "Key engineer on leave",
            "Budget cut",
            "Data migration needs rollback",
        ],
        probs_a=[90, 80, 80, 30, 20, 10],
        probs_b=[80, 70, 70, 40, 30, 15],
        outcomes=["yes", "yes", "no", "no", "no", "yes"],
        tags=["vendor"],
    )
    p2, r2 = await _graded_project(
        client,
        ws,
        user_a,
        user_b,
        title="SSO Rollout",
        statements=[
            "SAML quirks",
            "Legal review slips",
            "Admin UI unusable",
            "Vendor pricing change",
            "Timeline too tight",
            "Nobody owns support",
        ],
        probs_a=[60, 50, 70, 10, 40, 30],
        probs_b=[50, 60, 60, 20, 50, 20],
        outcomes=["yes", "partial", "no", "no", "yes", "no"],
        tags=["vendor", "identity"],
    )
    return {"p1": p1, "r1": r1, "p2": p2, "r2": r2}


async def test_my_calibration(client, ws, history, user_a):
    r = await client.get(f"/v1/workspaces/{ws['id']}/calibration/me", headers=user_a["headers"])
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["user"]["id"] == user_a["id"]
    assert body["sample"] == {"n_graded": 12, "n_projects": 2, "needed": 10, "sufficient": True}
    assert body["brier"] is not None and 0 <= body["brier"] <= 1
    assert body["brier_skill"] is not None
    assert len(body["bins"]) == 10
    assert body["bias_label"] in ("over_estimates_risk", "under_estimates_risk", "calibrated")
    assert [pt["project_title"] for pt in body["trend"]["points"]] == [
        "Checkout Rewrite",
        "SSO Rollout",
    ]
    assert body["trend"]["direction"] == "insufficient_data"
    worst = body["worst_calls"]
    assert 1 <= len(worst) <= 5
    assert (
        worst[0]["statement"] == "Data migration needs rollback" and worst[0]["probability"] == 10
    )
    assert worst[0]["outcome"] == "yes" and worst[0]["project_title"] == "Checkout Rewrite"


async def test_user_calibration_visibility(client, ws, history, user_a, user_b, user_c):
    url = f"/v1/workspaces/{ws['id']}/calibration/users/{user_a['id']}"
    assert (await client.get(url, headers=user_b["headers"])).status_code == 403
    assert (await client.get(url, headers=user_c["headers"])).status_code == 200  # admin
    assert (await client.get(url, headers=user_a["headers"])).status_code == 200  # self
    unknown = await client.get(
        f"/v1/workspaces/{ws['id']}/calibration/users/{uuid.uuid4()}", headers=user_c["headers"]
    )
    assert unknown.status_code == 404


async def test_non_member_404(client, ws, history, user_a):
    from tests.conftest import _make_user

    outsider = _make_user("Zed")
    r = await client.get(f"/v1/workspaces/{ws['id']}/calibration", headers=outsider["headers"])
    assert r.status_code == 404


async def test_workspace_calibration(client, ws, history, user_a, user_b):
    as_owner = await client.get(f"/v1/workspaces/{ws['id']}/calibration", headers=user_a["headers"])
    assert as_owner.status_code == 200, as_owner.text
    body = as_owner.json()
    assert body["sample"]["n_graded"] == 24 and body["sample"]["n_voters"] == 2
    assert body["sample"]["n_projects_closed"] == 2 and body["sample"]["n_projects_graded"] == 2
    assert body["sample"]["sufficient"] is True
    assert body["brier"] is not None
    assert body["base_rate"] == pytest.approx((3 + 2.5) / 12)

    spots = body["blind_spots"]
    assert spots and spots[0]["statement"] == "Data migration needs rollback"
    assert spots[0]["mean_predicted"] == pytest.approx(0.125) and spots[0]["miss"] == pytest.approx(
        0.875
    )
    alarms = body["false_alarms"]
    assert [a["statement"] for a in alarms] == ["Load test fails"]
    assert alarms[0]["miss"] == pytest.approx(-0.75)

    tags = {t["tag"]: t for t in body["tags"]}
    assert (
        "vendor" in tags and tags["vendor"]["n"] == 20
    )  # project tag inherited except by "rare" risks
    assert "rare" not in tags  # only 4 rows: below MIN_TAG_N
    assert "identity" in tags and tags["identity"]["n"] == 10

    members = {m["user"]["id"]: m for m in body["members"]}
    assert set(members) == {user_a["id"], user_b["id"]}
    assert members[user_a["id"]]["n_graded"] == 12 and members[user_a["id"]]["brier"] is not None

    as_member = await client.get(
        f"/v1/workspaces/{ws['id']}/calibration", headers=user_b["headers"]
    )
    assert as_member.status_code == 200 and as_member.json()["members"] is None


async def test_surprise_stats(client, ws, history, user_a):
    before = (
        await client.get(f"/v1/workspaces/{ws['id']}/calibration", headers=user_a["headers"])
    ).json()
    assert before["surprises"] == {
        "rate_per_project": 0.0,
        "share": 0.0,
        "n_surprises": 0,
        "n_projects": 2,
        "recent": [],
    }
    r = await client.post(
        f"/v1/projects/{history['p1']['id']}/surprises",
        json={"statement": "Legal blocked the clause", "tags": ["legal"]},
        headers=user_a["headers"],
    )
    assert r.status_code == 201
    after = (
        await client.get(f"/v1/workspaces/{ws['id']}/calibration", headers=user_a["headers"])
    ).json()
    s = after["surprises"]
    assert s["n_surprises"] == 1 and s["n_projects"] == 2 and s["rate_per_project"] == 0.5
    # materialized canonical risks: p1 yes,yes,yes (3) + p2 yes,partial,yes (3) = 6 -> share 1/7
    assert s["share"] == pytest.approx(1 / 7)
    assert s["recent"][0]["statement"] == "Legal blocked the clause"
    assert s["recent"][0]["project_title"] == "Checkout Rewrite"


async def test_api_small_sample_returns_null_brier(client, user_a, user_b):
    ws2 = await create_workspace(client, user_a, name="Tiny")
    await add_member(client, ws2, user_a, user_b)
    await _graded_project(
        client,
        ws2,
        user_a,
        user_b,
        title="Tiny project",
        statements=["A risk one", "A risk two", "A risk three"],
        probs_a=[50, 60, 70],
        probs_b=[40, 50, 60],
        outcomes=["yes", "no", "yes"],
        tags=["tiny"],
    )
    me = (
        await client.get(f"/v1/workspaces/{ws2['id']}/calibration/me", headers=user_a["headers"])
    ).json()
    assert me["sample"] == {"n_graded": 3, "n_projects": 1, "needed": 10, "sufficient": False}
    assert me["brier"] is None and me["bias"] is None and me["brier_skill"] is None
    assert len(me["bins"]) == 10 and all(b["observed"] is None for b in me["bins"])
    wsr = (
        await client.get(f"/v1/workspaces/{ws2['id']}/calibration", headers=user_a["headers"])
    ).json()
    assert wsr["sample"]["sufficient"] is False and wsr["brier"] is None
    assert wsr["tags"] == []


async def test_empty_workspace_calibration(client, user_a):
    ws3 = await create_workspace(client, user_a, name="Empty")
    r = await client.get(f"/v1/workspaces/{ws3['id']}/calibration", headers=user_a["headers"])
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["sample"]["n_graded"] == 0 and body["brier"] is None and body["base_rate"] == 0.0
    assert body["blind_spots"] == [] and body["trend"]["points"] == []
    assert body["surprises"]["n_projects"] == 0 and body["surprises"]["share"] is None

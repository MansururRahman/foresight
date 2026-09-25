import uuid
from datetime import UTC, datetime

import pytest


@pytest.fixture
async def ws(client, user_a):
    r = await client.post("/v1/workspaces", json={"name": "Demo Team"}, headers=user_a["headers"])
    assert r.status_code == 201
    return r.json()


async def _add_member(client, ws, owner, user, role="member"):
    await client.get("/v1/me", headers=user["headers"])
    r = await client.post(
        f"/v1/workspaces/{ws['id']}/members",
        json={"email": user["email"], "role": role},
        headers=owner["headers"],
    )
    assert r.status_code == 201, r.text


async def _create(client, ws, user, **body):
    payload = {"title": "Vendor API integration", **body}
    r = await client.post(
        f"/v1/workspaces/{ws['id']}/projects", json=payload, headers=user["headers"]
    )
    assert r.status_code == 201, r.text
    return r.json()


async def test_create_normalizes_tags_and_defaults(client, ws, user_a):
    p = await _create(client, ws, user_a, tags=[" Vendor ", "vendor", "External", ""])
    assert p["tags"] == ["vendor", "external"]
    assert p["status"] == "planning"
    assert p["description"] == ""
    assert p["session"] is None
    assert p["created_by"]["id"] == user_a["id"]
    assert p["archived_at"] is None


async def test_create_rejects_bad_date_order(client, ws, user_a):
    r = await client.post(
        f"/v1/workspaces/{ws['id']}/projects",
        json={"title": "X", "planned_start": "2026-12-01", "planned_end": "2026-10-01"},
        headers=user_a["headers"],
    )
    assert r.status_code == 422


async def test_create_rejects_too_many_tags(client, ws, user_a):
    r = await client.post(
        f"/v1/workspaces/{ws['id']}/projects",
        json={"title": "X", "tags": [f"t{i}" for i in range(21)]},
        headers=user_a["headers"],
    )
    assert r.status_code == 422


async def test_project_get_non_member_404(client, ws, user_a, user_b):
    p = await _create(client, ws, user_a)
    r = await client.get(f"/v1/projects/{p['id']}", headers=user_b["headers"])
    assert r.status_code == 404
    assert r.json() == {
        "error": {"code": "not_found", "message": "Project not found", "details": {}}
    }


async def test_get_unknown_project_404(client, ws, user_a):
    r = await client.get(f"/v1/projects/{uuid.uuid4()}", headers=user_a["headers"])
    assert r.status_code == 404


async def test_list_filters_by_status_and_tag(client, ws, user_a):
    p1 = await _create(client, ws, user_a, title="Alpha", tags=["vendor"])
    await _create(client, ws, user_a, title="Beta", tags=["mobile"])
    await client.post(
        f"/v1/projects/{p1['id']}/transition", json={"to": "active"}, headers=user_a["headers"]
    )

    r = await client.get(
        f"/v1/workspaces/{ws['id']}/projects?status=active", headers=user_a["headers"]
    )
    assert [p["title"] for p in r.json()["items"]] == ["Alpha"]

    r = await client.get(
        f"/v1/workspaces/{ws['id']}/projects?tag=mobile", headers=user_a["headers"]
    )
    assert [p["title"] for p in r.json()["items"]] == ["Beta"]

    r = await client.get(f"/v1/workspaces/{ws['id']}/projects?q=alph", headers=user_a["headers"])
    assert [p["title"] for p in r.json()["items"]] == ["Alpha"]


async def test_cursor_pagination_returns_disjoint_pages(client, ws, user_a):
    for i in range(5):
        await _create(client, ws, user_a, title=f"P{i}")
    r1 = await client.get(f"/v1/workspaces/{ws['id']}/projects?limit=2", headers=user_a["headers"])
    page1 = r1.json()
    assert len(page1["items"]) == 2 and page1["next_cursor"]
    r2 = await client.get(
        f"/v1/workspaces/{ws['id']}/projects?limit=2&cursor={page1['next_cursor']}",
        headers=user_a["headers"],
    )
    page2 = r2.json()
    assert len(page2["items"]) == 2 and page2["next_cursor"]
    r3 = await client.get(
        f"/v1/workspaces/{ws['id']}/projects?limit=2&cursor={page2['next_cursor']}",
        headers=user_a["headers"],
    )
    page3 = r3.json()
    assert len(page3["items"]) == 1 and page3["next_cursor"] is None
    ids = [p["id"] for p in page1["items"] + page2["items"] + page3["items"]]
    assert len(set(ids)) == 5
    assert [p["title"] for p in page1["items"]] == ["P4", "P3"]  # newest first


async def test_patch_updates_and_closed_is_locked(client, ws, user_a):
    p = await _create(client, ws, user_a)
    r = await client.patch(
        f"/v1/projects/{p['id']}",
        json={"title": "Renamed", "tags": ["A"]},
        headers=user_a["headers"],
    )
    assert r.status_code == 200 and r.json()["title"] == "Renamed" and r.json()["tags"] == ["a"]

    await client.post(
        f"/v1/projects/{p['id']}/transition", json={"to": "active"}, headers=user_a["headers"]
    )
    closed = await client.post(
        f"/v1/projects/{p['id']}/transition", json={"to": "closed"}, headers=user_a["headers"]
    )
    assert closed.status_code == 200
    assert closed.json()["project"]["status"] == "closed"
    assert closed.json()["project"]["closed_at"] is not None
    assert closed.json()["warnings"] == []

    r = await client.patch(
        f"/v1/projects/{p['id']}", json={"title": "Nope"}, headers=user_a["headers"]
    )
    assert r.status_code == 409 and r.json()["error"]["code"] == "project_closed"


async def test_member_cannot_edit_others_project(client, ws, user_a, user_b):
    await _add_member(client, ws, user_a, user_b)
    p = await _create(client, ws, user_a)
    r = await client.patch(
        f"/v1/projects/{p['id']}", json={"title": "Hijack"}, headers=user_b["headers"]
    )
    assert r.status_code == 403
    # ...but the creator's own project is editable by them even as a plain member.
    mine = await _create(client, ws, user_b, title="Mine")
    r2 = await client.patch(
        f"/v1/projects/{mine['id']}", json={"title": "Mine 2"}, headers=user_b["headers"]
    )
    assert r2.status_code == 200


async def test_transition_planning_to_active_sets_activated_at(client, ws, user_a):
    p = await _create(client, ws, user_a)
    r = await client.post(
        f"/v1/projects/{p['id']}/transition", json={"to": "active"}, headers=user_a["headers"]
    )
    assert r.status_code == 200
    assert r.json()["project"]["status"] == "active"
    assert r.json()["project"]["activated_at"] is not None


async def test_transition_planning_to_closed_409(client, ws, user_a):
    p = await _create(client, ws, user_a)
    r = await client.post(
        f"/v1/projects/{p['id']}/transition", json={"to": "closed"}, headers=user_a["headers"]
    )
    assert r.status_code == 409 and r.json()["error"]["code"] == "invalid_transition"


async def test_transition_active_twice_409(client, ws, user_a):
    p = await _create(client, ws, user_a)
    await client.post(
        f"/v1/projects/{p['id']}/transition", json={"to": "active"}, headers=user_a["headers"]
    )
    r = await client.post(
        f"/v1/projects/{p['id']}/transition", json={"to": "active"}, headers=user_a["headers"]
    )
    assert r.status_code == 409


async def test_close_requires_sealed_session(client, ws, user_a, db_session):
    from app.models import PremortemSession

    p = await _create(client, ws, user_a)
    await client.post(
        f"/v1/projects/{p['id']}/transition", json={"to": "active"}, headers=user_a["headers"]
    )
    db_session.add(
        PremortemSession(
            project_id=uuid.UUID(p["id"]),
            workspace_id=uuid.UUID(ws["id"]),
            created_by=uuid.UUID(user_a["id"]),
            facilitator_id=uuid.UUID(user_a["id"]),
        )
    )
    await db_session.flush()
    r = await client.post(
        f"/v1/projects/{p['id']}/transition", json={"to": "closed"}, headers=user_a["headers"]
    )
    assert r.status_code == 409 and r.json()["error"]["code"] == "session_not_sealed"
    got = await client.get(f"/v1/projects/{p['id']}", headers=user_a["headers"])
    assert got.json()["session"]["phase"] == "collect"


async def test_delete_with_sealed_session_409_then_archive(client, ws, user_a, db_session):
    from app.models import PremortemSession, SessionPhase

    p = await _create(client, ws, user_a)
    db_session.add(
        PremortemSession(
            project_id=uuid.UUID(p["id"]),
            workspace_id=uuid.UUID(ws["id"]),
            created_by=uuid.UUID(user_a["id"]),
            facilitator_id=uuid.UUID(user_a["id"]),
            phase=SessionPhase.sealed,
            sealed_at=datetime.now(UTC),
        )
    )
    await db_session.flush()
    r = await client.delete(f"/v1/projects/{p['id']}", headers=user_a["headers"])
    assert r.status_code == 409 and r.json()["error"]["code"] == "project_has_sealed_session"

    a = await client.post(f"/v1/projects/{p['id']}/archive", headers=user_a["headers"])
    assert a.status_code == 200 and a.json()["archived_at"] is not None
    listed = await client.get(f"/v1/workspaces/{ws['id']}/projects", headers=user_a["headers"])
    assert listed.json()["items"] == []
    listed_all = await client.get(
        f"/v1/workspaces/{ws['id']}/projects?include_archived=true", headers=user_a["headers"]
    )
    assert [x["id"] for x in listed_all.json()["items"]] == [p["id"]]
    u = await client.post(f"/v1/projects/{p['id']}/unarchive", headers=user_a["headers"])
    assert u.status_code == 200 and u.json()["archived_at"] is None


async def test_delete_without_sealed_session_204(client, ws, user_a):
    p = await _create(client, ws, user_a)
    r = await client.delete(f"/v1/projects/{p['id']}", headers=user_a["headers"])
    assert r.status_code == 204
    r2 = await client.get(f"/v1/projects/{p['id']}", headers=user_a["headers"])
    assert r2.status_code == 404


async def test_member_cannot_delete_or_archive(client, ws, user_a, user_b):
    await _add_member(client, ws, user_a, user_b)
    p = await _create(client, ws, user_a)
    assert (
        await client.delete(f"/v1/projects/{p['id']}", headers=user_b["headers"])
    ).status_code == 403
    assert (
        await client.post(f"/v1/projects/{p['id']}/archive", headers=user_b["headers"])
    ).status_code == 403

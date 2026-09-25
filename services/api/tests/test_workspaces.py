import uuid


async def _create_ws(client, user, name="Demo Team", slug=None):
    body = {"name": name}
    if slug:
        body["slug"] = slug
    r = await client.post("/v1/workspaces", json=body, headers=user["headers"])
    assert r.status_code == 201, r.text
    return r.json()


async def _register(client, user):
    # First authenticated call mirrors the user into the API database.
    r = await client.get("/v1/me", headers=user["headers"])
    assert r.status_code == 200


async def test_create_workspace_makes_creator_owner(client, user_a):
    ws = await _create_ws(client, user_a)
    assert ws["my_role"] == "owner"
    assert ws["slug"] == "demo-team"
    assert ws["name"] == "Demo Team"


async def test_slug_collision_gets_suffix(client, user_a):
    a = await _create_ws(client, user_a, name="Same Name")
    b = await _create_ws(client, user_a, name="Same Name")
    assert a["slug"] == "same-name" and b["slug"] == "same-name-2"


async def test_list_shows_only_my_workspaces(client, user_a, user_b):
    await _create_ws(client, user_a, name="A Team")
    await _create_ws(client, user_b, name="B Team")
    r = await client.get("/v1/workspaces", headers=user_a["headers"])
    names = [w["name"] for w in r.json()["items"]]
    assert names == ["A Team"]
    me = await client.get("/v1/me", headers=user_a["headers"])
    assert [w["name"] for w in me.json()["workspaces"]] == ["A Team"]


async def test_non_member_get_is_404(client, user_a, user_b):
    ws = await _create_ws(client, user_a)
    r = await client.get(f"/v1/workspaces/{ws['id']}", headers=user_b["headers"])
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "not_found"


async def test_member_patch_is_403(client, user_a, user_b):
    ws = await _create_ws(client, user_a)
    await _register(client, user_b)
    await client.post(
        f"/v1/workspaces/{ws['id']}/members",
        json={"email": user_b["email"], "role": "member"},
        headers=user_a["headers"],
    )
    r = await client.patch(
        f"/v1/workspaces/{ws['id']}", json={"name": "X"}, headers=user_b["headers"]
    )
    assert r.status_code == 403
    assert r.json()["error"]["code"] == "insufficient_role"


async def test_admin_patch_renames(client, user_a):
    ws = await _create_ws(client, user_a)
    r = await client.patch(
        f"/v1/workspaces/{ws['id']}", json={"name": "Renamed"}, headers=user_a["headers"]
    )
    assert r.status_code == 200 and r.json()["name"] == "Renamed"


async def test_add_member_unknown_email_404(client, user_a):
    ws = await _create_ws(client, user_a)
    r = await client.post(
        f"/v1/workspaces/{ws['id']}/members",
        json={"email": "nobody@demo.local", "role": "member"},
        headers=user_a["headers"],
    )
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "user_not_registered"


async def test_add_member_existing_user(client, user_a, user_b):
    ws = await _create_ws(client, user_a)
    await _register(client, user_b)
    r = await client.post(
        f"/v1/workspaces/{ws['id']}/members",
        json={"email": user_b["email"].upper(), "role": "admin"},
        headers=user_a["headers"],
    )
    assert r.status_code == 201
    assert r.json()["user"]["id"] == user_b["id"] and r.json()["role"] == "admin"
    again = await client.post(
        f"/v1/workspaces/{ws['id']}/members",
        json={"email": user_b["email"], "role": "member"},
        headers=user_a["headers"],
    )
    assert again.status_code == 409 and again.json()["error"]["code"] == "already_member"
    listing = await client.get(f"/v1/workspaces/{ws['id']}/members", headers=user_b["headers"])
    assert listing.status_code == 200
    roles = {m["user"]["id"]: m["role"] for m in listing.json()["items"]}
    assert roles == {user_a["id"]: "owner", user_b["id"]: "admin"}


async def test_admin_cannot_grant_owner(client, user_a, user_b, user_c):
    ws = await _create_ws(client, user_a)
    await _register(client, user_b)
    await _register(client, user_c)
    await client.post(
        f"/v1/workspaces/{ws['id']}/members",
        json={"email": user_b["email"], "role": "admin"},
        headers=user_a["headers"],
    )
    r = await client.post(
        f"/v1/workspaces/{ws['id']}/members",
        json={"email": user_c["email"], "role": "owner"},
        headers=user_b["headers"],
    )
    assert r.status_code == 403
    assert r.json()["error"]["code"] == "owner_required"


async def test_member_cannot_add_members(client, user_a, user_b, user_c):
    ws = await _create_ws(client, user_a)
    await _register(client, user_b)
    await _register(client, user_c)
    await client.post(
        f"/v1/workspaces/{ws['id']}/members",
        json={"email": user_b["email"], "role": "member"},
        headers=user_a["headers"],
    )
    r = await client.post(
        f"/v1/workspaces/{ws['id']}/members",
        json={"email": user_c["email"], "role": "member"},
        headers=user_b["headers"],
    )
    assert r.status_code == 403


async def test_demote_last_owner_409(client, user_a):
    ws = await _create_ws(client, user_a)
    r = await client.put(
        f"/v1/workspaces/{ws['id']}/members/{user_a['id']}",
        json={"role": "admin"},
        headers=user_a["headers"],
    )
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "last_owner"


async def test_owner_promotes_and_demotes(client, user_a, user_b):
    ws = await _create_ws(client, user_a)
    await _register(client, user_b)
    await client.post(
        f"/v1/workspaces/{ws['id']}/members",
        json={"email": user_b["email"], "role": "member"},
        headers=user_a["headers"],
    )
    r = await client.put(
        f"/v1/workspaces/{ws['id']}/members/{user_b['id']}",
        json={"role": "owner"},
        headers=user_a["headers"],
    )
    assert r.status_code == 200 and r.json()["role"] == "owner"
    # Now user_a is no longer the last owner and can step down.
    r2 = await client.put(
        f"/v1/workspaces/{ws['id']}/members/{user_a['id']}",
        json={"role": "member"},
        headers=user_a["headers"],
    )
    assert r2.status_code == 200 and r2.json()["role"] == "member"


async def test_member_self_leave_204(client, user_a, user_b):
    ws = await _create_ws(client, user_a)
    await _register(client, user_b)
    await client.post(
        f"/v1/workspaces/{ws['id']}/members",
        json={"email": user_b["email"], "role": "member"},
        headers=user_a["headers"],
    )
    r = await client.delete(
        f"/v1/workspaces/{ws['id']}/members/{user_b['id']}", headers=user_b["headers"]
    )
    assert r.status_code == 204
    r2 = await client.get(f"/v1/workspaces/{ws['id']}", headers=user_b["headers"])
    assert r2.status_code == 404


async def test_last_owner_cannot_leave(client, user_a):
    ws = await _create_ws(client, user_a)
    r = await client.delete(
        f"/v1/workspaces/{ws['id']}/members/{user_a['id']}", headers=user_a["headers"]
    )
    assert r.status_code == 409 and r.json()["error"]["code"] == "last_owner"


async def test_remove_unknown_member_404(client, user_a):
    ws = await _create_ws(client, user_a)
    r = await client.delete(
        f"/v1/workspaces/{ws['id']}/members/{uuid.uuid4()}", headers=user_a["headers"]
    )
    assert r.status_code == 404


async def test_tags_counts(client, user_a, db_session):
    from app.models import Project, Risk, RiskOrigin

    ws = await _create_ws(client, user_a)
    wid = uuid.UUID(ws["id"])
    uid = uuid.UUID(user_a["id"])
    p1 = Project(workspace_id=wid, title="P1", tags=["vendor", "tech"], created_by=uid)
    p2 = Project(workspace_id=wid, title="P2", tags=["vendor"], created_by=uid)
    db_session.add_all([p1, p2])
    await db_session.flush()
    db_session.add(
        Risk(
            project_id=p1.id,
            session_id=None,
            workspace_id=wid,
            author_id=uid,
            origin=RiskOrigin.surprise,
            statement="Legal blocked",
            submitted_statement="Legal blocked",
            tags=["legal", "vendor"],
        )
    )
    await db_session.flush()
    r = await client.get(f"/v1/workspaces/{ws['id']}/tags", headers=user_a["headers"])
    assert r.status_code == 200
    by_tag = {t["tag"]: t for t in r.json()["items"]}
    assert by_tag["vendor"] == {"tag": "vendor", "project_count": 2, "risk_count": 1}
    assert by_tag["tech"]["project_count"] == 1 and by_tag["tech"]["risk_count"] == 0
    assert by_tag["legal"]["project_count"] == 0 and by_tag["legal"]["risk_count"] == 1
    assert [t["tag"] for t in r.json()["items"]][0] == "vendor"  # sorted by total desc, then name

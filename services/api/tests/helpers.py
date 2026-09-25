"""HTTP-level helpers shared by API tests."""

import uuid


async def register(client, user):
    r = await client.get("/v1/me", headers=user["headers"])
    assert r.status_code == 200


async def create_workspace(client, user, name="Demo Team"):
    r = await client.post("/v1/workspaces", json={"name": name}, headers=user["headers"])
    assert r.status_code == 201, r.text
    return r.json()


async def add_member(client, ws, owner, user, role="member"):
    await register(client, user)
    r = await client.post(
        f"/v1/workspaces/{ws['id']}/members",
        json={"email": user["email"], "role": role},
        headers=owner["headers"],
    )
    assert r.status_code == 201, r.text
    return r.json()


async def create_project(client, ws, user, **body):
    payload = {"title": "Vendor API integration", **body}
    r = await client.post(
        f"/v1/workspaces/{ws['id']}/projects", json=payload, headers=user["headers"]
    )
    assert r.status_code == 201, r.text
    return r.json()


async def create_session(client, project, user, participant_ids=()):
    r = await client.post(
        f"/v1/projects/{project['id']}/session",
        json={"participant_ids": [str(uuid.UUID(p)) for p in participant_ids]},
        headers=user["headers"],
    )
    assert r.status_code == 201, r.text
    return r.json()


async def add_risk(client, session, user, statement):
    r = await client.post(
        f"/v1/sessions/{session['id']}/risks",
        json={"statement": statement},
        headers=user["headers"],
    )
    assert r.status_code == 201, r.text
    return r.json()


async def transition(client, session, user, to):
    r = await client.post(
        f"/v1/sessions/{session['id']}/transition", json={"to": to}, headers=user["headers"]
    )
    return r


async def put_votes(client, session, user, votes):
    r = await client.put(
        f"/v1/sessions/{session['id']}/votes", json={"votes": votes}, headers=user["headers"]
    )
    return r

from tests.conftest import PASSWORD


async def test_login_returns_token_pair(client, operator):
    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": "operator@orbitalsentinel.io", "password": PASSWORD},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["access_token"] and body["refresh_token"]
    assert body["token_type"] == "bearer"
    assert body["expires_in"] == 15 * 60


async def test_login_wrong_password_is_generic_401(client, operator):
    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": "operator@orbitalsentinel.io", "password": "wrong-password!"},
    )
    assert resp.status_code == 401
    assert resp.json()["detail"] == "Invalid credentials"  # no user-exists oracle


async def test_access_token_grants_me(client, operator):
    _, headers = operator
    resp = await client.get("/api/v1/auth/me", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["email"] == "operator@orbitalsentinel.io"
    assert body["roles"] == ["operator"]


async def test_refresh_rotates_token(client, operator):
    login = await client.post(
        "/api/v1/auth/login",
        json={"email": "operator@orbitalsentinel.io", "password": PASSWORD},
    )
    first_refresh = login.json()["refresh_token"]

    resp = await client.post("/api/v1/auth/refresh", json={"refresh_token": first_refresh})
    assert resp.status_code == 200
    second_refresh = resp.json()["refresh_token"]
    assert second_refresh != first_refresh

    # The successor works
    resp = await client.post("/api/v1/auth/refresh", json={"refresh_token": second_refresh})
    assert resp.status_code == 200


async def test_refresh_reuse_revokes_entire_family(client, operator):
    login = await client.post(
        "/api/v1/auth/login",
        json={"email": "operator@orbitalsentinel.io", "password": PASSWORD},
    )
    first = login.json()["refresh_token"]
    second = (await client.post("/api/v1/auth/refresh", json={"refresh_token": first})).json()[
        "refresh_token"
    ]

    # Replay of the rotated token: rejected AND kills the family
    reuse = await client.post("/api/v1/auth/refresh", json={"refresh_token": first})
    assert reuse.status_code == 401
    after = await client.post("/api/v1/auth/refresh", json={"refresh_token": second})
    assert after.status_code == 401


async def test_logout_revokes_refresh(client, operator):
    login = await client.post(
        "/api/v1/auth/login",
        json={"email": "operator@orbitalsentinel.io", "password": PASSWORD},
    )
    refresh = login.json()["refresh_token"]
    assert (
        await client.post("/api/v1/auth/logout", json={"refresh_token": refresh})
    ).status_code == 204
    assert (
        await client.post("/api/v1/auth/refresh", json={"refresh_token": refresh})
    ).status_code == 401


async def test_unauthenticated_request_is_401(client, db):
    resp = await client.get("/api/v1/assets")
    assert resp.status_code == 401
    assert resp.headers.get("WWW-Authenticate") == "Bearer"

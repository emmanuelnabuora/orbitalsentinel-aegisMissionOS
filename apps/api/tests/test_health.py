async def test_healthz_reports_ok(client):
    resp = await client.get("/api/v1/healthz")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["env"] == "test"
    assert body["version"]


async def test_security_headers_present_on_every_response(client):
    resp = await client.get("/api/v1/healthz")
    assert resp.headers["X-Content-Type-Options"] == "nosniff"
    assert resp.headers["X-Frame-Options"] == "DENY"
    assert resp.headers["Cache-Control"] == "no-store"
    assert resp.headers["X-Request-ID"]


async def test_request_id_is_propagated_when_supplied(client):
    resp = await client.get("/api/v1/healthz", headers={"X-Request-ID": "corr-123"})
    assert resp.headers["X-Request-ID"] == "corr-123"


async def test_readyz_degrades_honestly_without_dependencies(client):
    # No Postgres/Redis in unit tests: readiness must report 503, not crash.
    resp = await client.get("/api/v1/readyz")
    assert resp.status_code == 503
    body = resp.json()
    assert body["status"] == "degraded"
    assert set(body["checks"]) == {"postgres", "redis"}

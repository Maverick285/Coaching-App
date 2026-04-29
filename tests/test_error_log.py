"""Verify that unhandled exceptions land in the ring buffer + /admin/errors."""

from __future__ import annotations

from buddy.services.error_log import clear


def test_500_is_captured_with_traceback(authed_client, monkeypatch):
    clear()  # start clean for this test

    # Force a real unhandled exception inside a real request handler.
    # /converse uses chat() — patch it to blow up with a recognizable error.
    async def boom(**_):
        raise RuntimeError("smoke_test_marker_xyz")

    monkeypatch.setattr("buddy.api.converse.chat", boom)
    r = authed_client.post("/converse", json={"message": "hi"})
    assert r.status_code in (500, 502)

    listing = authed_client.get("/admin/errors").json()["errors"]
    assert len(listing) == 1
    e = listing[0]
    assert e["method"] == "POST"
    assert e["path"] == "/converse"
    assert "smoke_test_marker_xyz" in e["exception"]
    assert "Traceback" in e["traceback"] or "RuntimeError" in e["traceback"]


def test_clear_endpoint_drops_buffer(authed_client, monkeypatch):
    clear()

    async def boom(**_):
        raise RuntimeError("delete_me")

    monkeypatch.setattr("buddy.api.converse.chat", boom)
    authed_client.post("/converse", json={"message": "hi"})
    assert len(authed_client.get("/admin/errors").json()["errors"]) >= 1

    r = authed_client.post("/admin/errors/clear")
    assert r.status_code == 200
    assert authed_client.get("/admin/errors").json()["errors"] == []

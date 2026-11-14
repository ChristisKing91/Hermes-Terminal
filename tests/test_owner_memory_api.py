"""Synthetic route tests: no real owner data or model usage."""
import hmac
import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from hermes_terminal.owner_memory_api import create_memory_router


@pytest.fixture
def client(monkeypatch, tmp_path):
    monkeypatch.delenv("LXRION_OWNER_MEMORY_ENABLED", raising=False)
    monkeypatch.setenv("LXRION_OWNER_MEMORY_DB", str(tmp_path / "private" / "memory.sqlite"))

    def auth(value):
        if not hmac.compare_digest(value or "", "Bearer local-fixture-token"):
            raise HTTPException(401)

    app = FastAPI()
    app.include_router(create_memory_router(auth))
    return TestClient(app)


AUTH = {"Authorization": "Bearer local-fixture-token"}


def test_disabled_and_unauthorized(client):
    assert client.get("/api/memory/status").status_code == 401
    assert client.get("/api/memory/items", headers=AUTH).status_code == 412
    assert client.get("/api/memory/status", headers=AUTH).json()["enabled"] is False


def test_remember_search_forget(client, monkeypatch):
    monkeypatch.setenv("LXRION_OWNER_MEMORY_ENABLED", "1")
    payload = {
        "scope": "devices", "key": "fixture_laptop",
        "value": "Internal SSD holds the OS", "provenance": "owner-confirmed",
        "consent": True
    }
    rejected = client.post("/api/memory/items", headers=AUTH, json={**payload, "consent": False})
    assert rejected.status_code == 422
    assert client.post("/api/memory/items", headers=AUTH, json=payload).json()["revision"] == 1
    assert len(client.get("/api/memory/search", headers=AUTH, params={"q": "SSD"}).json()["items"]) == 1
    assert client.delete("/api/memory/items/devices/fixture_laptop", headers=AUTH).json()["forgotten"] is True
    assert client.get("/api/memory/items", headers=AUTH).json()["items"] == []


def test_no_auto_chat_retention(client, monkeypatch):
    monkeypatch.setenv("LXRION_OWNER_MEMORY_ENABLED", "1")
    status = client.get("/api/memory/status", headers=AUTH).json()
    assert not status["automaticChatRetention"]
    assert not status["automaticModelContextInjection"]

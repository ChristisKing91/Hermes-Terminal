"""Portal security and endpoint tests; all sources are synthetic or stubbed."""
from __future__ import annotations

import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient

from hermes_terminal import portal


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("LXRION_PORTAL_TOKEN", "fixture-private-token")
    monkeypatch.delenv("LXRION_COORDINATOR_ROOT", raising=False)
    return TestClient(portal.app)


def auth():
    return {"Authorization": "Bearer fixture-private-token"}


def test_health_is_read_only_and_no_backend_side_effects(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert not data["canExecute"]
    assert not data["canApprove"]
    assert not data["canApply"]
    assert not data["persistentKnowledgeStore"]


def test_ui_renders_without_exposing_configured_token(client):
    response = client.get("/")
    assert response.status_code == 200
    assert "LXRION" in response.text
    assert "fixture-private-token" not in response.text


def test_sensitive_routes_deny_missing_or_wrong_token(client):
    assert client.get("/api/models").status_code == 401
    assert client.get("/api/models", headers={"Authorization": "Bearer wrong"}).status_code == 401
    assert client.post("/api/chat", json={"prompt": "hello"}).status_code == 401
    assert client.post("/api/coordinator/snapshot").status_code == 401
    assert client.get("/api/telemetry").status_code == 401


def test_token_must_be_explicitly_configured(client, monkeypatch):
    monkeypatch.delenv("LXRION_PORTAL_TOKEN")
    assert client.get("/api/models", headers=auth()).status_code == 503


def test_coordinator_snapshot_requires_trusted_root(client):
    response = client.post("/api/coordinator/snapshot", headers=auth())
    assert response.status_code == 412


def test_snapshot_uses_existing_adapter_and_does_not_return_raw_payload(client, monkeypatch):
    monkeypatch.setenv("LXRION_COORDINATOR_ROOT", r"C:\\Owner\\AI Development Team")
    seen = []

    def stub(**kwargs):
        seen.append(kwargs)
        return {
            "authority": "existing-local-dev-team",
            "freshness": "observed",
            "tasks": [{"taskRef": {"coordinator": "local-dev-team",
                                  "projectId": "lxrion", "taskId": "task_fixture"},
                       "coordinatorStatus": "awaiting_approval"}],
            "capabilities": {"canExecute": False, "canApprove": False,
                             "canApply": False, "canTeach": False},
        }

    monkeypatch.setattr(portal, "read_snapshot", stub)
    result = client.post("/api/coordinator/snapshot", headers=auth())
    assert result.status_code == 200
    assert len(seen) == 1
    assert seen[0]["trusted_base"] == portal.TRUSTED_BASE
    assert seen[0]["timeout"] <= 10
    assert result.json()["capabilities"]["canApply"] is False


def test_chat_reuses_existing_provider_without_exec_or_tools(client, monkeypatch):
    calls = []

    class FakeProvider:
        model = "local-test:1"
        def generate_response(self, prompt, system_prompt=None):
            calls.append((prompt, system_prompt))
            return "This is a suggestion, not an executed action."

    monkeypatch.setattr(portal, "_provider", lambda: FakeProvider())
    response = client.post("/api/chat", headers=auth(),
                           json={"prompt": "Please explain the deployment pipeline"})
    assert response.status_code == 200
    assert response.json()["executedActions"] == 0
    assert calls[0][0] == "Please explain the deployment pipeline"
    assert "cannot run commands" in calls[0][1].lower()


def test_chat_enforces_prompt_bound_and_telemetry_contains_no_prompts(client):
    oversized = client.post("/api/chat", headers=auth(), json={"prompt": "a" * 6001})
    assert oversized.status_code == 422
    metrics = client.get("/api/telemetry", headers=auth())
    assert metrics.status_code == 200
    assert metrics.json()["promptsStored"] is False


def test_model_discovery_uses_existing_provider(client, monkeypatch):
    class FakeProvider:
        model = "fixture-model"
        def list_models(self):
            return ["fixture-model"]

    monkeypatch.setattr(portal, "_provider", lambda: FakeProvider())
    result = client.get("/api/models", headers=auth())
    assert result.status_code == 200
    assert result.json() == {"availableModels": ["fixture-model"],
                             "configuredModel": "fixture-model"}


def test_remote_ollama_config_is_rejected(client, monkeypatch):
    monkeypatch.setenv("OLLAMA_BASE_URL", "https://remote.example")
    result = client.get("/api/models", headers=auth())
    assert result.status_code == 503

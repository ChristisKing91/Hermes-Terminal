"""Synthetic contracts for the local portal model routes."""
import pytest
from fastapi.testclient import TestClient

from hermes_terminal import portal
from hermes_terminal.ai.ollama import AITimeoutError


@pytest.fixture
def runtime(monkeypatch):
    monkeypatch.setenv("LXRION_PORTAL_TOKEN", "synthetic")
    installed = []
    calls = []
    result = [0.01] * 768

    class Provider:
        def __init__(self, model):
            self.model = model

        def list_models(self):
            calls.append(("inventory", None))
            return installed

        def generate_response(self, prompt, system_prompt):
            calls.append(("chat", self.model))
            if prompt == "timeout":
                raise AITimeoutError("fixture")
            return "fixture"

        def embed(self, text):
            calls.append(("embed", self.model))
            return result

    monkeypatch.setattr(portal, "_provider", lambda model=None: Provider(model or "legacy"))
    with TestClient(portal.app, headers={"Authorization": "Bearer synthetic"}) as client:
        yield client, installed, calls, result


def test_legacy_chat_preserves_configured_model_without_inventory(runtime):
    client, _, calls, _ = runtime
    assert client.post("/api/chat", json={"prompt": "hello"}).json() == {
        "answer": "fixture", "model": "legacy", "executedActions": 0,
    }
    assert calls == [("chat", "legacy")]


@pytest.mark.parametrize(("purpose", "expected"), [
    ("chat", "llama3.2:3b"), ("coding", "qwen2.5-coder:1.5b"),
    ("reasoning", "qwen3:1.7b"),
])
def test_routing_uses_policy_order_and_exact_tags(runtime, purpose, expected):
    client, installed, calls, _ = runtime
    installed.extend(["qwen2.5-coder:7b", "qwen2.5-coder:1.5b", "qwen3:4b",
                      "qwen3:1.7b", "gemma3:4b", "llama3.2:3b", "llama3.2:3b"])
    reply = client.post("/api/chat", json={"prompt": "hello", "purpose": purpose})
    assert reply.status_code == 200
    assert reply.json()["model"] == expected
    assert calls == [("inventory", None), ("chat", expected)]


def test_fallback_never_crosses_capability_or_tag(runtime):
    client, installed, calls, _ = runtime
    installed.extend(["qwen2.5-coder:latest", "nomic-embed-text:latest"])
    request = {"prompt": "hello", "purpose": "coding"}
    reply = client.post("/api/chat", json=request)
    assert reply.status_code == 503
    assert reply.json()["detail"] == {"code": "model_unavailable", "capability": "coding"}
    assert calls == [("inventory", None)]
    installed.append("qwen2.5-coder:3b")
    assert client.post("/api/chat", json=request).json()["model"] == "qwen2.5-coder:3b"


def test_auth_invalid_purpose_and_busy_skip_inventory(runtime):
    client, _, calls, _ = runtime
    assert client.get("/api/model-capabilities", headers={"Authorization": "wrong"}).status_code == 401
    assert client.post("/api/embeddings", json={"text": "private"},
                       headers={"Authorization": "wrong"}).status_code == 401
    assert client.post("/api/chat", json={"prompt": "hello", "purpose": "vision"}).status_code == 422
    with portal.INFERENCE_LOCK:
        assert client.post("/api/chat", json={"prompt": "hello"}).status_code == 429
    assert not calls


def test_timeout_does_not_retry_and_releases_slot(runtime):
    client, installed, calls, _ = runtime
    installed.extend(["qwen3:1.7b", "qwen3:4b"])
    assert client.post("/api/chat", json={"prompt": "timeout", "purpose": "reasoning"}).status_code == 504
    assert calls == [("inventory", None), ("chat", "qwen3:1.7b")]
    assert client.post("/api/chat", json={"prompt": "hello"}).status_code == 200


def test_inventory_distinguishes_declared_from_installed_and_routable(runtime):
    client, installed, calls, _ = runtime
    installed.append("gemma3:4b")
    data = client.get("/api/model-capabilities").json()
    assert len(data["models"]) == 9
    assert "vision" not in data["routableCapabilities"]
    assert [entry["model"] for entry in data["models"] if entry["installed"]] == ["gemma3:4b"]
    assert calls == [("inventory", None)]


@pytest.mark.parametrize("invalid", [False, "bad", float("nan"), float("inf"), 10**500])
def test_embedding_vector_validation(runtime, invalid):
    client, installed, calls, result = runtime
    installed.append("nomic-embed-text:latest")
    result[0] = invalid
    reply = client.post("/api/embeddings", json={"text": "fixture"})
    assert reply.status_code == 503
    assert calls == [("inventory", None), ("embed", "nomic-embed-text:latest")]


def test_embedding_routes_to_embedding_model(runtime):
    client, installed, calls, _ = runtime
    installed.extend(["qwen3:1.7b", "nomic-embed-text:latest"])
    data = client.post("/api/embeddings", json={"text": "fixture"}).json()
    assert data["model"] == "nomic-embed-text:latest"
    assert data["dimensions"] == len(data["embedding"]) == 768
    assert calls == [("inventory", None), ("embed", "nomic-embed-text:latest")]

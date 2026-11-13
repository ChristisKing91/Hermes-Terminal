from base64 import b64encode
from io import BytesIO
import wave

from fastapi.testclient import TestClient
import pytest

from hermes_terminal import portal
from hermes_terminal.ai.ollama import AITimeoutError


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("LXRION_PORTAL_TOKEN", "synthetic")
    with TestClient(portal.app, headers={"Authorization": "Bearer synthetic"}) as value:
        yield value


def audio(rate=16000):
    buffer = BytesIO()
    with wave.open(buffer, "wb") as stream:
        stream.setnchannels(1)
        stream.setsampwidth(2)
        stream.setframerate(rate)
        stream.writeframes(b"\0\0" * 160)
    return b64encode(buffer.getvalue()).decode("ascii")


def test_transcription_checks_format_and_uses_typed_language(client, monkeypatch):
    calls = []
    monkeypatch.setattr(portal, "transcribe", lambda *args: (calls.append(args) or ("fixture", "speech")))
    assert client.post("/api/transcription", json={"audio": audio(8000)}).status_code == 422
    assert client.post("/api/transcription", json={"audio": "invalid"}).status_code == 422
    assert client.post("/api/transcription", json={"audio": audio()},
                       headers={"Authorization": "wrong"}).status_code == 401
    assert calls == []
    assert client.post("/api/transcription", json={"audio": audio(), "language": "es"}).json() == {
        "model": "fixture", "text": "speech",
    }
    assert calls == [(audio(), "es")]


def test_translation_validates_languages_and_calls_once(client, monkeypatch):
    calls = []
    monkeypatch.setattr(portal, "translate", lambda *args: (calls.append(args) or ("fixture", "Hola")))
    assert client.post("/api/translation", json={
        "text": "Hello", "source": "eng", "target": "eng",
    }).status_code == 422
    assert client.post("/api/translation", json={
        "text": "Hello", "source": "eng", "target": "spa",
    }).json() == {"model": "fixture", "text": "Hola"}
    assert calls == [("Hello", "eng", "spa")]


def test_unavailable_and_timeout_release_shared_slot(client, monkeypatch):
    payload = {"text": "Hello", "source": "eng", "target": "spa"}
    monkeypatch.setattr(portal, "translate", lambda *args: ("fixture", None))
    assert client.post("/api/translation", json=payload).status_code == 503
    with portal.INFERENCE_LOCK:
        assert client.post("/api/translation", json=payload).status_code == 429

    def timeout(*args):
        raise AITimeoutError("fixture")

    monkeypatch.setattr(portal, "translate", timeout)
    assert client.post("/api/translation", json=payload).status_code == 504
    assert not portal.INFERENCE_LOCK.locked()

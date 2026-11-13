"""Bounded adapters for the existing Kali speech and translation environments."""
from __future__ import annotations

import base64
import binascii
import io
import json
import os
from pathlib import Path
import subprocess
import wave

from .ai.ollama import AITimeoutError


SPEECH_MODELS = {
    "en": ("Systran/faster-whisper-small.en", "Systran--faster-whisper-small.en"),
    "es": ("Systran/faster-whisper-small", "Systran--faster-whisper-small"),
}
TRANSLATION_MODEL = "facebook/seamless-m4t-v2-large"
MAX_AUDIO_BYTES = 640044

_SPEECH = """
import base64, io, json, sys
from faster_whisper import WhisperModel
data = json.load(sys.stdin)
model = WhisperModel(sys.argv[1], device="cpu", compute_type="int8",
                     cpu_threads=4, local_files_only=True)
segments, _ = model.transcribe(io.BytesIO(base64.b64decode(data["audio"])),
                               language=data["language"], beam_size=1)
print(json.dumps({"text": " ".join(segment.text.strip() for segment in segments)}))
"""

_TRANSLATION = """
import json, sys, torch
from transformers import AutoProcessor, SeamlessM4Tv2Model
data = json.load(sys.stdin)
torch.set_num_threads(4)
processor = AutoProcessor.from_pretrained(sys.argv[1], local_files_only=True)
model = SeamlessM4Tv2Model.from_pretrained(
    sys.argv[1], local_files_only=True, dtype=torch.bfloat16, low_cpu_mem_usage=True
)
inputs = processor(text=data["text"], src_lang=data["source"], return_tensors="pt")
with torch.inference_mode():
    output = model.generate(**inputs, tgt_lang=data["target"], generate_speech=False,
                            max_new_tokens=128)
sequence = output.sequences[0] if hasattr(output, "sequences") else output[0]
print(json.dumps({"text": processor.decode(sequence.tolist(), skip_special_tokens=True)}))
"""


def valid_audio(encoded: str) -> bool:
    """Accept only complete, bounded, uncompressed mono PCM WAV."""
    try:
        audio = base64.b64decode(encoded, validate=True)
        if len(audio) > MAX_AUDIO_BYTES:
            return False
        with wave.open(io.BytesIO(audio), "rb") as stream:
            frames = stream.getnframes()
            return (
                stream.getnchannels() == 1
                and stream.getsampwidth() == 2
                and stream.getframerate() == 16000
                and 0 < frames <= 320000
                and len(stream.readframes(frames)) == frames * 2
            )
    except (binascii.Error, EOFError, wave.Error):
        return False


def _invoke(runtime: str, model_dir: str, program: str, data: dict, timeout: int) -> str | None:
    root = Path(os.environ.get("LXRION_MODEL_ASSETS", Path.home() / "LXRION" / "model-assets"))
    python = root / runtime / "bin" / "python"
    weights = root / model_dir
    if not python.is_file() or not (weights / "config.json").is_file():
        return None
    env = {
        "PATH": os.defpath,
        "HOME": str(Path.home()),
        "LANG": "C.UTF-8",
        "HF_HUB_OFFLINE": "1",
        "TRANSFORMERS_OFFLINE": "1",
        "OMP_NUM_THREADS": "4",
    }
    try:
        result = subprocess.run(
            [str(python), "-c", program, str(weights)],
            input=json.dumps(data), text=True, capture_output=True, timeout=timeout,
            env=env, check=True,
        )
        parsed = json.loads(result.stdout)
        if isinstance(parsed, dict) and isinstance(parsed.get("text"), str):
            return parsed["text"].strip()
    except subprocess.TimeoutExpired as error:
        raise AITimeoutError("Local model timed out") from error
    except (OSError, subprocess.CalledProcessError, ValueError):
        return None
    return None


def transcribe(audio: str, language: str) -> tuple[str, str | None]:
    model, directory = SPEECH_MODELS[language]
    return model, _invoke(
        ".venv-whisper", directory, _SPEECH, {"audio": audio, "language": language}, 90,
    )


def translate(text: str, source: str, target: str) -> tuple[str, str | None]:
    return TRANSLATION_MODEL, _invoke(
        ".venv-transformers", "facebook--seamless-m4t-v2-large", _TRANSLATION,
        {"text": text, "source": source, "target": target}, 300,
    )

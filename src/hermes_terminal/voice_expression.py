"""Deterministic voice direction. This does not claim to infer a person's feelings."""
from __future__ import annotations
from dataclasses import dataclass
from enum import Enum

class Emotion(str, Enum):
    NEUTRAL = "neutral"
    EXCITED = "excited"
    CONCERNED = "concerned"
    FOCUSED = "focused"
    PLAYFUL = "playful"
    URGENT = "urgent"

@dataclass(frozen=True)
class VoiceIdentity:
    """Owner-selected signature voice. Emotion never changes this identity."""
    voice_id: str = "am_michael"
    accent: str = "american"
    def __post_init__(self) -> None:
        if not self.voice_id or len(self.voice_id) > 100:
            raise ValueError("voice_id must be nonempty and at most 100 characters")
        if self.accent not in {"american", "british", "neutral"}:
            raise ValueError("unsupported accent")

@dataclass(frozen=True)
class VoiceRequest:
    text: str
    emotion: Emotion = Emotion.NEUTRAL
    safety_critical: bool = False
    owner_override: Emotion | None = None
    def __post_init__(self) -> None:
        if not isinstance(self.text, str) or not self.text.strip() or len(self.text) > 4000:
            raise ValueError("speech text must be 1-4000 non-whitespace characters")

@dataclass(frozen=True)
class SpeechPlan:
    text: str
    voice_id: str
    emotion: Emotion
    speed: float
    pause_ms: int
    direction: str

_PROFILE = {
    Emotion.NEUTRAL: (1.00, 160, "Conversational, composed, authentic; do not sound robotic."),
    Emotion.EXCITED: (1.07, 110, "Bright, enthusiastic, controlled; avoid exaggeration."),
    Emotion.CONCERNED: (0.94, 210, "Warm, gentle, steady; avoid theatrical sadness."),
    Emotion.FOCUSED: (1.00, 95, "Direct, precise, technically clear."),
    Emotion.PLAYFUL: (1.03, 155, "Light dry humor, subtle smile; never mocking."),
    Emotion.URGENT: (0.98, 80, "Clear, firm, calm urgency; no shouting or panic."),
}

class VoiceDirector:
    def __init__(self, identity: VoiceIdentity | None = None) -> None:
        self.identity = identity or VoiceIdentity()

    def plan(self, request: VoiceRequest) -> SpeechPlan:
        # Safety-sensitive information must not be weakened by a playful override.
        emotion = (Emotion.URGENT if request.safety_critical
                   else (request.owner_override or request.emotion))
        speed, pause_ms, direction = _PROFILE[emotion]
        return SpeechPlan(
            text=request.text.strip(), voice_id=self.identity.voice_id,
            emotion=emotion, speed=speed, pause_ms=pause_ms, direction=direction,
        )

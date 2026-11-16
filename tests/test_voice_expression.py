from hermes_terminal.voice_expression import Emotion, VoiceDirector, VoiceIdentity, VoiceRequest
import pytest


def test_same_voice_for_all_moods():
    director = VoiceDirector(VoiceIdentity("bm_george", "british"))
    assert {director.plan(VoiceRequest("hello", m)).voice_id for m in Emotion} == {"bm_george"}

@pytest.mark.parametrize("mood", list(Emotion))
def test_emotional_profiles_are_bounded(mood):
    result = VoiceDirector().plan(VoiceRequest("hello", mood))
    assert 0.7 <= result.speed <= 1.2
    assert result.pause_ms >= 0


def test_owner_override_applied():
    p = VoiceDirector().plan(VoiceRequest("hello", Emotion.EXCITED, owner_override=Emotion.FOCUSED))
    assert p.emotion == Emotion.FOCUSED


def test_critical_warning_does_not_sound_playful():
    p = VoiceDirector().plan(VoiceRequest("Warning", Emotion.PLAYFUL, True))
    assert p.emotion == Emotion.URGENT


def test_empty_utterance_rejected():
    with pytest.raises(ValueError):
        VoiceDirector().plan(VoiceRequest(" "))

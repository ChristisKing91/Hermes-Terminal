# LXRION adaptive voice: optional integration seam

This change introduces a **dependency-free speech-plan interface**. It preserves one owner-selected voice identity across six expression modes: neutral, excited, concerned, focused, playful, and urgent.

The owner may override ordinary expression. Safety-critical notices use a calm urgent profile instead of playful or excited delivery. These profiles are presentation metadata, not claims that LXRION has human emotions or can reliably infer a listener's feelings.

No existing CLI, Ollama route, embedding worker, coordinator, microphone, speech runtime, Qt session, or native OS service invokes this module. No external model is downloaded and no voice playback is changed.

A future **independent Adaptive Voice Engine repository** should own TTS backends, optional Kokoro model files, WAV output, performance tests, provider credentials, caching and expressive prosody. LXRION consumes only the stable plan and audio interfaces.

Focused test: pytest -q tests/test_voice_expression.py

This is a safe, reviewable first integration step, not a claim of completed neural voice playback.
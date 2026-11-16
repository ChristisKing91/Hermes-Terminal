# LXRION engineering ecosystem — modular integration roadmap

This file is an engineering plan, not a deployment record. **LXRION OS and LXRION Core remain authoritative.** Do not rebuild working systems or replace the local Windows/Kali coordinator.

## Capability ownership

| Capability | Owner | Rules |
|---|---|---|
| Native OS, Qt, installer, Core | Existing Windows LXRION OS sources | Preserve R1 images and recovery procedures |
| Task ledger, approvals and restricted native worker | Existing Windows AI Development Team | Preserve 214 historical records; deduplicate one authorized embedding job |
| SSH/CLI and optional speech-plan interface | ChristisKing91/Hermes-Terminal | Do not store owner credentials; no direct disk writes |
| Expressive neural speech and backend fallbacks | **Independent Adaptive Voice Engine project** | Stable signature voice, safe emotion styles, offline preference, consented cloud optional |
| Circuit research, datasheets, schematics, power screening | **Independent Hardware Intelligence Lab project** | Cite sources and revisions; require owner approval before physical modifications |
| Camera analytics and board-photo metadata | LeeRoberts-FA/Vision | Preserve privacy and security-camera behavior |
| Legacy Mac Hermes | Inventory still outstanding | Do not claim it was pushed to GitHub or overwrite local copies |

## Architecture research to apply, not import wholesale

- **Microsoft JARVIS/HuggingGPT:** task decomposition, expert-model selection, execution, result synthesis. Heavy default models are inappropriate for the existing HP.
- **OpenJarvis:** pluggable engine and TTS interfaces, local-first inference, persistent provenance, trace-driven model routing, and skill registry.
- **sukeesh/Jarvis:** simple command plugin patterns; its generic system speech is NOT the desired neural voice.
- **Schematik-like hardware workflow:** board identification -> manufacturer datasheet -> power and pinout checks -> schematic -> simulation -> real measurements. Unknowns remain explicitly unknown.

## Interoperability contracts

**Voice v0:** speech text + voice ID + owner-selected mood/urgency -> stable identity, bounded expression parameters and optional rendered audio. A real voice backend must be tested on Windows and Linux for audio quality, latency, interruptions, fallback, and licensing. Plan metadata alone does not produce expressive neural speech.

**Hardware v0:** owner-reviewed photo digest, identified revision, observations, source URLs/dates -> claim provenance, electrical sanity checks, unknowns and testable build plan. Never turn community guesses into validated datasheets. Camera export is metadata-only by default, with no automatic image collection.

**Memory and learning:** retain provenance, source timestamps, measured/observed/inferred status, test results, corrections, and owner privacy boundaries. Retrieval from the Internet is not model training and is not independent verification.

## Acceptance gates

1. From **Windows**, inspect the coordinator ledger for any existing authorized R1 job, authenticate the restricted native worker, and verify exactly one 768-value Nomic receipt. Do NOT use the older kali-lxrion task as native acceptance.
2. Review local-skills, PCM, admin authority, owner-memory isolation and scoped Core/Qt recovery.
3. Independently test neural TTS without changing Microsoft David production fallback until playback is verified.
4. Verify model storage without moving ~37 GiB of model assets to the Kali SSD.
5. Check physical HP networking and recovery and positively identify the Samsung disk before any installation or destructive writes.

## Publication policy

Reusable libraries belong in independent GitHub repositories rather than being copied wholesale into LXRION or Vision. Only small optional integration bridges belong in existing repositories, as unmerged draft PRs. Never push secrets, overwrite drives or claim that a passing GitHub test proves live deployment.

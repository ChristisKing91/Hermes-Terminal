# LXRION Owner Memory — foundation only

## Status and boundaries
This module is an **opt-in development component** of the existing Kali LXRION Terminal portal. It does not replace LXRION Core, the Windows AI Development Team, or the native OS. **The module is not deployed to Kali or an OS image by this PR.**

The existing portal remains local-only, authenticated, and unchanged by default. No existing model is mapped or downloaded. No user data is included in this repository.

## Infrastructure order (before model mapping)
1. Identify authoritative LXRION Core identity, owner authentication, permission boundaries and encrypted owner-data volume in the *canonical native OS source*. Do not repurpose the coordinator database or Seagate model HDD.
2. Make owner memory persistent, explicitly editable, correctable, forgettable, source-attributed and private.
3. Build bounded document ingestion, chunking, local indexing and retrieval; gate access by owner/project context, retain original source references and avoid indexing all files.
4. Define versioned, authenticated Core-to-memory/retrieval contracts. Ensure offline fallback and startup/shutdown persistence.
5. Add integration, redaction, retrieval quality, privacy, model-independence and VM boot tests.
6. **Only then** register the 14 already-downloaded model entries as backends of one LXRION AI identity.

## Local prototype
- Python standard-library SQLite in src/hermes_terminal/owner_memory.py.
- Authenticated endpoints through the **existing** portal token, behind LXRION_OWNER_MEMORY_ENABLED=1 and LXRION_OWNER_MEMORY_DB=/absolute/path/on/encrypted/volume.
- Status, explicit-consent remember, list, literal search, correct, and forget endpoints under /api/memory.
- Memory categories: owner, preferences, projects, devices, workflows.
- Each memory has a key, statement, provenance, revision and update timestamp.
- Change-log rows store action and a digest of key identity, **not previous statement contents**.
- Files are restricted to owner permissions on POSIX. No chat prompt, transcript or coordinator state is automatically stored. No model prompt automatically receives these memories.
- Existing /api/chat and /api/coordinator/snapshot behavior remains unchanged.

### Important security limits
SQLite is **not encrypted by this module**. A mode-0600 file is not disk encryption. Store real owner data only on a verified encrypted filesystem/volume. Do not enable this development prototype for high-sensitivity health, legal, finance, family or credentials data pending a threat model and encrypted-volume/backup validation. Local token authentication does not by itself give per-family-member access controls or revoke compromised tokens. No comprehensive secure deletion from filesystem snapshots/backups is promised.

### Testing
Synthetic tests cover consent, source/revision, persistence, literal search, deletion, private file permissions, disabled/unauthorized HTTP routes and no automatic import. Run on a separate, throwaway test database. Tests passing locally do not establish deployment, native OS compatibility or end-to-end personalization.

## Owner personalization design to add after foundation
- Owner-approved profile facts and communication preferences, with source, scope, freshness and revision.
- Project/hardware decision ledger that honors explicit corrections and avoids reasking settled details.
- Separate private personal/family domains from work, church, ministry and other projects by permission, with explicit sharing boundaries.
- Search results should cite source records and prefer newer owner corrections over stale inferences.
- Human review for imports/auto-suggested memories; explicit consent for sensitive categories.
- Private export, import, correction and delete operations; never publish user data or ingest unrelated files automatically.
- Assistant memory may be seeded only through user-controlled export/approved context; it does **not** inherit ChatGPT account memories automatically.

## Not part of this change
No automatic ChatGPT data transfer, semantic/vector search, background capture, always-on listening, model routing, retrieval prompt injection, service startup, Kali installation, OS image build, or physical disk writes. These are separate acceptance-gated integration phases.

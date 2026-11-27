# LXRION Agentic Stack — phase 1 development portal

**Status: reviewable development branch, not installed LXRION OS/Core.**
This is an optional local console attached to the existing LXRION Terminal package. It
**does not** replace the existing Windows AI Development Team coordinator, Core memory,
task queue, projects, approvals, Ollama setup, source trees, or agent worktrees.

## What works

- Responsive local-first UI served from FastAPI at `http://127.0.0.1:8765/`.
- Protected API with an explicitly configured bearer token; no public listener or CORS.
- Local Ollama model inventory and non-executing development chat, **reusing**
  `hermes_terminal.ai.ollama.OllamaProvider`.
- One-shot **read-only** coordinator metadata observations via the already-developed
  bounded adapter recovered from `audit/work-lxrion-20261031`. The portal never
  returns the coordinator's raw `/api/state` payload.
- Simple process-local operation counts and durations in logs; no prompts or
  coordinator responses logged or persisted.
- Isolated synthetic tests and GitHub Actions checks.

## Install / run on Windows (PowerShell)

Start from a checkout of this **feature branch**, not the installed product directory:

```powershell
git fetch origin feature/lxrion-agentic-stack-20261109
git switch feature/lxrion-agentic-stack-20261109
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev,portal]"
```

Set a long unique development token. Use a per-shell environment variable; do
not commit or paste the value into this repository.

```powershell
$env:LXRION_PORTAL_TOKEN = Read-Host "Enter local portal token"
$env:OLLAMA_BASE_URL = "http://127.0.0.1:11434"
$env:OLLAMA_MODEL = "qwen2.5-coder:7b"
$env:LXRION_COORDINATOR_ROOT = "C:\Users\royre\DevProjects\AI Development Team"
lxrion-portal
```

Open `http://127.0.0.1:8765/`, enter the token in the portal and use **Check
installed models**, **Ask local model**, or **Observe coordinator once**. The
coordinator command is opt-in and requires `LXRION_COORDINATOR_ROOT`; this is
an expected existing local source directory, not an installation instruction.
Your installed model may differ; verify with `ollama list`.

If the coordinator is not running, the portal remains usable for local Ollama
chat. The coordinator observation returns an explicit unavailable status, not a
cached or guessed task list. The read-only adapter never sends a write request.

## Run tests (synthetic only)

```powershell
python -m pytest tests/test_coordinator_snapshot.py tests/test_portal.py -q
```

These tests use fake coordinator transport, fake model responses and temporary
test data. They do **not** test live hardware, the installed Core, remote
providers, physical devices, Linux OS images, or a production release.

## Safety boundary

- Portal binds to **127.0.0.1 only**, with no publicly accessible listener.
- Never expose it through a tunnel, port forward, public reverse proxy or
  shared machine. This phase is **single operator**, not a multiuser auth system.
- Every nonpublic API route checks `LXRION_PORTAL_TOKEN`. A missing token
  disables the route. The browser keeps the entered token in DOM memory only;
  it is never written to localStorage or a cookie.
- `/api/chat` calls the existing Ollama **text generation** provider only.
  It does not expose command execution, MCP tools, task creation, or approval
  endpoints. System prompts limit claims but are **not** an authorization control;
  the missing tool/command interface is the real boundary.
- The coordinator adapter uses exactly one finite local GET, strict field
  selection, limits, and a fixed base URL. It discards source contents,
  messages, untrusted free text, provider secrets, and unverified actions.
- Never turn a task's reported status, historical model selection or
  peer-review flag into proof of Owner approval or deployment.
- No second coordinator, event bus, persistent knowledge store, worker,
  scheduler, vector database or "learning" feed is created.
- Local telemetry counters reset on process restart; no external OpenTelemetry
  exporter or Grafana integration is enabled at this stage.

## Architecture mapping and next integrations

| Diagram layer | Current implementation | Next verified integration |
|---|---|---|
| Frontend | FastAPI-served responsive HTML/JS UI | React/Next.js if a full multi-page product is justified |
| Document ingestion | Not implemented here | Reuse installed Core's document pipeline |
| Preprocessing/chunking | Not implemented here | Reuse team/Core project-aware extraction |
| Embeddings | Not implemented here | Existing approved local embedding route |
| Vector database | No second DB by design | Query authoritative project-scoped retrieval |
| Retrieval | Not duplicated | Add a read-only, versioned retrieval API to Core |
| Prompt engineering | Bounded non-executing system prompt | Versioned, tested prompt policy |
| LLM | Existing Ollama provider, local only | Capability-based routing via existing Team |
| Infrastructure | Loopback FastAPI opt-in | A reviewed native Core integration after acceptance |
| Evaluation | Synthetic tests; local counters | OpenTelemetry, benchmarks, hallucination/evidence tests |

**Next development gate:** Review existing live Core/coordinator API contracts on
the canonical Windows source (not just this public Terminal repo), then connect
retrieval, task planning and model routing through **authenticated, versioned,
least-privilege interfaces**. Run end-to-end tests on a throwaway workspace
before considering release. Do not bulk-publish the uncommitted private native
source, replace any worktree, replay a task, or assume the ISO is production-ready.

## Source preservation

The existing coordinator adapter and synthetic tests on this branch were
carried from the separate prior audit branch, not rewritten. Existing
`feature/lxrion-agent-workbench-20261022` and PR #1 histories are untouched.
This branch is intentionally a reviewable addition based on `main`.

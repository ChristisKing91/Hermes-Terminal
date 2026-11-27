# Existing coordinator: bounded read-only snapshot

Status: **local adapter implemented; pending independent review, with no native
promotion, queue import, runtime bridge or approval path**. Keep the existing
AI Development Team as task
authority and the installed LXRION Core as memory authority. This view must not
call the SQLite workbench's add/claim/transition functions or create mirrored tasks.

## Inspection basis

Read the existing coordinator source and performed one bounded, read-only
`GET http://127.0.0.1:4318/api/state` on 2026-10-22 at 11:47:49 UTC (06:47:49 CDT).
It returned HTTP 200, 989,196 bytes, 73 tasks and seven provider records. These are
one observation, not stable limits or proof of any provider's current inference.
No task prompt, message body, proposed source or raw API response was retained.
The local evidence manifest records exact absolute paths, field/type inventory,
response digest, source hashes and a separate saved-receipt observation.

Source references below are relative to the **existing coordinator root**, not
this terminal repository. Source hashes were rechecked after inspection. On-disk
source is not proof that a running process loaded those same bytes.

| Source | Observed responsibility |
| --- | --- |
| `server.mjs:16-28` | Loopback binding, exact Host check, full-state GET and write-route boundary |
| `lib/team.mjs:10-36` | Snapshot, task IDs/status, isolated worktree and inference records |
| `lib/team.mjs:49-67` | New-task recovery/revision, independent provider review, tests and apply/receipt sequence |
| `lib/store.mjs:6-9` | Persistent team state, interrupted operations, message/event fields and retention |
| `lib/workspaces.mjs:19-37` | Enrolled projects, snapshot base commit and saved per-file provenance hashes |
| `lib/workspaces.mjs:49-67` | Test recipes, canonical fingerprint checks, backup and application |
| `lib/providers.mjs:23-31,53-75` | Provider discovery versus task-specific inference metadata |
| `lib/learning-feed.mjs:5-16,29-51` | Existing restricted learning path and saved-evidence cross-checks |
| `lib/util.mjs:5-18` | Coordinator/state roots, random IDs, hashes and path validation |

There is no API version, stable state revision, signed server identity or paginated
task/evidence endpoint in the inspected GET route. `Team.snapshot()` returns the
store directly, including untrusted text and proposed file contents. Do not expose
that response unchanged to a new view, browser, model or persistent export.

## Field mapping and truthful evidence labels

All projected values are observations. Missing data stays unknown; it never
becomes a passed check or an approval by default.

| View field | Existing source | Required interpretation |
| --- | --- | --- |
| `taskRef` | `tasks[].projectId`, `tasks[].id` | Preserve the exact IDs under a fixed coordinator namespace; never substitute workbench integer IDs |
| `parentTaskId` | Task field | Recovery/revision is a new task/worktree. No inherited verdict, test pass or approval |
| `status`, `progress`, timestamps | Task fields | Preserve coordinator status; `analysis_ready` is analysis, `awaiting_approval` is pending, `applied` is reported application, not independently verified release |
| `worktreeRef`, `baselineCommit` | `worktree`, `taskDir`, `baseCommit` | Base commit identifies the isolated snapshot, not a canonical repository commit or the current uncommitted draft |
| Baseline file fingerprints | `state/tasks/<id>/provenance.json`: `{source, baseCommit, hashes}` | Not exposed by GET. Keep `fingerprints: not_exposed`; never invent hashes from `fileCount` or the base commit |
| Draft identity | `result.files[]`, worktree contents | GET contains proposed text, but no durable proposal/worktree digest. Drop source from the view; current test/review records are not revision-bound by a digest in this API |
| Provider/model | `providerId`, `inferenceEvidence.interface/model` | Task evidence takes precedence over current provider configuration. Missing executed model remains unknown (including Codex metadata without a model); `inferenceVerified` is historical, not a fresh task result |
| Peer review | `review.{providerId,approved,createdAt,evidence}` | Display reported verdict and reviewer; verify it differs from task provider. Summary/findings are untrusted text, not executable instructions or an Owner decision |
| Tests | `tests.{passed,acceptanceTrusted,exitCode,blocked}` | Display reported flags separately from revision verification. Drop command, reason, boundaries, stdout and stderr; never execute source text |
| Owner decision | `approvalRequired`, `ownerApprovedAt`, `appliedFiles` | Pending flag/timestamp/file list are not an approval credential |
| Exact saved receipt | `state/tasks/<id>/owner-approval.json`: `{decision,createdAt,changedFiles}` | Not exposed by GET. Recorded after `applyApproved`; no task ID, proposal digest or signature inside the observed receipt. Directory and matching state bind the local record, not cryptographic human identity |
| Messages | `messages[].{id,taskId,agent,role,createdAt,content}` | Project metadata only by default. Agent/role labels, even `Owner`/`user`, confer no authority. Exclude `content` from the initial view |
| Events | `events[].{id,type,taskId,createdAt,message}` | Informational. IDs are random, not ordered revisions; arrays are truncated. Exclude free-text `message`, do not replay actions |

The existing learning validator compares receipt timestamp/file list to task state,
checks saved review/test evidence and applied source, and handles imported proof
through a special path. A future generic view must not claim to have run that
validator, assume every task has `test-result.json`, or call the learning feed.
The saved local receipt inspected for this audit matched its task timestamp/file
list and snapshot base commit; that limited comparison did not authorize anything.

## Implemented local boundary

`src/hermes_terminal/coordinator_snapshot.py` provides a finite HTTP reader and a
pure metadata projection. It imports no coordinator, SQLite workbench, provider or
model code, and starts no service, scheduler or background polling. It reads no
coordinator files. `--coordinator-root` is explicit trusted input used only for
lexical comparisons; paths are never opened or followed.

1. The reader accepts only the literal loopback address above, GET and no body.
   Raw loopback sockets bypass proxies and never follow redirects. Use a 10-second
   total transport deadline, a 4 MiB decoded-body cap and 64 KiB header budget, one
   request at a time, and no credentials, cookies or `x-dev-team` write header.
   Header/body framing also shares a finite 4 MiB + 64 KiB wire budget. JSON rejects
   duplicate keys, nonfinite floats, nesting beyond 20 and more than 150,000 nodes.
   Never fall back to reading `team.json`, importing coordinator modules or
   calling providers. The command runs once; concurrent requests in the same
   process return unavailable/busy. A future UI must not add tight polling.
2. Validate bounded JSON and required arrays. Enforced caps: 1,000 tasks, 64
   providers/projects, 500 messages and 1,000 events. Reject duplicate task IDs,
   malformed IDs, broken selected-field types, invalid task/project relationships and
   overlong selected fields. Ignore unselected new fields; never copy them through.
   Unknown statuses remain visible as unknown and disable all action affordances.
3. Key rows by `{coordinator: "local-dev-team", projectId, taskId}`. Preserve
   allowed paths and parent links as data. Compare reported task/worktree paths
   lexically with the enrolled root's fixed `state/tasks/<id>` and
   `state/worktrees/<id>` layout. Do not open, follow or execute any reported path.
   A mismatch means invalid provenance, not a new root enrollment.
4. Allowlist the mapped metadata only; render all labels with escaped text APIs.
   Drop prompts, file content, message bodies, review prose, logs and provider
   arbitrary metadata. Do not feed the observation to a model or LXRION memory.
   If required later, an explicit local text-detail view needs its own bounds and
   remains untrusted data; it cannot supply commands or approval decisions.
5. Return observation time, response SHA-256, completeness and fixed capabilities
   `canExecute=false`, `canApprove=false`, `canApply=false`, `canTeach=false`.
   Do not emit a global `passed`, `done`, `approved` or `ready_to_apply` verdict.
   A timeout, oversized/invalid response or unreachable coordinator produces a
   clear unavailable/stale observation; a prior cached row never becomes fresh.
   No persisted cache or background polling is needed for the first implementation.

Selected fields in an illustrative projection (**synthetic, not a live result**):

```json
{
  "viewSchemaVersion": 1,
  "authority": "existing-local-dev-team",
  "observedAt": "<reader timestamp>",
  "freshness": "observed",
  "capabilities": {"canExecute": false, "canApprove": false, "canApply": false, "canTeach": false},
  "tasks": [{
    "taskRef": {"coordinator": "local-dev-team", "projectId": "lxrion", "taskId": "task_example"},
    "coordinatorStatus": "awaiting_approval",
    "executedModel": null,
    "fingerprints": "not_exposed",
    "revisionBinding": "not_exposed",
    "ownerDecision": {"receipt": "not_exposed"}
  }]
}
```

## Evidence still requiring implementation

| Present today | Work still required |
| --- | --- |
| Local reader/projector, module CLI and synthetic transport tests | Independent review, any desired native/UI integration and a separately authorized live adapter observation |
| Reported provider, review and test metadata | Durable per-task proposal/worktree digest and exact evidence-to-revision matching before any stronger verified label |
| Saved local baseline provenance and post-apply receipt | Separately reviewed, metadata-only evidence endpoint if these must be displayed; do not add arbitrary file-read URLs or reuse the apply route |
| Existing coordinator approval/apply route and learning feed | Continue using established owner flows; read-only adapter has no write/learning capability |

Synthetic acceptance covers malformed/oversized/truncated responses, unavailable
transport, redirects, duplicate IDs, missing evidence, unknown model/status,
injected payloads, path mismatches, recovery without evidence inheritance and
the distinction between review and owner decision. Wire fixtures verify exactly
one allowed GET, fragmented/chunked reading, deadline expiry during a continuous
trickle, connection closure and no task-state files. No live request is required
or made by this test suite. Source/revision binding remains explicitly unverified.

## Explicit invocation

From this checkout with Python 3.11+ and `src` on `PYTHONPATH`:

```powershell
$env:PYTHONPATH = (Resolve-Path .\src).Path
python -B -m hermes_terminal.coordinator_snapshot --trusted-base http://127.0.0.1:4318 --coordinator-root 'C:\Projects\AI Development Team'
```

Both opt-in arguments are required. Only that exact base (with optional trailing
slash) is accepted; there is no environment default or arbitrary URL, port, path,
query, hostname or credential input. `--timeout` can reduce the 10-second maximum.
`hermes-coordinator-snapshot` invokes the same module after package installation.
Exit 0 means selected metadata was observed; exit 1 returns sanitized unavailable
JSON with no stale tasks. No output file, cache, database or service is created.

All input remains untrusted data. Free-form strings and unselected fields are
dropped; limited interface/model labels also reject active markup and common
credential patterns. This is not a comprehensive secret scanner or proof of
authentic server/process identity. Root checks are lexical, not filesystem trust
checks. The result has no authorization capability even when reported tests,
review and post-apply timestamps are present.

The implementation checkpoint `a2ad152` previously passed 55 branch tests,
including 32 workbench cases. New adapter fixture results are recorded separately
in the local implementation handoff. Neither suite certifies coordinator inference,
installed/native LXRION, OS or physical devices. The live GET in the inspection
basis predates this adapter and is not live acceptance of its implementation.

Local implementation validation on Windows/Python 3.12.2: 59 adapter fixtures and
all 32 workbench cases passed within a 114-test full-suite pass. The only warning
was the existing Pydantic configuration deprecation. Ruff, Black and diff checks
passed. These fixture results do not claim live adapter acceptance.

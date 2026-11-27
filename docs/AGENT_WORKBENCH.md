# LXRION / Hermes agent workbench

This branch adds a local task ledger to the existing `hermes_terminal` package.
It records goals, roles, acceptance criteria, ownership, checkpoints and evidence.
It does not launch workers, execute task text, call models, install skills, grant
approvals, or rewrite source. Builder, reviewer and tester are coordination roles;
their existence is not proof that any agent is connected or running.

## Relationship to the installed LXRION

This GitHub repository contains the terminal implementation under
`src/hermes_terminal`. The owner's newer native LXRION checkout has a separate
Core, approval system and host-local runtime state. This change is an isolated,
reviewable development component, not an installed native-app update. It does not
replace the existing Core, memory, models, source authority or OS image.

The laptop already has an AI Development Team coordinator. Its local source
describes scheduling, isolated worktrees, provider adapters, peer review, tests
and approval gates. Preserve that coordinator and its established learning feed;
do not launch this ledger as a competing scheduler or memory service. This branch
does not connect to it, enroll a project, exercise its providers or verify its
current runtime health. Any later adapter must be justified against the existing
coordinator's task/state model rather than duplicating it.

A future adapter must preserve the coordinator's project/task IDs, canonical
source fingerprint and detached worktree path. It must reference that task's
trusted test results, independent review and exact Owner approval receipt before
any application. Those fields and an adapter are not implemented by this ledger;
free-text evidence cannot substitute for them. Prefer a read-only view of the
existing queue over two writable task authorities, and test interruption and stale
revision rejection before enabling a bridge. No automatic apply bridge is enabled.

The [read-only coordinator contract](COORDINATOR_READ_ONLY_CONTRACT.md) records a
live GET schema observation, exact field mapping and the separate, opt-in snapshot
module. Its local implementation is pending review, creates no mirrored tasks and
keeps the existing task queue authoritative. It does not connect this SQLite
ledger to the coordinator or the installed Core.

Before native adoption, reconcile source authority and adapt this ledger to the
existing Core's owner/project scope, approvals and storage policy. Review the diff
and prove installed behavior separately. Do not copy another writable brain onto
the OS drive, start a second Core, or treat terminal tests as native acceptance.

## Run without installing the terminal application

Requires Python 3.11 or newer; the workbench itself uses only the standard library.
From this source checkout, PowerShell:

```powershell
$env:PYTHONPATH = (Resolve-Path .\src).Path
$workbenchDir = Join-Path $env:LOCALAPPDATA 'Hermes\development\agent-workbench'
python -m hermes_terminal.workbench --dir $workbenchDir init
python -m hermes_terminal.workbench --dir $workbenchDir add --goal 'Review a bounded patch' --role reviewer --acceptance 'Inspect diff and record test evidence' --priority 5
python -m hermes_terminal.workbench --dir $workbenchDir claim --agent reviewer-1 --role reviewer
python -m hermes_terminal.workbench --dir $workbenchDir checkpoint --id 1 --agent reviewer-1 --note 'Next: inspect the focused test result'
python -m hermes_terminal.workbench --dir $workbenchDir finish --id 1 --agent reviewer-1 --note 'Record the actual result and its limitations here'
python -m hermes_terminal.workbench --dir $workbenchDir status
```

Choose a trusted host-local directory outside source, removable storage and the OS
image. Examples create development task state only. After a normal package install,
`hermes-workbench` invokes the same module without opening the interactive terminal.
No package installation is required for the module commands above.

Directory precedence is `--dir`, then `HERMES_WORKBENCH_DIR`, then the legacy
`~/.config/hermes-terminal/workbench` default. Put `--dir` before the subcommand.
Do not point this path at existing production databases. No live owner state is
needed for tests: use an isolated test directory and temporary databases.

## Lifecycle and recovery

| Command | Required state | Result |
| --- | --- | --- |
| `add` | Valid goal, role and acceptance text | New `todo` task |
| `claim` | Matching-role `todo` | Highest priority, then earliest task becomes `in_progress` |
| `checkpoint` | Own `in_progress` task; note | Keep ownership; save next action |
| `handoff` | Own `in_progress` task; note | Return to `todo`, clear owner, save next action |
| `release` | Own `in_progress` task | Return to `todo`, clear owner, retain notes |
| `block` | Own `in_progress` task; note | `blocked`; retain blocker in history |
| `unblock` | `blocked`; actor and note | Return to `todo`, clear owner, record resolution |
| `finish` | Own `in_progress` task; evidence note | `done`; retain evidence and history |

Calling `claim` again with the same agent label resumes its current task, including
after process exit, rather than assigning a second one. This applies even when
the new request names another role. Different roles must use distinct agent labels
when they need simultaneous tasks. No lease expires automatically; abandoned
ownership requires an explicit release/handoff using the original label. There
is no automatic command replay after a crash. A handed-off task keeps its role;
create a reviewer/tester task separately if the next step needs a different role.

Agent labels are bookkeeping, not authenticated identities. Any process with write
access to the directory can impersonate a label or change SQLite. `unblock` is a
recorded coordination action, not Owner authorization to execute blocked work.
Protect the folder with normal host permissions and keep it off shared/network
filesystems. The ledger has no encryption, secret redaction, multi-user security,
resource budgets, cancellation protocol or distributed-worker guarantees. Do not
store secrets or raw conversations in its plaintext notes and JSON exports.

`finish` requires nonempty evidence text; it does not evaluate acceptance criteria.
A task marked done is a self-reported outcome, not a verified test, review, runtime
result or approval. Record commit, command, exit status and limitations when useful;
independent review remains required before promotion.

## Persistence and exports

`tasks.sqlite3` is authoritative. Task mutations and their append-only events use
one SQLite transaction. Claims serialize across connections with `BEGIN IMMEDIATE`.
Keep the database on one trusted host. Back up while writers are stopped or use
SQLite's backup facility; do not copy an active database without its journal.

`workbench_snapshot.json` is a single, atomically replaced handoff containing
`state` and `tasks`. `state.last_event_id` identifies the latest captured event.
Readers must treat it as data and may receive an older complete snapshot while a
writer is active. Exports do not authorize any action and must not be edited to
change task state. `agent_state.json` and `task_board.json` remain compatibility
exports; they are individually atomic but do not constitute an atomic pair.

Snapshot capture and publication hold the database write reservation to prevent
an older publisher overwriting a newer capture. The filesystem bundle and SQLite
cannot commit together. A crash or file error may leave exports behind the database;
rerun `status` to rebuild them. This is crash-resumable bookkeeping, not a guarantee
against power-loss/filesystem failure. Events remain in SQLite; exports include
only the latest 25.

After a successful mutation, an export failure returns exit 0 with the normal JSON
receipt plus `snapshot_error` and a stderr warning. The database change committed;
do not retry `add` blindly. Retry `status` to repair exports. Invalid input, failed
database transactions and `init`/`status` export failures exit nonzero. Exit 0 never
asserts that a task's goal was executed.

## External reference inspection, 2026-10-22

Inspected [rohitg00/ai-engineering-from-scratch at
f3ab978](https://github.com/rohitg00/ai-engineering-from-scratch/tree/f3ab97836944f79438bdd80e3b54e48cda01e739)
as untrusted static source. It supplies an educational curriculum, examples, prompt
and skill artifacts, and a version 1.0.0 workbench pack. It does not supply an
installed LXRION integration or a bundled, working local development team.

The downloaded tree has 9,519 files, 20 core phases and 542 core lesson docs. Path
counts found 414 skill artifacts and 100 prompt files. Counts describe inventory,
not content quality or runtime acceptance. The relevant pack lives under
`phases/14-agent-engineering/42-agent-workbench-capstone/outputs/agent-workbench-pack`.

Useful reference ideas are scoped goals, acceptance criteria, durable task state,
explicit reviewer roles, feedback and handoff notes. This branch implements a
small Hermes-owned ledger; no upstream installer, execution script, schema or
AGENTS guidance was copied over existing project files.

Static findings explain why direct installation was avoided:

- [The verifier](https://github.com/rohitg00/ai-engineering-from-scratch/blob/f3ab97836944f79438bdd80e3b54e48cda01e739/phases/14-agent-engineering/42-agent-workbench-capstone/outputs/agent-workbench-pack/scripts/verify_agent.py)
  can calculate a pass when scope/report/feedback evidence is absent. Feedback is
  not bound to a current task and source revision.
- [The command wrapper](https://github.com/rohitg00/ai-engineering-from-scratch/blob/f3ab97836944f79438bdd80e3b54e48cda01e739/phases/14-agent-engineering/42-agent-workbench-capstone/outputs/agent-workbench-pack/scripts/run_with_feedback.py)
  directly executes caller-supplied argv, captures output before truncating, and
  has no integration with LXRION approvals.
- [The scaffolder](https://github.com/rohitg00/ai-engineering-from-scratch/blob/f3ab97836944f79438bdd80e3b54e48cda01e739/scripts/scaffold_workbench.py)
  can overwrite existing guidance/scripts when forced.
- [The actual MIT license](https://github.com/rohitg00/ai-engineering-from-scratch/blob/f3ab97836944f79438bdd80e3b54e48cda01e739/LICENSE)
  requires preserving its copyright and permission notice when copying substantial
  source. README wording does not waive that requirement.

Upstream code and dependencies were not executed or installed. This was a focused
static inspection, not a comprehensive security audit. Repository documentation
records findings for future review; it does not update ChatGPT account memory or
the installed LXRION memory database.

## Development checks

Use an isolated environment with pytest installed. From the checkout, set the
source import path explicitly before running the focused regression suite:

```powershell
$env:PYTHONPATH = (Resolve-Path .\src).Path
python -m pytest tests/test_workbench.py -q
```

The full `python -m pytest -q` suite also needs the project's declared dependencies.
Workbench tests use temporary directories and never require live owner memory,
installed LXRION, a running provider, network access or third-party workbench code.
The package entry point should also be checked in a disposable environment with
an explicitly chosen scratch `--dir`. This verifies packaging/CLI behavior only.

"""Work coordination regression tests; every database lives in a temporary directory."""

import json
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from threading import Barrier

import pytest

from hermes_terminal import workbench as wb


@pytest.fixture
def board(tmp_path):
    with closing(wb.connect(tmp_path)) as db:
        yield db


def task(db, task_id):
    return dict(db.execute("SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone())


def event_count(db):
    return db.execute("SELECT count(*) FROM events").fetchone()[0]


def add_task(db, goal="Implement bounded change", role="builder", priority=0):
    return wb.add(db, goal, role, "Focused acceptance checks pass", priority)


def test_claim_orders_by_role_priority_then_creation(board):
    first = add_task(board, "First equal-priority task", priority=5)
    second = add_task(board, "Second equal-priority task", priority=5)
    low = add_task(board, "Lower priority", priority=1)
    reviewer = add_task(board, "Review only", role="reviewer", priority=99)

    assert wb.claim(board, "builder-a", "builder")["id"] == first
    assert wb.claim(board, "builder-b", "builder")["id"] == second
    assert wb.claim(board, "builder-c", "builder")["id"] == low
    assert wb.claim(board, "builder-d", "builder") is None
    assert wb.claim(board, "reviewer-a", "reviewer")["id"] == reviewer


def test_claim_resumes_after_reconnect_even_when_role_changes(tmp_path):
    with closing(wb.connect(tmp_path)) as db:
        original_id = add_task(db)
        waiting_id = add_task(db, role="reviewer")
        wb.claim(db, "worker-a", "builder")
        wb.transition(db, original_id, "worker-a", "checkpoint", "Next: run the focused tests")
        original_event_count = event_count(db)

    with closing(wb.connect(tmp_path)) as db:
        resumed = wb.claim(db, "worker-a", "reviewer")
        assert resumed["id"] == original_id
        assert resumed["next_action"] == "Next: run the focused tests"
        assert event_count(db) == original_event_count
        assert task(db, waiting_id)["status"] == "todo"


def test_checkpoint_handoff_and_finish_preserve_evidence(board):
    task_id = add_task(board)
    wb.claim(board, "builder-a", "builder")
    wb.transition(board, task_id, "builder-a", "checkpoint", "Implementation ready for checks")
    checkpoint = task(board, task_id)
    assert checkpoint["status"] == "in_progress"
    assert checkpoint["claimed_by"] == "builder-a"

    wb.transition(board, task_id, "builder-a", "handoff", "Run acceptance checks and review diff")
    handed_off = task(board, task_id)
    assert handed_off["status"] == "todo"
    assert handed_off["claimed_by"] is None
    assert handed_off["next_action"] == "Run acceptance checks and review diff"
    assert wb.claim(board, "builder-b", "builder")["id"] == task_id

    wb.transition(board, task_id, "builder-b", "finish", "12 focused tests passed; diff reviewed")
    completed = task(board, task_id)
    assert completed["status"] == "done"
    assert completed["evidence"] == "12 focused tests passed; diff reviewed"
    assert wb.claim(board, "builder-c", "builder") is None
    actions = [row[0] for row in board.execute("SELECT action FROM events ORDER BY id")]
    assert actions == ["add", "claim", "checkpoint", "handoff", "claim", "finish"]


def test_blocked_task_requires_explicit_unblock_and_can_be_resumed(board):
    task_id = add_task(board)
    wb.claim(board, "builder-a", "builder")
    wb.transition(board, task_id, "builder-a", "block", "Waiting for acceptance criteria")
    assert wb.claim(board, "builder-b", "builder") is None
    wb.transition(board, task_id, "owner", "unblock", "Acceptance criteria are now supplied")
    unblocked = task(board, task_id)
    assert unblocked["status"] == "todo"
    assert unblocked["claimed_by"] is None
    assert wb.claim(board, "builder-b", "builder")["id"] == task_id
    wb.transition(board, task_id, "builder-b", "finish", "Criteria checked")
    history = [dict(row) for row in board.execute("SELECT * FROM events ORDER BY id")]
    assert history[2]["note"] == "Waiting for acceptance criteria"
    assert history[3]["agent"] == "owner"
    assert history[3]["action"] == "unblock"
    assert history[3]["note"] == "Acceptance criteria are now supplied"


def test_release_keeps_checkpoint_for_next_worker(board):
    task_id = add_task(board)
    wb.claim(board, "builder-a", "builder")
    wb.transition(board, task_id, "builder-a", "checkpoint", "Continue at verification step")
    wb.transition(board, task_id, "builder-a", "release", "")
    assert task(board, task_id)["claimed_by"] is None
    claimed = wb.claim(board, "builder-b", "builder")
    assert claimed["id"] == task_id
    assert claimed["next_action"] == "Continue at verification step"


@pytest.mark.parametrize("action", ["finish", "block", "checkpoint", "handoff", "unblock"])
def test_missing_transition_note_does_not_change_task_or_events(board, action):
    task_id = add_task(board)
    wb.claim(board, "builder-a", "builder")
    if action == "unblock":
        wb.transition(board, task_id, "builder-a", "block", "Needs owner input")
    before, count = task(board, task_id), event_count(board)
    with pytest.raises(ValueError):
        wb.transition(board, task_id, "builder-a", action, " \t")
    assert task(board, task_id) == before
    assert event_count(board) == count
    assert not board.in_transaction


@pytest.mark.parametrize("action", ["finish", "block", "checkpoint", "handoff", "release"])
def test_other_worker_cannot_transition_owned_task(board, action):
    task_id = add_task(board)
    wb.claim(board, "builder-a", "builder")
    before, count = task(board, task_id), event_count(board)
    with pytest.raises(ValueError):
        wb.transition(board, task_id, "builder-b", action, "Unapproved ownership change")
    assert task(board, task_id) == before
    assert event_count(board) == count
    assert not board.in_transaction


def test_unblock_rejects_nonblocked_or_missing_task_and_empty_actor(board):
    task_id = add_task(board)
    for target, actor in [(task_id, "owner"), (9999, "owner"), (task_id, " ")]:
        with pytest.raises(ValueError):
            wb.transition(board, target, actor, "unblock", "Input available")
    assert task(board, task_id)["status"] == "todo"
    assert event_count(board) == 1


@pytest.mark.parametrize(
    "goal,role,acceptance",
    [(" ", "builder", "check"), ("goal", "unknown", "check"), ("goal", "tester", " ")],
)
def test_invalid_task_input_leaves_no_records(board, goal, role, acceptance):
    with pytest.raises(ValueError):
        wb.add(board, goal, role, acceptance, 0)
    assert board.execute("SELECT count(*) FROM tasks").fetchone()[0] == 0
    assert event_count(board) == 0


def test_task_and_event_changes_roll_back_together(board, monkeypatch):
    def broken_record(*args, **kwargs):
        raise sqlite3.OperationalError("injected event write failure")

    with monkeypatch.context() as patch:
        patch.setattr(wb, "record", broken_record)
        with pytest.raises(sqlite3.OperationalError):
            add_task(board)
    assert board.execute("SELECT count(*) FROM tasks").fetchone()[0] == 0
    assert event_count(board) == 0
    assert not board.in_transaction

    task_id = add_task(board)
    with monkeypatch.context() as patch:
        patch.setattr(wb, "record", broken_record)
        with pytest.raises(sqlite3.OperationalError):
            wb.claim(board, "builder-a", "builder")
    assert task(board, task_id)["status"] == "todo"
    assert task(board, task_id)["claimed_by"] is None
    assert event_count(board) == 1

    wb.claim(board, "builder-a", "builder")
    with monkeypatch.context() as patch:
        patch.setattr(wb, "record", broken_record)
        with pytest.raises(sqlite3.OperationalError):
            wb.transition(board, task_id, "builder-a", "finish", "Checks passed")
    assert task(board, task_id)["status"] == "in_progress"
    assert task(board, task_id)["evidence"] == ""
    assert event_count(board) == 2
    assert not board.in_transaction


def test_competing_connections_claim_one_task_only_once(tmp_path):
    with closing(wb.connect(tmp_path)) as db:
        task_id = add_task(db)
    barrier = Barrier(2)

    def compete(agent):
        with closing(wb.connect(tmp_path)) as db:
            barrier.wait(timeout=10)
            return wb.claim(db, agent, "builder")

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(compete, ["builder-a", "builder-b"]))
    winners = [result for result in results if result is not None]
    assert len(winners) == 1
    assert winners[0]["id"] == task_id
    with closing(wb.connect(tmp_path)) as db:
        assert task(db, task_id)["claimed_by"] == winners[0]["claimed_by"]
        assert event_count(db) == 2


def test_snapshot_bundle_matches_database_and_legacy_exports(board, tmp_path):
    task_id = add_task(board)
    wb.claim(board, "builder-a", "builder")
    wb.transition(board, task_id, "builder-a", "checkpoint", "Next: test")
    result = wb.snapshot(board, tmp_path)
    bundle = json.loads((tmp_path / "workbench_snapshot.json").read_text(encoding="utf-8"))
    assert bundle == result
    assert json.loads((tmp_path / "task_board.json").read_text()) == result["tasks"]
    assert json.loads((tmp_path / "agent_state.json").read_text()) == result["state"]
    assert result["tasks"] == [task(board, task_id)]
    assert result["state"]["active_tasks"] == [
        {"id": task_id, "agent": "builder-a", "next_action": "Next: test"}
    ]
    assert result["state"]["recent_events"][0]["action"] == "checkpoint"
    assert not board.in_transaction


def test_snapshot_holds_writer_lock_until_publication(board, tmp_path, monkeypatch):
    add_task(board)
    original = wb.atomic_json
    blocked_writes = []
    with closing(wb.connect(tmp_path)) as competitor:
        competitor.execute("PRAGMA busy_timeout=1")

        def inspect_lock(path, data):
            with pytest.raises(sqlite3.OperationalError, match="locked"):
                competitor.execute("BEGIN IMMEDIATE")
            blocked_writes.append(path.name)
            original(path, data)

        monkeypatch.setattr(wb, "atomic_json", inspect_lock)
        wb.snapshot(board, tmp_path)
        competitor.execute("BEGIN IMMEDIATE")
        competitor.execute("ROLLBACK")
    assert "workbench_snapshot.json" in blocked_writes


def test_snapshot_failure_releases_database_lock(board, tmp_path, monkeypatch):
    add_task(board)

    def fail_export(*args):
        raise OSError("injected export failure")

    monkeypatch.setattr(wb, "atomic_json", fail_export)
    with pytest.raises(OSError, match="injected export failure"):
        wb.snapshot(board, tmp_path)
    assert not board.in_transaction
    with closing(wb.connect(tmp_path)) as competitor:
        assert wb.claim(competitor, "builder-a", "builder") is not None


def test_atomic_export_failure_preserves_previous_file_and_cleans_temp(tmp_path, monkeypatch):
    target = tmp_path / "snapshot.json"
    wb.atomic_json(target, {"generation": "previous"})
    previous = target.read_bytes()

    def fail_replace(*args):
        raise OSError("injected replacement failure")

    monkeypatch.setattr(wb.os, "replace", fail_replace)
    with pytest.raises(OSError):
        wb.atomic_json(target, {"generation": "new"})
    assert target.read_bytes() == previous
    assert sorted(path.name for path in tmp_path.iterdir()) == ["snapshot.json"]


def test_cli_mutation_reports_committed_result_when_snapshot_fails(tmp_path, monkeypatch, capsys):
    def fail_snapshot(*args):
        raise OSError("injected export failure")

    monkeypatch.setattr(wb, "snapshot", fail_snapshot)
    assert (
        wb.main(
            [
                "--dir",
                str(tmp_path),
                "add",
                "--goal",
                "Record a task",
                "--role",
                "builder",
                "--acceptance",
                "Evidence recorded",
            ]
        )
        == 0
    )
    captured = capsys.readouterr()
    result = json.loads(captured.out)
    assert result["created_id"] > 0
    assert "injected export failure" in result["snapshot_error"]
    assert captured.err
    with closing(wb.connect(tmp_path)) as db:
        assert task(db, result["created_id"])["goal"] == "Record a task"
        assert event_count(db) == 1


@pytest.mark.parametrize("command", ["init", "status"])
def test_cli_read_commands_fail_if_no_snapshot_can_be_produced(
    tmp_path,
    monkeypatch,
    capsys,
    command,
):
    def fail_snapshot(*args):
        raise OSError("injected export failure")

    monkeypatch.setattr(wb, "snapshot", fail_snapshot)
    with pytest.raises(SystemExit) as error:
        wb.main(["--dir", str(tmp_path), command])
    assert error.value.code == 1
    captured = capsys.readouterr()
    assert "injected export failure" in captured.err
    assert not captured.out


def test_cli_closes_connection_after_success_and_failure(tmp_path, monkeypatch, capsys):
    original = wb.connect
    opened = []

    def track_connect(directory):
        db = original(directory)
        opened.append(db)
        return db

    monkeypatch.setattr(wb, "connect", track_connect)
    assert wb.main(["--dir", str(tmp_path), "init"]) == 0
    with pytest.raises(SystemExit):
        wb.main(
            [
                "--dir",
                str(tmp_path),
                "finish",
                "--id",
                "999",
                "--agent",
                "builder-a",
                "--note",
                "Not a real task",
            ]
        )
    for db in opened:
        with pytest.raises(sqlite3.ProgrammingError, match="closed"):
            db.execute("SELECT 1")
    capsys.readouterr()


def test_cli_environment_directory_and_explicit_override(tmp_path, monkeypatch, capsys):
    environment_dir = tmp_path / "environment"
    explicit_dir = tmp_path / "explicit"
    monkeypatch.setenv("HERMES_WORKBENCH_DIR", str(environment_dir))
    assert wb.main(["init"]) == 0
    assert (environment_dir / "tasks.sqlite3").exists()
    assert wb.main(["--dir", str(explicit_dir), "status"]) == 0
    assert (explicit_dir / "tasks.sqlite3").exists()
    capsys.readouterr()


def test_cli_legacy_default_is_used_when_environment_is_unset(tmp_path, monkeypatch, capsys):
    monkeypatch.delenv("HERMES_WORKBENCH_DIR", raising=False)
    monkeypatch.setattr(wb, "DEFAULT_DIR", tmp_path)
    assert wb.main(["init"]) == 0
    assert (tmp_path / "tasks.sqlite3").exists()
    capsys.readouterr()


def test_cli_lifecycle_exposes_checkpoint_handoff_and_unblock(tmp_path, capsys):
    def invoke(*args):
        assert wb.main(["--dir", str(tmp_path), *args]) == 0
        return json.loads(capsys.readouterr().out)

    task_id = invoke(
        "add",
        "--goal",
        "Review the bounded integration",
        "--role",
        "reviewer",
        "--acceptance",
        "Review and checks complete",
    )["created_id"]
    assert (
        invoke("claim", "--agent", "reviewer-a", "--role", "reviewer")["claimed"]["id"] == task_id
    )

    def change(action, agent, note):
        return invoke(action, "--id", str(task_id), "--agent", agent, "--note", note)

    change("checkpoint", "reviewer-a", "Diff reviewed; acceptance checks remain")
    change("handoff", "reviewer-a", "Continue with acceptance checks")
    assert (
        invoke("claim", "--agent", "reviewer-b", "--role", "reviewer")["claimed"]["id"] == task_id
    )
    change("block", "reviewer-b", "Need clarified acceptance criteria")
    change("unblock", "owner", "Criteria clarified")
    invoke("claim", "--agent", "reviewer-b", "--role", "reviewer")
    change("finish", "reviewer-b", "Acceptance checks complete")
    status = invoke("status")
    assert status["tasks"][0]["status"] == "done"
    assert status["tasks"][0]["evidence"] == "Acceptance checks complete"
    assert status["state"]["active_tasks"] == []

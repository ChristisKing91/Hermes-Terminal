"""Crash-resumable, multi-agent task coordination without running agent commands.

The SQLite database is authoritative; JSON snapshots are read-only handoffs.
No background process or model invocation is started by this module.
"""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
import tempfile
import sys
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_DIR = Path.home() / ".config" / "hermes-terminal" / "workbench"
ROLES = ("builder", "reviewer", "tester", "human")


def stamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def connect(directory: Path) -> sqlite3.Connection:
    directory.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(directory / "tasks.sqlite3", timeout=20, isolation_level=None)
    try:
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA busy_timeout=20000")
        db.execute(
            """CREATE TABLE IF NOT EXISTS tasks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        goal TEXT NOT NULL, role TEXT NOT NULL, acceptance TEXT NOT NULL,
        priority INTEGER NOT NULL DEFAULT 0,
        status TEXT NOT NULL DEFAULT 'todo'
          CHECK(status IN ('todo','in_progress','blocked','done')),
        claimed_by TEXT, next_action TEXT NOT NULL DEFAULT '',
        evidence TEXT NOT NULL DEFAULT '', updated_at TEXT NOT NULL
    )"""
        )
        db.execute(
            """CREATE TABLE IF NOT EXISTS events (
        id INTEGER PRIMARY KEY AUTOINCREMENT, task_id INTEGER NOT NULL,
        agent TEXT NOT NULL, action TEXT NOT NULL, note TEXT NOT NULL,
        created_at TEXT NOT NULL
    )"""
        )
        return db
    except BaseException:
        db.close()
        raise


def record(db: sqlite3.Connection, task_id: int, agent: str, action: str, note: str = "") -> None:
    db.execute(
        "INSERT INTO events(task_id,agent,action,note,created_at) VALUES(?,?,?,?,?)",
        (task_id, agent, action, note, stamp()),
    )


def add(db: sqlite3.Connection, goal: str, role: str, acceptance: str, priority: int) -> int:
    if not goal.strip() or not acceptance.strip() or role not in ROLES:
        raise ValueError("goal, role and acceptance must be valid and nonempty")
    with db:
        db.execute("BEGIN IMMEDIATE")
        cur = db.execute(
            "INSERT INTO tasks(goal,role,acceptance,priority,updated_at) VALUES(?,?,?,?,?)",
            (goal.strip(), role, acceptance.strip(), priority, stamp()),
        )
        record(db, cur.lastrowid, "human", "add", goal)
        return cur.lastrowid


def claim(db: sqlite3.Connection, agent: str, role: str) -> dict | None:
    if not agent.strip() or role not in ROLES:
        raise ValueError("valid nonempty agent and role required")
    db.execute("BEGIN IMMEDIATE")
    try:
        active = db.execute(
            "SELECT * FROM tasks WHERE status='in_progress' AND claimed_by=? ORDER BY id LIMIT 1",
            (agent,),
        ).fetchone()
        if active:
            db.execute("COMMIT")
            return dict(active)
        row = db.execute(
            "SELECT * FROM tasks WHERE status='todo' AND role=? ORDER BY priority DESC, id ASC LIMIT 1",
            (role,),
        ).fetchone()
        if row is None:
            db.execute("COMMIT")
            return None
        db.execute(
            "UPDATE tasks SET status='in_progress', claimed_by=?, updated_at=? WHERE id=?",
            (agent, stamp(), row["id"]),
        )
        record(db, row["id"], agent, "claim")
        task = db.execute("SELECT * FROM tasks WHERE id=?", (row["id"],)).fetchone()
        db.execute("COMMIT")
        return dict(task)
    except BaseException:
        db.execute("ROLLBACK")
        raise


def transition(db: sqlite3.Connection, task_id: int, agent: str, action: str, note: str) -> None:
    if not agent.strip():
        raise ValueError("agent required")
    if action in ("finish", "block", "checkpoint", "handoff", "unblock") and not note.strip():
        raise ValueError("evidence, blocker, or next action required")
    db.execute("BEGIN IMMEDIATE")
    try:
        task = db.execute("SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone()
        if action == "unblock":
            if not task or task["status"] != "blocked":
                raise ValueError("task must be blocked before it can be unblocked")
            db.execute(
                "UPDATE tasks SET status='todo', claimed_by=NULL, next_action=?, updated_at=? WHERE id=?",
                (note.strip(), stamp(), task_id),
            )
        elif not task or task["claimed_by"] != agent or task["status"] != "in_progress":
            raise ValueError("task must be in progress and owned by this agent")
        elif action == "finish":
            db.execute(
                "UPDATE tasks SET status='done', evidence=?, updated_at=? WHERE id=?",
                (note.strip(), stamp(), task_id),
            )
        elif action == "block":
            db.execute(
                "UPDATE tasks SET status='blocked', next_action=?, updated_at=? WHERE id=?",
                (note.strip(), stamp(), task_id),
            )
        elif action == "release":
            db.execute(
                "UPDATE tasks SET status='todo', claimed_by=NULL, updated_at=? WHERE id=?",
                (stamp(), task_id),
            )
        elif action == "handoff":
            db.execute(
                "UPDATE tasks SET status='todo', claimed_by=NULL, next_action=?, updated_at=? WHERE id=?",
                (note.strip(), stamp(), task_id),
            )
        elif action == "checkpoint":
            db.execute(
                "UPDATE tasks SET next_action=?, updated_at=? WHERE id=?",
                (note.strip(), stamp(), task_id),
            )
        else:
            raise ValueError("invalid transition")
        record(db, task_id, agent, action, note)
        db.execute("COMMIT")
    except BaseException:
        db.execute("ROLLBACK")
        raise


def atomic_json(path: Path, data: object) -> None:
    fd, temp = tempfile.mkstemp(dir=path.parent, prefix=path.name + ".")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as out:
            json.dump(data, out, indent=2)
            out.write("\n")
            out.flush()
            os.fsync(out.fileno())
        os.replace(temp, path)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)


def snapshot(db: sqlite3.Connection, directory: Path) -> dict:
    # Serialize readers/publishers with task writers so an older capture cannot
    # overwrite a newer one. Consumers use the single complete snapshot file;
    # the two legacy exports cannot form an atomic pair on the filesystem.
    db.execute("BEGIN IMMEDIATE")
    try:
        tasks = [dict(row) for row in db.execute("SELECT * FROM tasks ORDER BY priority DESC,id")]
        events = [dict(row) for row in db.execute("SELECT * FROM events ORDER BY id DESC LIMIT 25")]
        state = {
            "schema_version": 1,
            "updated_at": stamp(),
            "last_event_id": events[0]["id"] if events else 0,
            "active_tasks": [
                {"id": t["id"], "agent": t["claimed_by"], "next_action": t["next_action"]}
                for t in tasks
                if t["status"] == "in_progress"
            ],
            "recent_events": events,
        }
        board = {"state": state, "tasks": tasks}
        atomic_json(directory / "agent_state.json", state)
        atomic_json(directory / "task_board.json", tasks)
        atomic_json(directory / "workbench_snapshot.json", board)
        db.execute("COMMIT")
        return board
    except BaseException:
        db.execute("ROLLBACK")
        raise


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Hermes/LXRION agent workbench (coordination only)"
    )
    parser.add_argument(
        "--dir", type=Path, default=Path(os.environ.get("HERMES_WORKBENCH_DIR", str(DEFAULT_DIR)))
    )
    cmds = parser.add_subparsers(dest="command", required=True)
    cmds.add_parser("init")
    cmds.add_parser("status")
    new = cmds.add_parser("add")
    new.add_argument("--goal", required=True)
    new.add_argument("--role", choices=ROLES, required=True)
    new.add_argument("--acceptance", required=True)
    new.add_argument("--priority", type=int, default=0)
    take = cmds.add_parser("claim")
    take.add_argument("--agent", required=True)
    take.add_argument("--role", choices=ROLES, required=True)
    for cmd in ("finish", "block", "checkpoint", "handoff", "release", "unblock"):
        sub = cmds.add_parser(cmd)
        sub.add_argument("--id", type=int, required=True)
        sub.add_argument("--agent", required=True)
        if cmd != "release":
            sub.add_argument("--note", required=True)
    args = parser.parse_args(argv)
    try:
        with closing(connect(args.dir)) as db:
            if args.command == "add":
                result = {
                    "created_id": add(db, args.goal, args.role, args.acceptance, args.priority)
                }
            elif args.command == "claim":
                result = {"claimed": claim(db, args.agent, args.role)}
            elif args.command in ("finish", "block", "checkpoint", "handoff", "release", "unblock"):
                transition(db, args.id, args.agent, args.command, getattr(args, "note", ""))
                result = {"updated_id": args.id, "action": args.command}
            else:
                result = {"ok": True}
            try:
                board = snapshot(db, args.dir)
            except (sqlite3.Error, OSError) as exc:
                if args.command in ("init", "status"):
                    raise
                # The mutation and its event have committed. Preserve the success
                # receipt so a retry of add does not silently duplicate the task.
                result["snapshot_error"] = str(exc)
                print(
                    f"workbench warning: database committed; snapshot failed: {exc}",
                    file=sys.stderr,
                )
                print(json.dumps(result, indent=2))
                return 0
            if args.command == "status":
                result = board
            print(json.dumps(result, indent=2))
        return 0
    except (ValueError, sqlite3.Error, OSError) as exc:
        parser.exit(1, f"workbench error: {exc}\n")


if __name__ == "__main__":
    raise SystemExit(main())

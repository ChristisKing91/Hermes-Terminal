#!/usr/bin/python3
"""Restricted SSH worker for the existing Kali loopback embedding portal."""

from __future__ import annotations

import contextlib
import hashlib
import http.client
import json
import math
import os
from pathlib import Path
import re
import select
import signal
import sqlite3
import stat
import subprocess
import sys
import time


WORKER_ID = "kali-lxrion"
MODEL = "nomic-embed-text:latest"
DIMENSIONS = 768
MAX_REQUEST_BYTES = 16 * 1024
MAX_RESPONSE_BYTES = 24 * 1024
MAX_PORTAL_BYTES = 64 * 1024
MAX_DEADLINE_MS = 120_000
MAX_LEDGER_ROWS = 4096
TASK_ID_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}")
REVISION_PATTERN = re.compile(r"[0-9a-f]{40}")
TOKEN_PATTERN = re.compile(rb"[!-~]{1,1024}")
BASE_FIELDS = {"version", "operation"}
EMBEDDING_FIELDS = BASE_FIELDS | {"taskId", "deadlineMs", "text"}


class InvalidRequest(ValueError):
    pass


class TimeLimit(TimeoutError):
    pass


def json_bytes(value):
    return json.dumps(value, ensure_ascii=True, separators=(",", ":"), allow_nan=False).encode("ascii")


def reject_duplicates(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise InvalidRequest("duplicate JSON member")
        result[key] = value
    return result


def decode_request(data):
    if len(data) > MAX_REQUEST_BYTES or not data.endswith(b"\n") or data.count(b"\n") != 1:
        raise InvalidRequest("expected one bounded JSON line")
    try:
        request = json.loads(data.decode("utf-8"), object_pairs_hook=reject_duplicates)
    except (UnicodeError, ValueError, RecursionError) as error:
        raise InvalidRequest("invalid JSON") from error
    if not isinstance(request, dict) or type(request.get("version")) is not int or request["version"] != 1:
        raise InvalidRequest("invalid protocol version")
    operation = request.get("operation")
    if operation == "discover" and request.keys() == BASE_FIELDS:
        return request
    if operation != "embedding" or request.keys() != EMBEDDING_FIELDS:
        raise InvalidRequest("unknown operation or request member")
    task_id, deadline, text = request["taskId"], request["deadlineMs"], request["text"]
    if not isinstance(task_id, str) or not TASK_ID_PATTERN.fullmatch(task_id):
        raise InvalidRequest("invalid task ID")
    if type(deadline) is not int or deadline < 1:
        raise InvalidRequest("invalid deadline")
    if not isinstance(text, str) or not 1 <= len(text) <= 1200 or not text.strip():
        raise InvalidRequest("invalid text")
    try:
        text.encode("utf-8")
    except UnicodeError as error:
        raise InvalidRequest("invalid text encoding") from error
    return request


def read_request(fd):
    expires = time.monotonic() + 5
    data = bytearray()
    while len(data) <= MAX_REQUEST_BYTES:
        remaining = expires - time.monotonic()
        if remaining <= 0 or not select.select([fd], [], [], remaining)[0]:
            raise InvalidRequest("input timed out")
        chunk = os.read(fd, min(4096, MAX_REQUEST_BYTES + 1 - len(data)))
        if not chunk:
            return decode_request(bytes(data))
        data.extend(chunk)
    raise InvalidRequest("request exceeds maximum size")


def checkout_revision(home):
    git = ["/usr/bin/git", "-C", str(home / "LXRION" / "Hermes-Terminal")]
    environment = {"PATH": "/usr/bin:/bin", "HOME": str(home), "LC_ALL": "C"}
    options = {"stderr": subprocess.DEVNULL, "stdin": subprocess.DEVNULL, "env": environment, "timeout": 2, "check": True}
    result = subprocess.run([*git, "rev-parse", "--verify", "HEAD"], stdout=subprocess.PIPE, **options)
    revision = result.stdout.decode("ascii").strip()
    if not REVISION_PATTERN.fullmatch(revision):
        raise ValueError("invalid checkout revision")
    subprocess.run([*git, "diff-index", "--quiet", revision, "--"], stdout=subprocess.DEVNULL, **options)
    return revision


def verify_private(info, *, directory=False):
    expected_kind = stat.S_ISDIR if directory else stat.S_ISREG
    expected_mode = 0o700 if directory else 0o600
    if (
        not expected_kind(info.st_mode)
        or info.st_uid != os.getuid()
        or stat.S_IMODE(info.st_mode) != expected_mode
        or (not directory and info.st_nlink != 1)
    ):
        raise PermissionError("worker state is not private")


def portal_token(home):
    directory = home / ".config" / "lxrion-worker"
    verify_private(directory.lstat(), directory=True)
    descriptor = os.open(directory / "portal-token", os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(descriptor, "rb") as source:
        verify_private(os.fstat(source.fileno()))
        token = source.read(1026).removesuffix(b"\n")
    if not TOKEN_PATTERN.fullmatch(token):
        raise ValueError("invalid worker portal credential")
    return token.decode("ascii")


def interrupt_on_timeout(_signum, _frame):
    raise TimeLimit("portal request timed out")


@contextlib.contextmanager
def bounded_time(seconds):
    if seconds <= 0:
        raise TimeLimit("request deadline passed")
    old_handler = signal.signal(signal.SIGALRM, interrupt_on_timeout)
    try:
        signal.setitimer(signal.ITIMER_REAL, seconds)
        yield
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, old_handler)


def portal_request(method, path, token, seconds, *, body=None):
    headers = {"Authorization": "Bearer " + token, "Accept": "application/json"}
    if body is not None:
        headers["Content-Type"] = "application/json"
    with bounded_time(seconds):
        with contextlib.closing(http.client.HTTPConnection("127.0.0.1", 8765, timeout=seconds)) as connection:
            connection.request(method, path, body=body, headers=headers)
            with connection.getresponse() as response:
                if response.status != 200 and (method, response.status) != ("POST", 503):
                    return response.status, None
                raw = response.read(MAX_PORTAL_BYTES + 1)
                if len(raw) > MAX_PORTAL_BYTES:
                    raise ValueError("portal response exceeds limit")
                return response.status, json.loads(raw, object_pairs_hook=reject_duplicates)


def installed_embedding(document):
    models = document.get("models") if isinstance(document, dict) else None
    if not isinstance(models, list):
        return False
    return any(
        isinstance(entry, dict)
        and entry.get("model") == MODEL
        and entry.get("installed") is True
        and isinstance(entry.get("declaredCapabilities"), list)
        and "embedding" in entry["declaredCapabilities"]
        for entry in models
    )


def portal_embedding(document):
    if (
        not isinstance(document, dict)
        or document.get("model") != MODEL
        or type(document.get("dimensions")) is not int
        or document["dimensions"] != DIMENSIONS
    ):
        raise ValueError("unexpected embedding metadata")
    values = document.get("embedding")
    if not isinstance(values, list) or len(values) != DIMENSIONS:
        raise ValueError("unexpected vector dimensions")
    if not all(type(value) in (int, float) and math.isfinite(value) for value in values):
        raise ValueError("invalid vector values")
    return values


@contextlib.contextmanager
def open_ledger(home):
    import fcntl

    directory = home / ".config" / "lxrion-worker"
    verify_private(directory.lstat(), directory=True)
    lock_fd = os.open(directory / "ledger.lock", os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW | os.O_NONBLOCK, 0o600)
    try:
        verify_private(os.fstat(lock_fd))
        fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        path = directory / "ledger.sqlite3"
        db_fd = os.open(path, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW | os.O_NONBLOCK, 0o600)
        try:
            verify_private(os.fstat(db_fd))
        finally:
            os.close(db_fd)
        with contextlib.closing(sqlite3.connect(path, timeout=0)) as database:
            database.execute("PRAGMA synchronous = FULL")
            initialize_ledger(database)
            yield database
    finally:
        os.close(lock_fd)


def initialize_ledger(database):
    database.execute(
        "CREATE TABLE IF NOT EXISTS tasks (task_id TEXT PRIMARY KEY, request_hash TEXT NOT NULL, response BLOB)"
    )
    database.commit()


def epoch_ms():
    return time.time_ns() // 1_000_000


def response_base(operation, revision, **fields):
    return {"version": 1, "operation": operation, "workerId": WORKER_ID, "revision": revision, **fields}


PORTAL_FAILURES = (OSError, http.client.HTTPException, ValueError, RecursionError, OverflowError)


def discover(home, revision):
    try:
        status, document = portal_request("GET", "/api/model-capabilities", portal_token(home), 4)
        capabilities = ["embedding"] if status == 200 and installed_embedding(document) else []
    except PORTAL_FAILURES:
        capabilities = []
    return response_base("discover", revision, capabilities=capabilities)


def embedding(request, home, revision):
    base = response_base("embedding", revision, taskId=request["taskId"])
    expires = request["deadlineMs"]
    remaining = expires - epoch_ms()
    if remaining <= 0:
        return {**base, "status": "deadline_exceeded"}
    if remaining > MAX_DEADLINE_MS:
        return {**base, "status": "invalid_request"}
    try:
        with open_ledger(home) as database:
            return run_embedding(request, base, home, database)
    except BlockingIOError:
        return {**base, "status": "busy"}
    except (OSError, sqlite3.Error, ValueError):
        return {**base, "status": "unavailable"}


def run_embedding(request, base, home, database):
    task_id = request["taskId"]
    expires = request["deadlineMs"]
    request_hash = hashlib.sha256(json_bytes({key: request[key] for key in sorted(request)})).hexdigest()
    previous = database.execute("SELECT request_hash, response FROM tasks WHERE task_id = ?", (task_id,)).fetchone()
    if previous is not None:
        if previous[0] != request_hash:
            return {**base, "status": "conflict"}
        if previous[1] is None:
            return {**base, "status": "execution_unknown"}
        result = json.loads(previous[1])
        if result.get("revision") != base["revision"]:
            return {**base, "status": "execution_unknown"}
        return result

    if database.execute("SELECT COUNT(*) FROM tasks").fetchone()[0] >= MAX_LEDGER_ROWS:
        return {**base, "status": "unavailable"}
    try:
        token = portal_token(home)
        seconds = min(4, (expires - epoch_ms()) / 1000)
        status, document = portal_request("GET", "/api/model-capabilities", token, seconds)
    except PORTAL_FAILURES:
        status, document = 0, None
    if expires <= epoch_ms():
        return {**base, "status": "deadline_exceeded"}
    if status != 200 or not installed_embedding(document):
        return {**base, "status": "unavailable"}

    database.execute("INSERT INTO tasks (task_id, request_hash) VALUES (?, ?)", (task_id, request_hash))
    database.commit()
    seconds = (expires - epoch_ms()) / 1000
    if seconds <= 0:
        database.execute("DELETE FROM tasks WHERE task_id = ?", (task_id,))
        database.commit()
        return {**base, "status": "deadline_exceeded"}
    try:
        status, document = portal_request(
            "POST", "/api/embeddings", token, seconds, body=json_bytes({"text": request["text"]})
        )
        detail = document.get("detail") if isinstance(document, dict) else None
        rejection = None
        if status == 429:
            rejection = "busy"
        elif status == 503 and isinstance(detail, dict) and detail.get("code") == "model_unavailable":
            rejection = "unavailable"
        if rejection is not None:
            database.execute("DELETE FROM tasks WHERE task_id = ?", (task_id,))
            database.commit()
            return {**base, "status": rejection}
        if status != 200:
            return {**base, "status": "execution_unknown"}
        result = {**base, "status": "ok", "model": MODEL, "embedding": portal_embedding(document)}
        encoded = json_bytes(result)
        if len(encoded) + 1 > MAX_RESPONSE_BYTES:
            return {**base, "status": "execution_unknown"}
        database.execute("UPDATE tasks SET response = ? WHERE task_id = ?", (encoded, task_id))
        database.commit()
        return result
    except PORTAL_FAILURES + (sqlite3.Error,):
        return {**base, "status": "execution_unknown"}


def main():
    os.umask(0o077)
    if os.environ.get("SSH_ORIGINAL_COMMAND"):
        return 2
    try:
        request = read_request(sys.stdin.fileno())
        home = Path.home()
        revision = checkout_revision(home)
    except (OSError, ValueError, subprocess.SubprocessError):
        return 2
    result = discover(home, revision) if request["operation"] == "discover" else embedding(request, home, revision)
    sys.stdout.buffer.write(json_bytes(result) + b"\n")
    sys.stdout.buffer.flush()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

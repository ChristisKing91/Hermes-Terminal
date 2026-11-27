"""Opt-in, finite metadata observation of the existing local coordinator.

No coordinator modules, ledger, provider, database or write route is used.
All evidence in the result is reported data, never an execution/approval grant.
"""

from __future__ import annotations

import argparse
import hashlib
import http.client
import io
import json
import math
import re
import socket
import threading
import time
from datetime import datetime, timezone
from pathlib import PurePosixPath, PureWindowsPath

TRUSTED_BASE = "http://127.0.0.1:4318"
MAX_BYTES = 4 * 1024 * 1024
HEADER_BYTES = 64 * 1024
CAPABILITIES = {"canExecute": False, "canApprove": False, "canApply": False, "canTeach": False}
STATUSES = frozenset(
    "queued running reviewing testing waiting_provider interrupted failed analysis_ready "
    "awaiting_review awaiting_approval changes_requested applied rejected".split()
)
_REQUEST_LOCK = threading.Lock()
_now = time.monotonic
_SECRET = re.compile(
    r"sk-(?:proj-)?[A-Za-z0-9_-]{8,}|gh[pousr]_[A-Za-z0-9_]{8,}|github_pat_|"
    r"AIza[A-Za-z0-9_-]{12,}|(?:AKIA|ASIA)[A-Z0-9]{16}|"
    r"eyJ[A-Za-z0-9_-]{12,}\.[A-Za-z0-9_-]{12,}\.[A-Za-z0-9_-]{12,}|"
    r"\b(?:bearer|password|credential|secret|token)\b|-----BEGIN",
    re.I,
)


class SnapshotError(ValueError):
    """Contains a fixed error code, never remote text or a supplied path."""


def _fail(code="invalid_schema"):
    raise SnapshotError(code)


def _text(value, limit=160):
    if not isinstance(value, str) or not value or len(value) > limit:
        _fail()
    if any(ord(char) < 32 for char in value):
        _fail()
    return value


def _identifier(value, *, task=False):
    value = _text(value, 70)
    if not re.fullmatch(r"[a-z0-9_]{1,70}" if task else r"[a-z0-9_-]{1,70}", value):
        _fail()
    if _SECRET.search(value):
        _fail()
    return value


def _label(value):
    # Unknown/free-form metadata is discarded rather than copied or interpreted.
    if value is None:
        return None
    if not isinstance(value, str) or len(value) > 160:
        _fail()
    if not re.fullmatch(r"[A-Za-z0-9 /._:+-]{1,160}", value) or _SECRET.search(value):
        return None
    return value


def _boolean(obj, key):
    value = obj.get(key)
    if value is not None and not isinstance(value, bool):
        _fail()
    return value


def _timestamp(obj, key):
    value = obj.get(key)
    if value is None:
        return None
    value = _text(value, 40)
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if "T" not in value or parsed.utcoffset() is None:
            _fail()
    except ValueError:
        _fail()
    return value


def _object(value):
    if not isinstance(value, dict):
        _fail()
    return value


def _array(value, limit):
    if not isinstance(value, list) or len(value) > limit:
        _fail()
    return value


def _paths(value):
    paths = _array(value, 128)
    for item in paths:
        item = _text(item, 220)
        if (
            not re.fullmatch(r"[A-Za-z0-9_./ -]+", item)
            or item.startswith("/")
            or any(part in ("", ".", "..") for part in item.split("/"))
            or any(part.lower().startswith(".env") for part in item.split("/"))
            or _SECRET.search(item)
        ):
            _fail()
    return list(paths)


def _root(value):
    value = _text(value, 1024)
    path_type = PureWindowsPath if re.match(r"^[A-Za-z]:[\\/]", value) else PurePosixPath
    path = path_type(value)
    if not path.is_absolute() or ".." in path.parts or value.startswith(("\\\\", "//")):
        _fail("invalid_configuration")
    return path


def _path_matches(value, expected):
    if value is None:
        return None
    value = _text(value, 1024)
    if ".." in type(expected)(value).parts:
        return False
    return type(expected)(value) == expected


def _metadata(value):
    value = _object(value)
    return {"interface": _label(value.get("interface")), "model": _label(value.get("model"))}


def _base(observed_at=None):
    return {
        "viewSchemaVersion": 1,
        "authority": "existing-local-dev-team",
        "observedAt": observed_at or datetime.now(timezone.utc).isoformat(),
        "capabilities": dict(CAPABILITIES),
    }


def project_snapshot(document, *, coordinator_root, observed_at=None):
    """Pure projection: validate selected fields and drop all unselected content."""
    root = _root(coordinator_root)
    document = _object(document)
    arrays = {
        key: _array(document.get(key), limit)
        for key, limit in {
            "projects": 64,
            "providers": 64,
            "tasks": 1000,
            "messages": 500,
            "events": 1000,
        }.items()
    }
    projects, providers = {}, {}
    for key, output in (("projects", projects), ("providers", providers)):
        for raw in arrays[key]:
            item = _object(raw)
            identity = _identifier(item.get("id"))
            if identity in output:
                _fail()
            output[identity] = {"id": identity}
            if key == "providers":
                status = _identifier(item.get("status"))
                output[identity].update(
                    status=(
                        status if status in ("available", "unavailable", "blocked") else "unknown"
                    ),
                    historicalInferenceReported=_boolean(item, "inferenceVerified"),
                )
    tasks, identities = [], set()
    for raw in arrays["tasks"]:
        task = _object(raw)
        identity = _identifier(task.get("id"), task=True)
        project_id = _identifier(task.get("projectId"))
        provider_id = _identifier(task.get("providerId"))
        if identity in identities or project_id not in projects:
            _fail()
        identities.add(identity)
        status = _identifier(task.get("status"))
        progress = task.get("progress")
        if (
            not isinstance(progress, (int, float))
            or isinstance(progress, bool)
            or not 0 <= progress <= 100
        ):
            _fail()
        base_commit = task.get("baseCommit")
        if base_commit is not None and (
            not isinstance(base_commit, str)
            or not re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}", base_commit)
        ):
            _fail()
        parent = task.get("parentTaskId")
        if parent is not None:
            parent = _identifier(parent, task=True)
            if parent == identity:
                _fail()
        inference = (
            _metadata(task["inferenceEvidence"])
            if task.get("inferenceEvidence") is not None
            else None
        )
        review = None
        if task.get("review") is not None:
            raw_review = _object(task["review"])
            reviewer = _identifier(raw_review.get("providerId"))
            review = {
                "providerId": reviewer,
                "approvedReported": _boolean(raw_review, "approved"),
                "differentProvider": reviewer != provider_id,
                "createdAt": _timestamp(raw_review, "createdAt"),
                "inference": (
                    _metadata(raw_review["evidence"])
                    if raw_review.get("evidence") is not None
                    else None
                ),
                "revisionBinding": "not_exposed",
            }
        tests = None
        if task.get("tests") is not None:
            raw_tests = _object(task["tests"])
            exit_code = raw_tests.get("exitCode")
            if exit_code is not None and (
                not isinstance(exit_code, int)
                or isinstance(exit_code, bool)
                or not -(2**31) <= exit_code < 2**31
            ):
                _fail()
            tests = {
                "passedReported": _boolean(raw_tests, "passed"),
                "acceptanceTrustedReported": _boolean(raw_tests, "acceptanceTrusted"),
                "blockedReported": _boolean(raw_tests, "blocked"),
                "exitCodeReported": exit_code,
                "revisionBinding": "not_exposed",
            }
        tasks.append(
            {
                "taskRef": {
                    "coordinator": "local-dev-team",
                    "projectId": project_id,
                    "taskId": identity,
                },
                "parentTaskId": parent,
                "coordinatorStatus": status if status in STATUSES else "unknown",
                "statusRecognized": status in STATUSES,
                "progressReported": progress,
                "createdAt": _timestamp(task, "createdAt"),
                "completedAt": _timestamp(task, "completedAt"),
                "baselineCommit": base_commit,
                "worktreeRef": {
                    "relativePath": f"state/worktrees/{identity}",
                    "worktreeMatchesLayout": _path_matches(
                        task.get("worktree"), root / "state" / "worktrees" / identity
                    ),
                    "taskDirMatchesLayout": _path_matches(
                        task.get("taskDir"), root / "state" / "tasks" / identity
                    ),
                    "check": "lexical_only",
                },
                "allowedPaths": _paths(task.get("allowedPaths", [])),
                "providerId": provider_id,
                "providerListed": provider_id in providers,
                "inference": inference,
                "executedModel": inference["model"] if inference else None,
                "review": review,
                "tests": tests,
                "ownerDecision": {
                    "approvalRequiredReported": _boolean(task, "approvalRequired"),
                    "ownerApprovedAtReported": _timestamp(task, "ownerApprovedAt"),
                    "appliedFilesReported": _paths(task.get("appliedFiles", [])),
                    "receipt": "not_exposed",
                },
                "fingerprints": "not_exposed",
                "revisionBinding": "not_exposed",
            }
        )
    # Preserve relationships without copying message bodies, actor labels or event prose.
    metadata = {}
    for key in ("messages", "events"):
        rows, seen = [], set()
        for raw in arrays[key]:
            item = _object(raw)
            identity = _identifier(item.get("id"), task=True)
            if identity in seen:
                _fail()
            seen.add(identity)
            task_id = item.get("taskId")
            if task_id is not None:
                task_id = _identifier(task_id, task=True)
            rows.append(
                {
                    "id": identity,
                    "taskId": task_id,
                    "taskListed": task_id in identities if task_id else None,
                    "createdAt": _timestamp(item, "createdAt"),
                }
            )
        metadata[key] = rows
    result = _base(observed_at)
    result.update(
        freshness="observed",
        completeness="selected_metadata_only",
        projects=list(projects.values()),
        providers=list(providers.values()),
        tasks=tasks,
        **metadata,
    )
    return result


class _DeadlineReader(io.RawIOBase):
    def __init__(self, connection, deadline):
        self.connection, self.deadline = connection, deadline
        self.bytes_read, self.limit = 0, HEADER_BYTES

    def readable(self):
        return True

    def remaining(self):
        remaining = self.deadline - _now()
        if remaining <= 0:
            _fail("timeout")
        return remaining

    def readinto(self, target):
        self.connection.settimeout(self.remaining())
        remaining_bytes = self.limit - self.bytes_read
        if remaining_bytes <= 0:
            _fail("response_too_large")
        count = self.connection.recv_into(memoryview(target)[:remaining_bytes])
        self.bytes_read += count
        self.remaining()
        return count


class _ResponseSocket:
    def __init__(self, reader):
        self.reader = reader

    def makefile(self, mode):
        return io.BufferedReader(self.reader)


def _open_connection(timeout):
    return socket.create_connection(("127.0.0.1", 4318), timeout=timeout)


def _read_response(timeout):
    deadline = _now() + timeout
    with _open_connection(timeout) as connection:
        reader = _DeadlineReader(connection, deadline)
        connection.settimeout(reader.remaining())
        connection.sendall(
            b"GET /api/state HTTP/1.1\r\nHost: 127.0.0.1:4318\r\n"
            b"Accept: application/json\r\nAccept-Encoding: identity\r\nConnection: close\r\n\r\n"
        )
        with http.client.HTTPResponse(_ResponseSocket(reader)) as response:
            response.begin()
            reader.remaining()
            if response.status != 200:
                _fail("http_status")
            if response.headers.get_content_type() != "application/json":
                _fail("content_type")
            if response.headers.get("Content-Encoding", "identity").lower() != "identity":
                _fail("content_encoding")
            lengths = response.headers.get_all("Content-Length", [])
            transfers = response.headers.get_all("Transfer-Encoding", [])
            if len(lengths) > 1 or len(transfers) > 1 or (lengths and transfers):
                _fail("invalid_http")
            if transfers and transfers[0].lower() != "chunked":
                _fail("invalid_http")
            expected = None
            if lengths:
                if not re.fullmatch(r"[0-9]{1,10}", lengths[0]):
                    _fail("invalid_http")
                expected = int(lengths[0])
                if expected > MAX_BYTES:
                    _fail("response_too_large")
            reader.limit = MAX_BYTES + HEADER_BYTES
            body = bytearray()
            while True:
                reader.remaining()
                chunk = response.read1(min(65536, MAX_BYTES + 1 - len(body)))
                reader.remaining()
                if not chunk:
                    break
                body.extend(chunk)
                if len(body) > MAX_BYTES:
                    _fail("response_too_large")
            if expected is not None and len(body) != expected:
                _fail("invalid_http")
            return bytes(body)


def _decode(body):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                _fail("invalid_json")
            result[key] = value
        return result

    def constant(value):
        _fail("invalid_json")

    try:
        data = json.loads(body.decode("utf-8"), object_pairs_hook=pairs, parse_constant=constant)
    except (ValueError, RecursionError):
        _fail("invalid_json")
    pending, count = [(data, 0)], 0
    while pending:
        value, depth = pending.pop()
        count += 1
        if depth > 20 or count > 150000:
            _fail("invalid_json")
        if isinstance(value, float) and not math.isfinite(value):
            _fail("invalid_json")
        if isinstance(value, dict):
            if count + len(pending) + len(value) > 150000:
                _fail("invalid_json")
            pending.extend((item, depth + 1) for item in value.values())
        elif isinstance(value, list):
            if count + len(pending) + len(value) > 150000:
                _fail("invalid_json")
            pending.extend((item, depth + 1) for item in value)
    return data


def read_snapshot(*, trusted_base, coordinator_root, timeout=10.0):
    """Return one filtered observation or a sanitized unavailable result; never cache."""
    result = _base()
    result.update(freshness="unavailable", completeness="unavailable", tasks=[])
    try:
        if trusted_base not in (TRUSTED_BASE, TRUSTED_BASE + "/"):
            _fail("invalid_configuration")
        _root(coordinator_root)
        if (
            not isinstance(timeout, (int, float))
            or isinstance(timeout, bool)
            or not 0 < timeout <= 10
        ):
            _fail("invalid_configuration")
        if not _REQUEST_LOCK.acquire(blocking=False):
            _fail("busy")
        try:
            body = _read_response(timeout)
            result = project_snapshot(_decode(body), coordinator_root=coordinator_root)
            result["responseSha256"] = hashlib.sha256(body).hexdigest()
            return result
        finally:
            _REQUEST_LOCK.release()
    except SnapshotError as exc:
        result["reason"] = str(exc)
    except TimeoutError:
        result["reason"] = "timeout"
    except (http.client.HTTPException, OSError):
        result["reason"] = "transport_unavailable"
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Read selected coordinator metadata once; no actions"
    )
    parser.add_argument(
        "--trusted-base", required=True, help="Explicit opt-in: http://127.0.0.1:4318"
    )
    parser.add_argument(
        "--coordinator-root", required=True, help="Trusted root for lexical comparison only"
    )
    parser.add_argument("--timeout", type=float, default=10.0)
    args = parser.parse_args(argv)
    result = read_snapshot(
        trusted_base=args.trusted_base, coordinator_root=args.coordinator_root, timeout=args.timeout
    )
    print(json.dumps(result, indent=2))
    return 0 if result["freshness"] == "observed" else 1


if __name__ == "__main__":
    raise SystemExit(main())

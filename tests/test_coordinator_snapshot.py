"""Synthetic coordinator/wire fixtures only: no live service, provider or owner state."""

import copy
import hashlib
import json

import pytest

from hermes_terminal import coordinator_snapshot as cs

ROOT = r"C:\trusted\AI Development Team"
CANARY = "RAW_PRIVATE_PAYLOAD_DO_NOT_EXPORT"


@pytest.fixture(autouse=True)
def forbid_live_connection(monkeypatch):
    def forbidden(timeout):
        pytest.fail("A fixture must supply transport; never contact the live coordinator")

    monkeypatch.setattr(cs, "_open_connection", forbidden)


@pytest.fixture
def state():
    return {
        "projects": [{"id": "lxrion", "path": r"C:\private\product", "name": CANARY}],
        "providers": [
            {
                "id": "codex",
                "status": "available",
                "model": "current-config-not-executed",
                "inferenceVerified": True,
                "detail": CANARY,
            },
            {"id": "ollama", "status": "unavailable"},
        ],
        "tasks": [
            {
                "id": "task_example",
                "projectId": "lxrion",
                "providerId": "codex",
                "status": "awaiting_approval",
                "progress": 100,
                "createdAt": "2026-10-22T10:00:00Z",
                "completedAt": "2026-10-22T10:01:00Z",
                "baseCommit": "a" * 40,
                "worktree": ROOT + r"\state\worktrees\task_example",
                "taskDir": ROOT + r"\state\tasks\task_example",
                "allowedPaths": ["src/helper.py"],
                "prompt": CANARY,
                "title": CANARY,
                "credentials": {"api_key": CANARY},
                "result": {"files": [{"path": "src/helper.py", "content": CANARY}]},
                "approvalRequired": True,
                "inferenceEvidence": {"interface": "codex exec --json", "credentials": CANARY},
                "review": {
                    "providerId": "ollama",
                    "approved": True,
                    "summary": CANARY,
                    "findings": [CANARY],
                    "createdAt": "2026-10-22T10:02:00Z",
                    "evidence": {"interface": "Ollama /api/chat streaming", "model": "qwen3:1.7b"},
                },
                "tests": {
                    "passed": True,
                    "acceptanceTrusted": True,
                    "exitCode": 0,
                    "command": CANARY,
                    "stdout": CANARY,
                    "stderr": CANARY,
                    "reason": CANARY,
                    "boundaries": CANARY,
                },
            }
        ],
        "messages": [
            {
                "id": "message_example",
                "taskId": "task_example",
                "role": "user",
                "agent": "Owner",
                "content": CANARY,
                "createdAt": "2026-10-22T10:00:00Z",
            }
        ],
        "events": [
            {
                "id": "event_example",
                "taskId": "task_example",
                "type": "applied",
                "message": CANARY,
                "createdAt": "2026-10-22T10:00:00Z",
            }
        ],
        "learningFeed": {"records": [CANARY]},
        "futureExtension": {"instructions": CANARY},
    }


def project(state):
    return cs.project_snapshot(state, coordinator_root=ROOT, observed_at="fixture-observation")


def test_projection_preserves_identity_but_never_promotes_review_to_owner_approval(state):
    original = copy.deepcopy(state)
    result = project(state)
    task = result["tasks"][0]
    assert task["taskRef"] == {
        "coordinator": "local-dev-team",
        "projectId": "lxrion",
        "taskId": "task_example",
    }
    assert task["baselineCommit"] == "a" * 40
    assert task["review"]["approvedReported"] is True
    assert task["tests"]["passedReported"] is True
    assert task["ownerDecision"] == {
        "approvalRequiredReported": True,
        "ownerApprovedAtReported": None,
        "appliedFilesReported": [],
        "receipt": "not_exposed",
    }
    assert task["executedModel"] is None  # Never use current provider config as executed identity.
    assert task["revisionBinding"] == task["fingerprints"] == "not_exposed"
    assert all(value is False for value in result["capabilities"].values())
    assert not {"approved", "passed", "done", "ready_to_apply"}.intersection(result)
    assert CANARY not in json.dumps(result)
    assert r"private" not in json.dumps(result)
    assert result["messages"][0]["taskId"] == "task_example"
    assert "role" not in result["messages"][0] and "agent" not in result["messages"][0]
    assert state == original


def test_task_model_and_failed_tests_remain_reported_independently(state):
    state["tasks"][0]["inferenceEvidence"]["model"] = "actual-task-model:1.0"
    state["tasks"][0]["tests"].update(passed=False, exitCode=7)
    result = project(state)
    assert result["tasks"][0]["executedModel"] == "actual-task-model:1.0"
    assert result["tasks"][0]["tests"]["passedReported"] is False
    assert result["tasks"][0]["tests"]["exitCodeReported"] == 7
    assert result["providers"][1]["status"] == "unavailable"
    assert result["tasks"][0]["coordinatorStatus"] == "awaiting_approval"


def test_applied_state_keeps_reported_owner_provenance_without_accepting_embedded_receipt(state):
    state["tasks"][0].update(
        status="applied",
        approvalRequired=False,
        ownerApprovedAt="2026-10-22T10:03:00Z",
        appliedFiles=["src/helper.py"],
        ownerReceipt={"decision": "approve", "credentials": CANARY},
    )
    result = project(state)
    owner = result["tasks"][0]["ownerDecision"]
    assert owner["ownerApprovedAtReported"] == "2026-10-22T10:03:00Z"
    assert owner["appliedFilesReported"] == ["src/helper.py"]
    assert owner["approvalRequiredReported"] is False
    assert owner["receipt"] == "not_exposed"
    assert CANARY not in json.dumps(result)
    assert all(value is False for value in result["capabilities"].values())


def test_missing_evidence_unknown_status_and_same_provider_are_not_positive_verdicts(state):
    task = state["tasks"][0]
    task["status"] = "future_status"
    task["review"]["providerId"] = "codex"
    task.pop("inferenceEvidence")
    task.pop("tests")
    result = project(state)["tasks"][0]
    assert result["coordinatorStatus"] == "unknown" and result["statusRecognized"] is False
    assert result["inference"] is result["tests"] is result["executedModel"] is None
    assert result["review"]["differentProvider"] is False
    assert result["ownerDecision"]["receipt"] == "not_exposed"


def test_recovery_task_does_not_inherit_parent_evidence(state):
    child = copy.deepcopy(state["tasks"][0])
    child.update(id="task_recovery", parentTaskId="task_example", status="queued", progress=0)
    for key in ("review", "tests", "inferenceEvidence", "worktree", "taskDir", "baseCommit"):
        child.pop(key)
    state["tasks"].append(child)
    result = project(state)["tasks"][1]
    assert result["parentTaskId"] == "task_example"
    assert result["review"] is result["tests"] is result["inference"] is None
    assert result["worktreeRef"]["worktreeMatchesLayout"] is None


@pytest.mark.parametrize(
    "reported", [r"C:\outside\task_example", ROOT + r"\state\worktrees\..\task_example"]
)
def test_path_mismatch_is_explicit_and_never_opened(state, reported):
    state["tasks"][0]["worktree"] = reported
    result = project(state)["tasks"][0]
    assert result["worktreeRef"]["worktreeMatchesLayout"] is False
    assert reported not in json.dumps(result)


def test_windows_path_comparison_is_lexical_and_case_insensitive(state):
    state["tasks"][0]["worktree"] = (ROOT + "/state/worktrees/task_example").upper()
    assert project(state)["tasks"][0]["worktreeRef"]["worktreeMatchesLayout"] is True


@pytest.mark.parametrize(
    "model", ["sk-proj-fixturecredentialvalue123", "AKIA1234567890ABCDEF", "<script>bad</script>"]
)
def test_credential_shaped_or_active_markup_identity_is_discarded(state, model):
    state["tasks"][0]["inferenceEvidence"]["model"] = model
    result = project(state)
    assert result["tasks"][0]["executedModel"] is None
    assert model not in json.dumps(result)


@pytest.mark.parametrize(
    "field,value",
    [
        ("progress", True),
        ("progress", 10**1000),
        ("progress", float("inf")),
        ("approvalRequired", "true"),
        ("projectId", "not_enrolled"),
        ("id", "../../task"),
        ("baseCommit", "not-a-hash"),
        ("allowedPaths", ["../owner.txt"]),
        ("allowedPaths", [".env"]),
        ("ownerApprovedAt", "tomorrow"),
        ("review", {"providerId": "ollama", "approved": "true"}),
    ],
)
def test_invalid_metadata_is_rejected_without_echoing_values(state, field, value):
    state["tasks"][0][field] = value
    with pytest.raises(cs.SnapshotError, match="^invalid_schema$"):
        project(state)


def test_duplicate_task_ids_and_unbounded_collections_are_rejected(state):
    state["tasks"].append(copy.deepcopy(state["tasks"][0]))
    with pytest.raises(cs.SnapshotError):
        project(state)
    state["tasks"] = []
    state["events"] *= 1001
    with pytest.raises(cs.SnapshotError):
        project(state)


class WireSocket:
    """Fragmented HTTP fixture; no listening socket or background server."""

    def __init__(self, wire, *, fragment=4096, on_read=None):
        self.wire, self.fragment, self.on_read = wire, fragment, on_read
        self.offset, self.sent, self.timeouts, self.closed = 0, [], [], False

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.closed = True

    def settimeout(self, timeout):
        self.timeouts.append(timeout)

    def sendall(self, request):
        self.sent.append(request)

    def recv_into(self, target):
        if self.on_read:
            self.on_read()
        count = min(len(target), self.fragment, len(self.wire) - self.offset)
        target[:count] = self.wire[self.offset : self.offset + count]
        self.offset += count
        return count


def wire_response(body, *, status=200, headers=None, chunked=False):
    headers = headers or {}
    start = f"HTTP/1.1 {status} Fixture\r\nContent-Type: {headers.pop('Content-Type', 'application/json')}\r\n"
    if chunked:
        start += "Transfer-Encoding: chunked\r\n"
        body = f"{len(body):x}\r\n".encode() + body + b"\r\n0\r\n\r\n"
    else:
        start += f"Content-Length: {len(body)}\r\n"
    start += "".join(f"{key}: {value}\r\n" for key, value in headers.items()) + "\r\n"
    return start.encode() + body


def observe(monkeypatch, wire, **socket_options):
    connection = WireSocket(wire, **socket_options)
    opens = []

    def connect(timeout):
        opens.append(timeout)
        return connection

    monkeypatch.setattr(cs, "_open_connection", connect)
    result = cs.read_snapshot(trusted_base=cs.TRUSTED_BASE, coordinator_root=ROOT)
    return result, connection, opens


@pytest.mark.parametrize("chunked", [False, True])
def test_reader_uses_exactly_one_get_filters_body_and_closes(monkeypatch, state, chunked):
    body = json.dumps(state).encode()
    result, connection, opens = observe(
        monkeypatch, wire_response(body, chunked=chunked), fragment=7
    )
    assert result["freshness"] == "observed"
    assert result["responseSha256"] == hashlib.sha256(body).hexdigest()
    assert len(opens) == len(connection.sent) == 1 and connection.closed
    assert connection.sent[0] == (
        b"GET /api/state HTTP/1.1\r\nHost: 127.0.0.1:4318\r\nAccept: application/json\r\n"
        b"Accept-Encoding: identity\r\nConnection: close\r\n\r\n"
    )
    assert CANARY not in json.dumps(result)


@pytest.mark.parametrize(
    "base",
    [
        "http://localhost:4318",
        "http://127.0.0.1:4319",
        "https://127.0.0.1:4318",
        "http://127.0.0.1:4318/api/state",
        "http://127.0.0.1:4318?secret=x",
        "http://user:pass@127.0.0.1:4318",
        "http://example.com",
    ],
)
def test_untrusted_base_is_rejected_before_any_connection(base):
    result = cs.read_snapshot(trusted_base=base, coordinator_root=ROOT)
    assert result["freshness"] == "unavailable" and result["reason"] == "invalid_configuration"
    assert base not in json.dumps(result)


@pytest.mark.parametrize("timeout", [0, 11, 10**1000, float("nan"), float("inf"), True])
def test_invalid_deadline_is_rejected_without_network(timeout):
    assert (
        cs.read_snapshot(trusted_base=cs.TRUSTED_BASE, coordinator_root=ROOT, timeout=timeout)[
            "reason"
        ]
        == "invalid_configuration"
    )


@pytest.mark.parametrize(
    "wire,reason",
    [
        (
            wire_response(b"{}", status=302, headers={"Location": "http://outside.invalid"}),
            "http_status",
        ),
        (wire_response(b"{}", status=503), "http_status"),
        (wire_response(b"{}", headers={"Content-Type": "text/html"}), "content_type"),
        (wire_response(b"{}", headers={"Content-Encoding": "gzip"}), "content_encoding"),
        (wire_response(b'{"tasks":[],"tasks":[]}'), "invalid_json"),
        (wire_response(b'{"ignored":NaN}'), "invalid_json"),
        (wire_response(b"\xff"), "invalid_json"),
        (wire_response(b"null"), "invalid_schema"),
        (
            b"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nContent-Length: 99\r\n\r\n{}",
            "invalid_http",
        ),
        (
            b"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nContent-Length: 2\r\nContent-Length: 2\r\n\r\n{}",
            "invalid_http",
        ),
    ],
)
def test_bad_http_or_json_is_unavailable_without_raw_payload(monkeypatch, wire, reason):
    result, connection, opens = observe(monkeypatch, wire, fragment=3)
    assert result["reason"] == reason and result["freshness"] == "unavailable"
    assert result["tasks"] == [] and connection.closed and len(opens) == 1


@pytest.mark.parametrize(
    "number,reason", [("1e999", "invalid_json"), ("1" + "0" * 1000, "invalid_schema")]
)
def test_numeric_overflow_on_the_wire_returns_sanitized_unavailable(
    monkeypatch, state, number, reason
):
    body = json.dumps(state).replace('"progress": 100', '"progress": ' + number).encode()
    result, connection, _ = observe(monkeypatch, wire_response(body))
    assert result["freshness"] == "unavailable" and result["reason"] == reason
    assert result["tasks"] == [] and connection.closed


def test_recursion_limit_on_the_wire_is_sanitized(monkeypatch):
    result, connection, _ = observe(monkeypatch, wire_response(b"[" * 2000 + b"0" + b"]" * 2000))
    assert result["freshness"] == "unavailable" and result["reason"] == "invalid_json"
    assert connection.closed


def test_declared_and_streamed_size_caps(monkeypatch, state):
    result, connection, _ = observe(
        monkeypatch,
        (b"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nContent-Length: 4194305\r\n\r\n"),
    )
    assert result["reason"] == "response_too_large" and connection.closed
    monkeypatch.setattr(cs, "MAX_BYTES", 256)
    result, connection, _ = observe(
        monkeypatch, wire_response(json.dumps(state).encode(), chunked=True)
    )
    assert result["reason"] == "response_too_large" and connection.closed


def test_header_budget_and_depth_node_budgets(monkeypatch):
    monkeypatch.setattr(cs, "HEADER_BYTES", 128)
    result, connection, _ = observe(
        monkeypatch, wire_response(b"{}", headers={"X-Large": "x" * 200})
    )
    assert result["reason"] == "response_too_large" and connection.closed
    with pytest.raises(cs.SnapshotError, match="invalid_json"):
        cs._decode(b"[" * 25 + b"0" + b"]" * 25)
    with pytest.raises(cs.SnapshotError, match="invalid_json"):
        cs._decode(json.dumps([0] * 150001).encode())


def test_total_deadline_stops_continuous_trickle_not_only_idle_sockets(monkeypatch, state):
    clock = [0.0]
    monkeypatch.setattr(cs, "_now", lambda: clock[0])

    def trickle():
        clock[0] += 0.4

    result, connection, _ = observe(
        monkeypatch, wire_response(json.dumps(state).encode()), fragment=1, on_read=trickle
    )
    assert result["reason"] == "timeout" and connection.closed
    assert connection.timeouts[-1] < connection.timeouts[0]
    assert clock[0] < 11  # A continuing byte stream did not reset the total deadline.


@pytest.mark.parametrize(
    "error,reason",
    [(ConnectionRefusedError(CANARY), "transport_unavailable"), (TimeoutError(CANARY), "timeout")],
)
def test_transport_errors_are_sanitized_and_no_stale_tasks_return(monkeypatch, error, reason):
    def fail(timeout):
        raise error

    monkeypatch.setattr(cs, "_open_connection", fail)
    result = cs.read_snapshot(trusted_base=cs.TRUSTED_BASE, coordinator_root=ROOT)
    assert result["reason"] == reason and result["tasks"] == []
    assert CANARY not in json.dumps(result)


def test_second_in_process_request_is_unavailable_without_starting_work():
    with cs._REQUEST_LOCK:
        result = cs.read_snapshot(trusted_base=cs.TRUSTED_BASE, coordinator_root=ROOT)
    assert result["reason"] == "busy"


def test_cli_requires_opt_in_and_returns_failure_for_unavailable(monkeypatch, capsys):
    with pytest.raises(SystemExit) as missing:
        cs.main([])
    assert missing.value.code == 2
    capsys.readouterr()
    assert cs.main(["--trusted-base", "http://outside.invalid", "--coordinator-root", ROOT]) == 1
    result = json.loads(capsys.readouterr().out)
    assert result["freshness"] == "unavailable"


def test_cli_outputs_only_filtered_json_and_creates_no_task_state(
    monkeypatch, state, capsys, tmp_path
):
    monkeypatch.chdir(tmp_path)
    connection = WireSocket(wire_response(json.dumps(state).encode()))
    monkeypatch.setattr(cs, "_open_connection", lambda timeout: connection)
    assert cs.main(["--trusted-base", cs.TRUSTED_BASE, "--coordinator-root", ROOT]) == 0
    output = capsys.readouterr().out
    assert json.loads(output)["freshness"] == "observed" and CANARY not in output
    assert list(tmp_path.iterdir()) == []

from contextlib import contextmanager
from io import BytesIO
import json
import sqlite3
import unittest
from pathlib import Path
from unittest.mock import patch

from tools import kali_embedding_worker as worker


REVISION = "1" * 40
NOW = 1_000_000
INVENTORY = {"models": [{"model": worker.MODEL, "installed": True, "declaredCapabilities": ["embedding"]}]}
VECTOR = {"model": worker.MODEL, "dimensions": 768, "embedding": [0.125] * 768}


class WorkerTests(unittest.TestCase):
    def setUp(self):
        self.db = sqlite3.connect(":memory:")
        self.addCleanup(self.db.close)
        worker.initialize_ledger(self.db)
        self.request = {
            "version": 1,
            "operation": "embedding",
            "taskId": "task-1",
            "deadlineMs": NOW + 10_000,
            "text": "synthetic fixture",
        }
        self.home = Path("unused")

    def run_job(self, replies, request=None):
        request = request or self.request
        base = worker.response_base("embedding", REVISION, taskId=request["taskId"])
        with (
            patch.object(worker, "epoch_ms", return_value=NOW),
            patch.object(worker, "portal_token", return_value="test-token"),
            patch.object(worker, "portal_request", side_effect=replies) as http,
        ):
            result = worker.run_embedding(request, base, self.home, self.db)
        return result, http.call_args_list

    def test_request_requires_one_strict_bounded_line(self):
        line = worker.json_bytes(self.request) + b"\n"
        self.assertEqual(worker.decode_request(line), self.request)
        for raw in [
            line + b"\n",
            line.rstrip(),
            b'{"version":1,"version":1,"operation":"discover"}\n',
            b'{"version":true,"operation":"discover"}\n',
            worker.json_bytes({**self.request, "text": "x" * 1201}) + b"\n",
            worker.json_bytes({**self.request, "text": "\ud800"}) + b"\n",
            worker.json_bytes({**self.request, "taskId": "path/other"}) + b"\n",
        ]:
            with self.subTest(raw=raw[:30]), self.assertRaises(worker.InvalidRequest):
                worker.decode_request(raw)

    def test_discovery_fails_closed_and_checks_exact_tag_and_capability(self):
        documents = [
            (200, INVENTORY),
            (200, {"models": [{"model": "nomic-embed-text:other", "installed": True, "declaredCapabilities": ["embedding"]}]}),
            (200, {"models": [{"model": worker.MODEL, "installed": False, "declaredCapabilities": ["embedding"]}]}),
            (401, None),
            ConnectionRefusedError(),
        ]
        with (
            patch.object(worker, "portal_token", return_value="test-token"),
            patch.object(worker, "portal_request", side_effect=documents),
        ):
            results = [worker.discover(self.home, REVISION) for _ in documents]
        self.assertEqual([result["capabilities"] for result in results], [["embedding"], [], [], [], []])

    def test_duplicate_is_cached_and_changed_deadline_conflicts(self):
        first, calls = self.run_job([(200, INVENTORY), (200, VECTOR)])
        self.assertEqual(first["status"], "ok")
        self.assertEqual(first["embedding"], VECTOR["embedding"])
        self.assertEqual([call.args[:2] for call in calls], [("GET", "/api/model-capabilities"), ("POST", "/api/embeddings")])
        self.assertEqual(json.loads(calls[1].kwargs["body"]), {"text": self.request["text"]})
        cached, calls = self.run_job([])
        self.assertEqual(cached, first)
        self.assertEqual(calls, [])
        conflict, calls = self.run_job([], {**self.request, "deadlineMs": self.request["deadlineMs"] + 1})
        self.assertEqual(conflict["status"], "conflict")
        self.assertEqual(calls, [])

    def test_definitive_rejections_and_preflight_may_retry(self):
        for status, document, expected in [
            (429, None, "busy"),
            (503, {"detail": {"code": "model_unavailable"}}, "unavailable"),
        ]:
            result, _ = self.run_job([(200, INVENTORY), (status, document)])
            self.assertEqual(result["status"], expected)
            self.assertEqual(self.db.execute("SELECT COUNT(*) FROM tasks").fetchone()[0], 0)
        result, calls = self.run_job([(503, None)])
        self.assertEqual(result["status"], "unavailable")
        self.assertEqual(len(calls), 1)
        result, _ = self.run_job([(200, INVENTORY), (200, VECTOR)])
        self.assertEqual(result["status"], "ok")

    def test_ambiguous_error_never_reexecutes(self):
        for n, failure in enumerate([TimeoutError(), (503, {"detail": "offline"}), (200, {**VECTOR, "embedding": [0]})]):
            request = {**self.request, "taskId": f"task-{n}"}
            result, _ = self.run_job([(200, INVENTORY), failure], request)
            self.assertEqual(result["status"], "execution_unknown")
            retry, calls = self.run_job([], request)
            self.assertEqual(retry["status"], "execution_unknown")
            self.assertEqual(calls, [])

    def test_entry_point_refuses_ssh_command_before_reading(self):
        with patch.dict(worker.os.environ, {"SSH_ORIGINAL_COMMAND": "whoami"}), patch.object(worker, "read_request") as read:
            self.assertEqual(worker.main(), 2)
        read.assert_not_called()

    def test_main_writes_one_json_line(self):
        class Output:
            buffer = BytesIO()

        expected = worker.response_base("discover", REVISION, capabilities=[])
        with (
            patch.dict(worker.os.environ, {"SSH_ORIGINAL_COMMAND": ""}),
            patch.object(worker.os, "umask"),
            patch.object(worker.sys, "stdout", Output()),
            patch.object(worker, "read_request", return_value={"version": 1, "operation": "discover"}),
            patch.object(worker, "checkout_revision", return_value=REVISION),
            patch.object(worker, "discover", return_value=expected),
        ):
            self.assertEqual(worker.main(), 0)
        self.assertEqual(Output.buffer.getvalue(), worker.json_bytes(expected) + b"\n")


if __name__ == "__main__":
    unittest.main()

from unittest.mock import Mock, patch

import httpx
import pytest

from hermes_terminal.ai.ollama import AI_TIMEOUT_MESSAGE, AITimeoutError, OllamaProvider
from hermes_terminal.cli import ai_assistant


def test_generation_uses_configured_300_second_httpx_timeout():
    response = Mock()
    response.raise_for_status.return_value = None
    response.json.return_value = {"message": {"content": "proposal"}}

    with patch("hermes_terminal.ai.ollama.httpx.Client") as client:
        client.return_value.__enter__.return_value.post.return_value = response
        provider = OllamaProvider("http://localhost:11434", "hermes-qwen:latest", timeout=300)
        assert provider.generate_response("propose pwd") == "proposal"

    timeout = client.call_args.kwargs["timeout"]
    assert timeout.read == 300.0
    assert timeout.connect == 10.0


def test_generation_timeout_is_not_returned_as_ai_content():
    with patch("hermes_terminal.ai.ollama.httpx.Client") as client:
        client.return_value.__enter__.return_value.post.side_effect = httpx.ReadTimeout("slow")
        provider = OllamaProvider("http://localhost:11434", "hermes-qwen:latest", timeout=300)
        with pytest.raises(AITimeoutError, match="local model took too long") as error:
            provider.generate_response("large prompt")

    assert str(error.value) == AI_TIMEOUT_MESSAGE


def test_timeout_message_does_not_show_proposal_review(capsys):
    app = Mock(current_host="gateway", ai_provider=object())
    app.generate_command_plan.return_value = {
        "error": AI_TIMEOUT_MESSAGE,
        "ai_response": "",
        "commands_generated": False,
    }
    with patch("hermes_terminal.cli.Prompt.ask", side_effect=["large prompt", "/exit"]):
        ai_assistant(app)

    output = capsys.readouterr().out
    assert AI_TIMEOUT_MESSAGE in output
    assert "Review the proposed commands" not in output

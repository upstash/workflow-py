"""Tests for redact parameter being converted to the Upstash-Redact-Fields header."""

import json
from typing import Any, Dict, Optional
from unittest.mock import MagicMock

import pytest

from upstash_workflow.workflow_requests import _trigger_first_invocation
from upstash_workflow.types import Redact


def _make_workflow_context() -> MagicMock:
    ctx = MagicMock()
    ctx.workflow_run_id = "wfr-test-id"
    ctx.url = "https://example.com"
    ctx.headers = {}
    ctx.request_payload = '{"test": true}'
    ctx.failure_url = None
    ctx.qstash_client.http.request = MagicMock()
    return ctx


def _trigger(
    redact: Optional[Redact], failure_url: Optional[str] = None
) -> Dict[str, Any]:
    """Triggers the first invocation and returns the single batch message sent."""
    ctx = _make_workflow_context()
    ctx.failure_url = failure_url

    _trigger_first_invocation(ctx, retries=3, redact=redact)

    ctx.qstash_client.http.request.assert_called_once()
    # publish_json must not be used: qstash-py (>=3) prefixes every header with
    # `Upstash-Forward-` which corrupts the workflow control headers.
    ctx.qstash_client.message.publish_json.assert_not_called()

    kwargs = ctx.qstash_client.http.request.call_args.kwargs
    assert kwargs["path"] == "/v2/batch"
    assert kwargs["method"] == "POST"

    batch_body = json.loads(kwargs["body"])
    assert len(batch_body) == 1
    message: Dict[str, Any] = batch_body[0]
    assert message["destination"] == "https://example.com"
    assert message["body"] == '{"test": true}'
    return message


@pytest.mark.parametrize(
    "redact, expected",
    [
        ({"body": True}, "body"),
        ({"header": True}, "header"),
        (
            {"header": ["Authorization", "X-API-Key"]},
            "header[Authorization],header[X-API-Key]",
        ),
        ({"body": True, "header": ["Authorization"]}, "body,header[Authorization]"),
    ],
)
def test_trigger_passes_redact_header(redact: Redact, expected: str) -> None:
    message = _trigger(redact)
    assert message["headers"]["Upstash-Redact-Fields"] == expected


@pytest.mark.parametrize("redact", [None, {}, {"header": []}])
def test_trigger_passes_no_redact(redact: Optional[Redact]) -> None:
    message = _trigger(redact)
    assert "Upstash-Redact-Fields" not in message["headers"]


def test_trigger_sends_workflow_headers_unprefixed() -> None:
    """Workflow control headers must reach QStash as-is, not as forwarded headers."""
    message = _trigger(None)
    headers = message["headers"]

    assert headers["Upstash-Workflow-Init"] == "true"
    assert headers["Upstash-Workflow-RunId"] == "wfr-test-id"
    assert headers["Upstash-Workflow-Url"] == "https://example.com"
    assert headers["Upstash-Feature-Set"] == "LazyFetch,InitialBody,WF_DetectTrigger"
    assert headers["Upstash-Forward-Upstash-Workflow-Sdk-Version"] == "1"
    assert headers["Content-Type"] == "application/json"
    assert "Upstash-Forward-Upstash-Workflow-Init" not in headers


def test_trigger_sends_failure_callback_when_failure_url_set() -> None:
    """A failing first step must also reach the failure function (as in workflow-js)."""
    message = _trigger(None, failure_url="https://example.com/failure")
    headers = message["headers"]

    assert headers["Upstash-Failure-Callback"] == "https://example.com/failure"
    assert headers["Upstash-Failure-Callback-Workflow-Runid"] == "wfr-test-id"
    assert (
        headers["Upstash-Failure-Callback-Forward-Upstash-Workflow-Is-Failure"]
        == "true"
    )


def test_trigger_sends_no_failure_callback_without_failure_url() -> None:
    message = _trigger(None)
    assert "Upstash-Failure-Callback" not in message["headers"]

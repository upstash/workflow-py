"""Tests for redact parameter being passed to qstash client."""

from unittest.mock import MagicMock
from upstash_workflow.workflow_requests import _trigger_first_invocation
from upstash_workflow.types import Redact


def _make_workflow_context():
    ctx = MagicMock()
    ctx.workflow_run_id = "wfr-test-id"
    ctx.url = "https://example.com"
    ctx.headers = {}
    ctx.request_payload = '{"test": true}'
    ctx.qstash_client.message.publish_json = MagicMock()
    return ctx


def test_trigger_passes_redact_body() -> None:
    """Test that redact with body is passed to publish_json."""
    ctx = _make_workflow_context()
    redact: Redact = {"body": True}

    _trigger_first_invocation(ctx, retries=3, redact=redact)

    ctx.qstash_client.message.publish_json.assert_called_once()
    call_kwargs = ctx.qstash_client.message.publish_json.call_args
    assert call_kwargs.kwargs["redact"] == {"body": True}


def test_trigger_passes_redact_header_all() -> None:
    """Test that redact with all headers is passed to publish_json."""
    ctx = _make_workflow_context()
    redact: Redact = {"header": True}

    _trigger_first_invocation(ctx, retries=3, redact=redact)

    call_kwargs = ctx.qstash_client.message.publish_json.call_args
    assert call_kwargs.kwargs["redact"] == {"header": True}


def test_trigger_passes_redact_specific_headers() -> None:
    """Test that redact with specific headers is passed to publish_json."""
    ctx = _make_workflow_context()
    redact: Redact = {"header": ["Authorization", "X-API-Key"]}

    _trigger_first_invocation(ctx, retries=3, redact=redact)

    call_kwargs = ctx.qstash_client.message.publish_json.call_args
    assert call_kwargs.kwargs["redact"] == {"header": ["Authorization", "X-API-Key"]}


def test_trigger_passes_redact_body_and_headers() -> None:
    """Test that redact with body and specific headers is passed to publish_json."""
    ctx = _make_workflow_context()
    redact: Redact = {"body": True, "header": ["Authorization"]}

    _trigger_first_invocation(ctx, retries=3, redact=redact)

    call_kwargs = ctx.qstash_client.message.publish_json.call_args
    assert call_kwargs.kwargs["redact"] == {"body": True, "header": ["Authorization"]}


def test_trigger_passes_no_redact() -> None:
    """Test that redact=None is passed when no redact specified."""
    ctx = _make_workflow_context()

    _trigger_first_invocation(ctx, retries=3, redact=None)

    call_kwargs = ctx.qstash_client.message.publish_json.call_args
    assert call_kwargs.kwargs["redact"] is None


def test_trigger_no_redact_headers_in_headers() -> None:
    """Test that Upstash-Redact-Fields is NOT in the headers (qstash client handles it)."""
    ctx = _make_workflow_context()
    redact: Redact = {"body": True, "header": ["Authorization"]}

    _trigger_first_invocation(ctx, retries=3, redact=redact)

    call_kwargs = ctx.qstash_client.message.publish_json.call_args
    headers = call_kwargs.kwargs["headers"]
    assert "Upstash-Redact-Fields" not in headers

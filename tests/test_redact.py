"""Tests for redacted fields functionality."""

from upstash_workflow.workflow_requests import _get_headers
from upstash_workflow.types import Redact


def test_redact_body_only() -> None:
    """Test redacting only the body."""
    redact: Redact = {"body": True}

    result = _get_headers(
        "true",
        "wfr-test-id",
        "https://example.com",
        None,
        None,
        3,
        redact=redact,
    )

    assert result.headers["Upstash-Redact-Fields"] == "body"


def test_redact_header_all() -> None:
    """Test redacting all headers."""
    redact: Redact = {"header": True}

    result = _get_headers(
        "true",
        "wfr-test-id",
        "https://example.com",
        None,
        None,
        3,
        redact=redact,
    )

    assert result.headers["Upstash-Redact-Fields"] == "header"


def test_redact_body_and_header_all() -> None:
    """Test redacting body and all headers."""
    redact: Redact = {"body": True, "header": True}

    result = _get_headers(
        "true",
        "wfr-test-id",
        "https://example.com",
        None,
        None,
        3,
        redact=redact,
    )

    assert result.headers["Upstash-Redact-Fields"] == "body,header"


def test_redact_specific_headers() -> None:
    """Test redacting specific headers."""
    redact: Redact = {"header": ["Authorization"]}

    result = _get_headers(
        "true",
        "wfr-test-id",
        "https://example.com",
        None,
        None,
        3,
        redact=redact,
    )

    assert result.headers["Upstash-Redact-Fields"] == "header[Authorization]"


def test_redact_body_and_specific_headers() -> None:
    """Test redacting body and specific headers."""
    redact: Redact = {"body": True, "header": ["Authorization", "X-API-Key"]}

    result = _get_headers(
        "true",
        "wfr-test-id",
        "https://example.com",
        None,
        None,
        3,
        redact=redact,
    )

    assert result.headers["Upstash-Redact-Fields"] == "body,header[Authorization],header[X-API-Key]"


def test_redact_with_failure_url() -> None:
    """Test redacting with failure URL sets both headers."""
    redact: Redact = {"body": True, "header": ["Authorization"]}

    result = _get_headers(
        "true",
        "wfr-test-id",
        "https://example.com",
        None,
        None,
        3,
        workflow_failure_url="https://failure.com",
        redact=redact,
    )

    assert result.headers["Upstash-Redact-Fields"] == "body,header[Authorization]"
    assert result.headers["Upstash-Failure-Callback-Redact-Fields"] == "body,header[Authorization]"


def test_no_redact() -> None:
    """Test that no redact header is added when redact is None."""
    result = _get_headers(
        "true",
        "wfr-test-id",
        "https://example.com",
        None,
        None,
        3,
        redact=None,
    )

    assert "Upstash-Redact-Fields" not in result.headers


def test_redact_empty_header_list() -> None:
    """Test that empty header list doesn't add redact parts."""
    redact: Redact = {"header": []}

    result = _get_headers(
        "true",
        "wfr-test-id",
        "https://example.com",
        None,
        None,
        3,
        redact=redact,
    )

    assert "Upstash-Redact-Fields" not in result.headers

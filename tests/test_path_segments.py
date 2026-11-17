import pytest
from qstash import QStash
from upstash_workflow import WorkflowContext
from upstash_workflow.constants import (
    WORKFLOW_ID_HEADER,
    WORKFLOW_PROTOCOL_VERSION,
    WORKFLOW_PROTOCOL_VERSION_HEADER,
)
from upstash_workflow.error import WorkflowError
from upstash_workflow.utils import _destination_path, _path_segment
from upstash_workflow.workflow_parser import _validate_request
from upstash_workflow.workflow_requests import _trigger_workflow_delete
from tests.utils import (
    mock_qstash_server,
    RequestFields,
    ResponseFields,
    MOCK_QSTASH_SERVER_URL,
)


class _Request:
    def __init__(self, run_id: str) -> None:
        self.headers = {
            WORKFLOW_PROTOCOL_VERSION_HEADER: WORKFLOW_PROTOCOL_VERSION,
            WORKFLOW_ID_HEADER: run_id,
        }


def _context(run_id: str) -> WorkflowContext[None]:
    return WorkflowContext(
        qstash_client=QStash("mock-token", base_url=MOCK_QSTASH_SERVER_URL),
        workflow_run_id=run_id,
        headers={},
        steps=[],
        url="https://some-website.com",
        initial_payload=None,
        env=None,
        retries=None,
        failure_url=None,
    )


@pytest.mark.parametrize(
    "value", ["wfr_abc-123.x~y", "user:1@example.com+a=b", "100%", "a b"]
)
def test_path_segment_is_kept(value: str) -> None:
    assert _path_segment(value) == value


@pytest.mark.parametrize(
    "value",
    ["a/b", "a\\b", "a?b", "a#b", "a\tb", "a\nb", " a", "a ", "../../messages"],
)
def test_path_segment_with_separators_is_rejected(value: str) -> None:
    with pytest.raises(WorkflowError, match="Workflow run id cannot contain"):
        _path_segment(value, "Workflow run id")


@pytest.mark.parametrize(
    "value", [".", "..", "%2e", "%2E%2e", ".%2e", ".\t.", ".. ", " ..", "..\n"]
)
def test_dot_path_segment_is_rejected(value: str) -> None:
    with pytest.raises(WorkflowError, match='cannot be "." or ".."'):
        _path_segment(value, "Workflow run id")


def test_request_with_unusable_run_id_is_rejected() -> None:
    assert _validate_request(_Request("wfr_abc")).workflow_run_id == "wfr_abc"  # type: ignore[arg-type]

    for run_id in ["../../messages", "..", "wfr_abc?cancel=true", "a#b"]:
        with pytest.raises(WorkflowError, match="Workflow run id"):
            _validate_request(_Request(run_id))  # type: ignore[arg-type]


def test_delete_sends_cancel_as_query_parameter() -> None:
    mock_qstash_server(
        execute=lambda: _trigger_workflow_delete(_context("wfr_abc"), cancel=True),
        response_fields=ResponseFields(status=200, body="deleted"),
        receives_request=RequestFields(
            method="DELETE",
            url=f"{MOCK_QSTASH_SERVER_URL}/v2/workflows/runs/wfr_abc?cancel=true",
            token="mock-token",
        ),
    )


def test_delete_with_unusable_run_id_is_not_sent() -> None:
    with pytest.raises(WorkflowError, match="Workflow run id"):
        _trigger_workflow_delete(_context("../../messages"))


@pytest.mark.parametrize(
    "url",
    [
        "https://some-website.com",
        "http://localhost:8000/api/wf?x=../y#z",
        "https://some-website.com/.well-known/wf",
    ],
)
def test_workflow_url_is_kept(url: str) -> None:
    assert _destination_path(url) == url


@pytest.mark.parametrize(
    "url",
    [
        "http://a/../../../v2/keys/rotate?/wf",
        "http://a/%2e%2e/wf",
        "http://a/./wf",
        "http://a?/wf",
        "http://a#/wf",
        "http:///wf",
        "http://a\\..\\wf",
        "ftp://a/wf",
        "",
    ],
)
def test_unusable_workflow_url_is_rejected(url: str) -> None:
    with pytest.raises(WorkflowError, match="Workflow url"):
        _destination_path(url)

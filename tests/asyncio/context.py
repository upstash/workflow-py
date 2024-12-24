import pytest
from unittest.mock import Mock, AsyncMock
from upstash_workflow.context.context import WorkflowContext
from upstash_workflow.error import QStashWorkflowAbort

WORKFLOW_ENDPOINT = "https://workflow.example.com"
MOCK_QSTASH_SERVER_URL = "https://qstash.upstash.io"


@pytest.fixture
def mock_qstash_client():
    client = Mock()
    client.message = Mock()
    client.message.batch_json = AsyncMock(return_value={"messageId": "msgId"})
    return client


@pytest.fixture
def workflow_context(mock_qstash_client):
    return WorkflowContext(
        qstash_client=mock_qstash_client,
        workflow_run_id="wfr-id",
        headers={},
        steps=[],
        url=WORKFLOW_ENDPOINT,
        initial_payload="my-payload",
        raw_initial_payload=None,
        env=None,
        retries=None,
    )


@pytest.mark.asyncio
async def test_context_call_headers(workflow_context, mock_qstash_client):
    """Test that context.call sends correct headers"""
    url = "https://some-website.com"
    body = "request-body"
    retries = 10

    with pytest.raises(QStashWorkflowAbort) as exc_info:
        await workflow_context.call(
            step_name="my-step",
            url=url,
            method="PATCH",
            body=body,
            headers={"my-header": "my-value"},
            retries=retries,
        )

    actual_batch_request = mock_qstash_client.message.batch_json.call_args[0][0]
    assert len(actual_batch_request) == 1
    actual_request = actual_batch_request[0]

    assert actual_request["url"] == url
    assert actual_request["method"] == "PATCH"
    assert actual_request["body"] == body

    expected_headers = {
        "Upstash-Callback": WORKFLOW_ENDPOINT,
        "Upstash-Callback-Feature-Set": "LazyFetch,InitialBody",
        "Upstash-Callback-Forward-Upstash-Workflow-Callback": "true",
        "Upstash-Callback-Forward-Upstash-Workflow-Concurrent": "1",
        "Upstash-Callback-Forward-Upstash-Workflow-ContentType": "application/json",
        "Upstash-Callback-Forward-Upstash-Workflow-StepId": "1",
        "Upstash-Callback-Forward-Upstash-Workflow-StepName": "my-step",
        "Upstash-Callback-Forward-Upstash-Workflow-StepType": "Call",
        "Upstash-Callback-Retries": "3",
        "Upstash-Callback-Workflow-CallType": "fromCallback",
        "Upstash-Callback-Workflow-Init": "false",
        "Upstash-Callback-Workflow-RunId": "wfr-id",
        "Upstash-Callback-Workflow-Url": WORKFLOW_ENDPOINT,
        "Upstash-Failure-Callback-Retries": "3",
        "Upstash-Feature-Set": "WF_NoDelete,InitialBody",
        "Upstash-Forward-my-header": "my-value",
        "Upstash-Retries": str(retries),
        "Upstash-Workflow-CallType": "toCallback",
        "Upstash-Workflow-Init": "false",
        "Upstash-Workflow-RunId": "wfr-id",
        "Upstash-Workflow-Url": WORKFLOW_ENDPOINT,
    }
    print(actual_request["headers"])

    for header_key, header_value in expected_headers.items():
        assert (
            actual_request["headers"][header_key] == header_value
        ), f"Header mismatch for {header_key}"

    assert "Aborting workflow after executing step 'my-step'." in str(exc_info.value)

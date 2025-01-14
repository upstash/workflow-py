import pytest
from qstash import AsyncQStash
from upstash_workflow import AsyncWorkflowContext
from upstash_workflow.error import WorkflowAbort
from tests.utils import (
    RequestFields,
    ResponseFields,
    MOCK_QSTASH_SERVER_URL,
    WORKFLOW_ENDPOINT,
)
from tests.asyncio.utils import mock_qstash_server


@pytest.fixture
def qstash_client() -> AsyncQStash:
    return AsyncQStash("mock-token", base_url=MOCK_QSTASH_SERVER_URL)


@pytest.mark.asyncio
async def test_workflow_headers(qstash_client: AsyncQStash) -> None:
    url = "https://some-website.com"
    body = "request-body"
    retries = 10

    context = AsyncWorkflowContext(
        qstash_client=qstash_client,
        workflow_run_id="wfr-id",
        headers={},
        steps=[],
        url=WORKFLOW_ENDPOINT,
        initial_payload="my-payload",
        env=None,
        retries=None,
    )

    async def execute() -> None:
        with pytest.raises(WorkflowAbort) as excinfo:
            await context.call(
                "my-step",
                url=url,
                method="PATCH",
                body=body,
                headers={"my-header": "my-value"},
                retries=retries,
            )

        assert "Aborting workflow after executing step 'my-step'." in str(excinfo.value)

    await mock_qstash_server(
        execute=execute,
        response_fields=ResponseFields(status=200, body="msgId"),
        receives_request=RequestFields(
            method="POST",
            url=f"{MOCK_QSTASH_SERVER_URL}/v2/batch",
            token="mock-token",
            body=[
                {
                    "body": '"request-body"',
                    "destination": url,
                    "queue": None,
                    "headers": {
                        "Content-Type": "application/json",
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
                        "Upstash-Method": "PATCH",
                        "Upstash-Retries": str(retries),
                        "Upstash-Workflow-CallType": "toCallback",
                        "Upstash-Workflow-Init": "false",
                        "Upstash-Workflow-RunId": "wfr-id",
                        "Upstash-Workflow-Url": WORKFLOW_ENDPOINT,
                    },
                }
            ],
        ),
    )

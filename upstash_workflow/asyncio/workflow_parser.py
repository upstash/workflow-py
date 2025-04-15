from typing import Optional, cast
from upstash_workflow.workflow_types import _AsyncRequest
import json
from typing import Callable, Dict, Any, Literal, Awaitable, TypeVar
from upstash_workflow.utils import _decode_base64
from upstash_workflow.constants import (
    WORKFLOW_FAILURE_HEADER,
)
from upstash_workflow.error import WorkflowError
from upstash_workflow.workflow_requests import _recreate_user_headers
from upstash_workflow.asyncio.serve.authorization import _DisabledWorkflowContext
from qstash import AsyncQStash
from upstash_workflow import AsyncWorkflowContext


async def _get_payload(request: _AsyncRequest) -> Optional[str]:
    """
    Gets the request body. If that fails, returns None

    :param request: request received in the workflow api
    :return: request body
    """
    try:
        return (await request.body()).decode()
    except Exception:
        return None


TInitialPayload = TypeVar("TInitialPayload")
TRequest = TypeVar("TRequest", bound=_AsyncRequest)


async def _handle_failure(
    request: TRequest,
    request_payload: str,
    qstash_client: AsyncQStash,
    initial_payload_parser: Callable[[str], Any],
    route_function: Callable[[AsyncWorkflowContext[TInitialPayload]], Awaitable[None]],
    failure_function: Optional[
        Callable[
            [AsyncWorkflowContext[TInitialPayload], int, str, Dict[str, str]],
            Awaitable[Any],
        ]
    ],
    env: Dict[str, Any],
    retries: int,
) -> Literal["not-failure-callback", "is-failure-callback"]:
    if request.headers and request.headers.get(WORKFLOW_FAILURE_HEADER) != "true":
        return "not-failure-callback"

    if not failure_function:
        raise WorkflowError(
            "Workflow endpoint is called to handle a failure, "
            "but a failure_function is not provided in serve options. "
            "Either provide a failure_url or a failure_function."
        )

    try:
        payload = json.loads(request_payload)
        status = payload["status"]
        header = payload["header"]
        body = payload["body"]
        url = payload["url"]
        source_body = payload["sourceBody"]
        workflow_run_id = payload["workflowRunId"]

        decoded_body = _decode_base64(body) if body else "{}"
        error_payload = json.loads(decoded_body)

        # Create context
        workflow_context = AsyncWorkflowContext(
            qstash_client=qstash_client,
            workflow_run_id=workflow_run_id,
            initial_payload=initial_payload_parser(_decode_base64(source_body))
            if source_body
            else None,
            headers=_recreate_user_headers(request.headers or {}),
            steps=[],
            url=url,
            failure_url=url,
            env=env,
            retries=retries,
        )

        # Attempt running route_function until the first step
        auth_check = await _DisabledWorkflowContext[Any].try_authentication(
            route_function,
            cast(AsyncWorkflowContext[TInitialPayload], workflow_context),
        )

        if auth_check == "run-ended":
            raise WorkflowError("Not authorized to run the failure function.")

        await failure_function(
            cast(AsyncWorkflowContext[TInitialPayload], workflow_context),
            status,
            error_payload.get("message"),
            header,
        )
    except Exception as error:
        raise error

    return "is-failure-callback"

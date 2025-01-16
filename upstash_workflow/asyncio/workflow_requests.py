from __future__ import annotations
import json
import base64
import logging
from typing import (
    TYPE_CHECKING,
    Callable,
    Awaitable,
    Literal,
    Optional,
    cast,
    TypeVar,
)
from qstash import AsyncQStash
from upstash_workflow.error import WorkflowError, WorkflowAbort
from upstash_workflow.constants import (
    WORKFLOW_ID_HEADER,
)
from upstash_workflow.types import StepTypes
from upstash_workflow.workflow_types import _AsyncRequest
from upstash_workflow.workflow_requests import _get_headers, _recreate_user_headers

if TYPE_CHECKING:
    from upstash_workflow import AsyncWorkflowContext

_logger = logging.getLogger(__name__)

TInitialPayload = TypeVar("TInitialPayload")


async def _trigger_first_invocation(
    workflow_context: AsyncWorkflowContext[TInitialPayload],
    retries: int,
) -> None:
    headers = _get_headers(
        "true",
        workflow_context.workflow_run_id,
        workflow_context.url,
        workflow_context.headers,
        None,
        retries,
    ).headers

    await workflow_context.qstash_client.message.publish_json(
        url=workflow_context.url,
        body=workflow_context.request_payload,
        headers=headers,
    )


async def _trigger_route_function(
    on_step: Callable[[], Awaitable[None]], on_cleanup: Callable[[], Awaitable[None]]
) -> None:
    try:
        # When onStep completes successfully, it throws WorkflowAbort
        # indicating that the step has been successfully executed.
        # This ensures that onCleanup is only called when no exception is thrown.
        await on_step()
        await on_cleanup()
    except Exception as error:
        if isinstance(error, WorkflowAbort):
            return
        raise error


async def _trigger_workflow_delete(
    workflow_context: AsyncWorkflowContext[TInitialPayload],
    cancel: Optional[bool] = False,
) -> None:
    await workflow_context.qstash_client.http.request(
        path=f"/v2/workflows/runs/{workflow_context.workflow_run_id}?cancel={str(cancel).lower()}",
        method="DELETE",
        parse_response=False,
    )


async def _handle_third_party_call_result(
    request: _AsyncRequest,
    request_payload: str,
    client: AsyncQStash,
    workflow_url: str,
    retries: int,
) -> Literal["call-will-retry", "is-call-return", "continue-workflow"]:
    """
    Check if the request is from a third party call result. If so,
    call QStash to add the result to the ongoing workflow.

    Otherwise, do nothing.

    ### How third party calls work

    In third party calls, we publish a message to the third party API.
    the result is then returned back to the workflow endpoint.

    Whenever the workflow endpoint receives a request, we first check
    if the incoming request is a third party call result coming from QStash.
    If so, we send back the result to QStash as a result step.

    :param request: Incoming request
    :param request_payload: Request payload
    :param client: QStash client
    :param workflow_url: Workflow URL
    :param retries: Number of retries
    :return: "call-will-retry", "is-call-return" or "continue-workflow"
    """
    try:
        if request.headers and request.headers.get("Upstash-Workflow-Callback"):
            if request_payload:
                callback_payload = request_payload
            else:
                raise NotImplementedError

            callback_message = json.loads(callback_payload)

            if (
                not (200 <= callback_message["status"] < 300)
                and callback_message.get("maxRetries")
                and callback_message.get("retried") != callback_message["maxRetries"]
            ):
                _logger.warning(
                    f'Workflow Warning: "context.call" failed with status {callback_message["status"]} '
                    f'and will retry (retried {callback_message.get("retried", 0)} out of '
                    f'{callback_message["maxRetries"]} times). '
                    f'Error Message:\n{base64.b64decode(callback_message.get("body", "")).decode()}'
                )

                return "call-will-retry"

            headers = request.headers
            workflow_run_id = headers.get(WORKFLOW_ID_HEADER)
            step_id_str = headers.get("Upstash-Workflow-StepId")
            step_name = headers.get("Upstash-Workflow-StepName")
            step_type = headers.get("Upstash-Workflow-StepType")
            concurrent_str = headers.get("Upstash-Workflow-Concurrent")
            content_type = headers.get("Upstash-Workflow-ContentType")

            if not all(
                [
                    workflow_run_id,
                    step_id_str,
                    step_name,
                    step_type in StepTypes,
                    concurrent_str,
                    content_type,
                ]
            ):
                info = json.dumps(
                    {
                        "workflow_run_id": workflow_run_id,
                        "step_id_str": step_id_str,
                        "step_name": step_name,
                        "step_type": step_type,
                        "concurrent_str": concurrent_str,
                        "content_type": content_type,
                    }
                )
                raise ValueError(
                    f"Missing info in callback message source header: {info}"
                )

            workflow_run_id = cast(str, workflow_run_id)
            step_id_str = cast(str, step_id_str)
            step_name = cast(str, step_name)
            step_type = cast(str, step_type)
            concurrent_str = cast(str, concurrent_str)
            content_type = cast(str, content_type)

            user_headers = _recreate_user_headers(headers)
            request_headers = _get_headers(
                "false",
                workflow_run_id,
                workflow_url,
                user_headers,
                None,
                retries,
            ).headers

            call_response = {
                "status": callback_message["status"],
                "body": base64.b64decode(callback_message.get("body", "")).decode(),
                "header": callback_message["header"],
            }

            call_result_step = {
                "stepId": int(step_id_str),
                "stepName": step_name,
                "stepType": step_type,
                "out": json.dumps(call_response),
                "concurrent": int(concurrent_str),
            }

            await client.message.publish_json(
                headers=request_headers,
                body=call_result_step,
                url=workflow_url,
            )

            return "is-call-return"

        return "continue-workflow"

    except Exception as error:
        is_call_return = request.headers and request.headers.get(
            "Upstash-Workflow-Callback"
        )
        raise WorkflowError(
            f"Error when handling call return (isCallReturn={is_call_return}): {str(error)}"
        )

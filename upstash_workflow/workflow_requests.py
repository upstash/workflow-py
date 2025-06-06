from __future__ import annotations
import json
import base64
import logging
from typing import (
    TYPE_CHECKING,
    Callable,
    Literal,
    Optional,
    Union,
    cast,
    TypeVar,
    Dict,
)
from qstash import QStash, Receiver
from upstash_workflow.error import WorkflowError, WorkflowAbort
from upstash_workflow.constants import (
    WORKFLOW_INIT_HEADER,
    WORKFLOW_ID_HEADER,
    WORKFLOW_URL_HEADER,
    WORKFLOW_PROTOCOL_VERSION,
    WORKFLOW_PROTOCOL_VERSION_HEADER,
    WORKFLOW_FEATURE_HEADER,
    WORKFLOW_FAILURE_HEADER,
    DEFAULT_CONTENT_TYPE,
    DEFAULT_RETRIES,
)
from upstash_workflow.types import StepTypes, DefaultStep, _HeadersResponse
from upstash_workflow.workflow_types import _SyncRequest

if TYPE_CHECKING:
    from upstash_workflow import WorkflowContext

_logger = logging.getLogger(__name__)

TInitialPayload = TypeVar("TInitialPayload")


def _trigger_first_invocation(
    workflow_context: WorkflowContext[TInitialPayload],
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

    workflow_context.qstash_client.message.publish_json(
        url=workflow_context.url,
        body=workflow_context.request_payload,
        headers=headers,
    )


def _trigger_route_function(
    on_step: Callable[[], None], on_cleanup: Callable[[], None]
) -> None:
    try:
        # When onStep completes successfully, it throws WorkflowAbort
        # indicating that the step has been successfully executed.
        # This ensures that onCleanup is only called when no exception is thrown.
        on_step()
        on_cleanup()
    except Exception as error:
        if isinstance(error, WorkflowAbort):
            return
        raise error


def _trigger_workflow_delete(
    workflow_context: WorkflowContext[TInitialPayload],
    cancel: Optional[bool] = False,
) -> None:
    workflow_context.qstash_client.http.request(
        path=f"/v2/workflows/runs/{workflow_context.workflow_run_id}?cancel={str(cancel).lower()}",
        method="DELETE",
        parse_response=False,
    )


def _recreate_user_headers(headers: Dict[str, str]) -> Dict[str, str]:
    """
    Removes headers starting with `Upstash-Workflow-` from the headers

    :param headers: incoming headers
    :return: headers with `Upstash-Workflow-` headers removed
    """
    filtered_headers = {}

    for header, value in headers.items():
        header_lower = header.lower()
        if not any(
            [
                header_lower.startswith("upstash-workflow-"),
                # https://vercel.com/docs/edge-network/headers/request-headers#x-vercel-id
                header_lower.startswith("x-vercel-"),
                header_lower.startswith("x-forwarded-"),
                # https://blog.cloudflare.com/preventing-request-loops-using-cdn-loop/
                header_lower == "cf-connecting-ip",
                header_lower == "cdn-loop",
                header_lower == "cf-ew-via",
                header_lower == "cf-ray",
                # For Render https://render.com
                header_lower == "render-proxy-ttl",
            ]
        ):
            filtered_headers[header] = value

    return filtered_headers


def _handle_third_party_call_result(
    request: _SyncRequest,
    request_payload: str,
    client: QStash,
    workflow_url: str,
    workflow_failure_url: Optional[str],
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
                workflow_failure_url=workflow_failure_url,
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

            client.message.publish_json(
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


def _should_set_retries(retries: Optional[int]):
    return retries is not None and retries != DEFAULT_RETRIES


def _get_headers(
    init_header_value: Literal["true", "false"],
    workflow_run_id: str,
    workflow_url: str,
    user_headers: Optional[Dict[str, str]] = None,
    step: Optional[DefaultStep] = None,
    retries: Optional[int] = None,
    call_retries: Optional[int] = None,
    call_timeout: Optional[Union[int, str]] = None,
    workflow_failure_url: Optional[str] = None,
) -> _HeadersResponse:
    """
    Gets headers for calling QStash

    :param init_header_value: Whether the invocation should create a new workflow
    :param workflow_run_id: id of the workflow
    :param workflow_url: url of the workflow endpoint
    :param step: step to get headers for. If the step is a third party call step, more
          headers are added.
    :return: headers to submit
    """
    base_headers = {
        WORKFLOW_INIT_HEADER: init_header_value,
        WORKFLOW_ID_HEADER: workflow_run_id,
        WORKFLOW_URL_HEADER: workflow_url,
        WORKFLOW_FEATURE_HEADER: "LazyFetch,InitialBody",
    }

    if not (step and step.call_url):
        base_headers[f"Upstash-Forward-{WORKFLOW_PROTOCOL_VERSION_HEADER}"] = (
            WORKFLOW_PROTOCOL_VERSION
        )

    if call_timeout:
        base_headers["Upstash-Timeout"] = str(call_timeout)

    if workflow_failure_url:
        base_headers[f"Upstash-Failure-Callback-Forward-{WORKFLOW_FAILURE_HEADER}"] = (
            "true"
        )
        base_headers[
            "Upstash-Failure-Callback-Forward-Upstash-Workflow-Failure-Callback"
        ] = "true"
        base_headers["Upstash-Failure-Callback-Workflow-Runid"] = workflow_run_id
        base_headers["Upstash-Failure-Callback-Workflow-Init"] = "false"
        base_headers["Upstash-Failure-Callback-Workflow-Url"] = workflow_url
        base_headers["Upstash-Failure-Callback-Workflow-Calltype"] = "failureCall"
        if step and step.call_url:
            base_headers[
                f"Upstash-Callback-Failure-Callback-Forward-{WORKFLOW_FAILURE_HEADER}"
            ] = "true"
            base_headers[
                "Upstash-Callback-Failure-Callback-Forward-Upstash-Workflow-Failure-Callback"
            ] = "true"
            base_headers["Upstash-Callback-Failure-Callback-Workflow-Runid"] = (
                workflow_run_id
            )
            base_headers["Upstash-Callback-Failure-Callback-Workflow-Init"] = "false"
            base_headers["Upstash-Callback-Failure-Callback-Workflow-Url"] = (
                workflow_url
            )
            base_headers["Upstash-Callback-Failure-Callback-Workflow-Calltype"] = (
                "failureCall"
            )

        if _should_set_retries(retries):
            base_headers["Upstash-Failure-Callback-Retries"] = str(retries)
            if step and step.call_url:
                base_headers["Upstash-Callback-Failure-Callback-Retries"] = str(retries)

        if not step or not step.call_url:
            base_headers["Upstash-Failure-Callback"] = workflow_failure_url
            if step and step.call_url:
                base_headers["Upstash-Callback-Failure-Callback"] = workflow_failure_url

    if step and step.call_url:
        base_headers["Upstash-Retries"] = str(
            call_retries if call_retries is not None else 0
        )
        base_headers[WORKFLOW_FEATURE_HEADER] = "WF_NoDelete,InitialBody"

        if retries is not None:
            base_headers["Upstash-Callback-Retries"] = str(retries)
            base_headers["Upstash-Failure-Callback-Retries"] = str(retries)
    elif _should_set_retries(retries):
        base_headers["Upstash-Retries"] = str(retries)
        base_headers["Upstash-Failure-Callback-Retries"] = str(retries)

    if user_headers:
        for header in user_headers.keys():
            header_value = user_headers.get(header)
            if header_value is not None:
                if step and step.call_headers is not None:
                    base_headers[f"Upstash-Callback-Forward-{header}"] = header_value
                else:
                    base_headers[f"Upstash-Forward-{header}"] = header_value
                base_headers[f"Upstash-Failure-Callback-Forward-{header}"] = (
                    header_value
                )

    content_type = user_headers.get("Content-Type") if user_headers else None
    content_type = DEFAULT_CONTENT_TYPE if content_type is None else content_type

    if step and step.call_headers is not None:
        forwarded_headers = {
            f"Upstash-Forward-{header}": value
            for header, value in step.call_headers.items()
        }

        return _HeadersResponse(
            headers={
                **base_headers,
                **forwarded_headers,
                "Upstash-Callback": workflow_url,
                "Upstash-Callback-Workflow-RunId": workflow_run_id,
                "Upstash-Callback-Workflow-CallType": "fromCallback",
                "Upstash-Callback-Workflow-Init": "false",
                "Upstash-Callback-Workflow-Url": workflow_url,
                "Upstash-Callback-Feature-Set": "LazyFetch,InitialBody",
                "Upstash-Callback-Forward-Upstash-Workflow-Callback": "true",
                "Upstash-Callback-Forward-Upstash-Workflow-StepId": str(step.step_id),
                "Upstash-Callback-Forward-Upstash-Workflow-StepName": step.step_name,
                "Upstash-Callback-Forward-Upstash-Workflow-StepType": step.step_type,
                "Upstash-Callback-Forward-Upstash-Workflow-Concurrent": str(
                    step.concurrent
                ),
                "Upstash-Callback-Forward-Upstash-Workflow-ContentType": content_type,
                "Upstash-Workflow-CallType": "toCallback",
            }
        )

    return _HeadersResponse(headers=base_headers)


def _verify_request(
    body: str, signature: Union[str, None], verifier: Optional[Receiver]
) -> None:
    if not verifier:
        return

    try:
        if not signature:
            raise Exception("`Upstash-Signature` header is not passed.")
        try:
            verifier.verify(
                body=body,
                signature=signature,
            )
        except Exception:
            raise Exception("Signature in `Upstash-Signature` header is not valid")
    except Exception as error:
        raise WorkflowError(
            f"Failed to verify that the Workflow request comes from QStash: {error}\n\n"
            + "If signature is missing, trigger the workflow endpoint by publishing your request to QStash instead of calling it directly.\n\n"
            + "If you want to disable QStash Verification, you should clear env variables QSTASH_CURRENT_SIGNING_KEY and QSTASH_NEXT_SIGNING_KEY"
        )

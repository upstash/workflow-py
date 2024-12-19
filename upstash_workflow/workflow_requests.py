import httpx
import json
import base64
import logging
from upstash_workflow.error import QStashWorkflowError, QStashWorkflowAbort
from upstash_workflow.constants import (
    WORKFLOW_INIT_HEADER,
    WORKFLOW_ID_HEADER,
    WORKFLOW_URL_HEADER,
    WORKFLOW_PROTOCOL_VERSION,
    WORKFLOW_PROTOCOL_VERSION_HEADER,
    DEFAULT_CONTENT_TYPE,
    WORKFLOW_FEATURE_HEADER,
)
from upstash_workflow.types import StepTypes

_logger = logging.getLogger(__name__)


async def trigger_first_invocation(
    workflow_context,
    retries,
    env,
):
    headers = get_headers(
        "true",
        workflow_context.workflow_run_id,
        workflow_context.url,
        workflow_context.headers,
        None,
        retries,
    )["headers"]

    await workflow_context.qstash_client.message.publish_json(
        url=workflow_context.url,
        body=workflow_context.request_payload,
        headers=headers,
    )


async def trigger_route_function(on_step, on_cleanup):
    try:
        # When onStep completes successfully, it throws QStashWorkflowAbort
        # indicating that the step has been successfully executed.
        # This ensures that onCleanup is only called when no exception is thrown.
        await on_step()
        await on_cleanup()
    except Exception as error:
        if isinstance(error, QStashWorkflowAbort):
            return
        raise error


async def trigger_workflow_delete(
    workflow_context,
    cancel=False,
):
    async with httpx.AsyncClient() as client:
        await client.delete(
            f"https://qstash.upstash.io/v2/workflows/runs/{workflow_context.workflow_run_id}?cancel={str(cancel).lower()}",
            headers={
                "Authorization": f"Bearer {workflow_context.env.get('QSTASH_TOKEN', '')}"
            },
        )


def recreate_user_headers(headers: dict) -> dict:
    filtered_headers = {}

    for header, value in headers.items():
        header_lower = header.lower()
        if not any(
            [
                header_lower.startswith("upstash-workflow-"),
                header_lower.startswith("x-vercel-"),
                header_lower.startswith("x-forwarded-"),
                header_lower == "cf-connecting-ip",
            ]
        ):
            filtered_headers[header] = value

    return filtered_headers


async def handle_third_party_call_result(
    request, request_payload, client, workflow_url, retries
):
    try:
        if request.headers.get("Upstash-Workflow-Callback"):
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
                raise ValueError(
                    f"Missing info in callback message source header: {json.dumps({
                        'workflow_run_id': workflow_run_id,
                        'step_id_str': step_id_str,
                        'step_name': step_name,
                        'step_type': step_type,
                        'concurrent_str': concurrent_str,
                        'content_type': content_type
                    })}"
                )

            user_headers = recreate_user_headers(headers)
            request_headers = get_headers(
                "false",
                workflow_run_id,
                workflow_url,
                user_headers,
                None,
                retries,
            )["headers"]

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

            result = await client.message.publish_json(
                headers=request_headers,
                body=call_result_step,
                url=workflow_url,
            )

            return "is-call-return"

        return "continue-workflow"

    except Exception as error:
        is_call_return = request.headers.get("Upstash-Workflow-Callback")
        raise QStashWorkflowError(
            f"Error when handling call return (isCallReturn={is_call_return}): {str(error)}"
        )


def get_headers(
    init_header_value,
    workflow_run_id,
    workflow_url,
    user_headers,
    step,
    retries,
    call_retries=None,
    call_timeout=None,
):
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

    if step and step.call_url:
        base_headers["Upstash-Retries"] = str(
            call_retries if call_retries is not None else 0
        )
        base_headers[WORKFLOW_FEATURE_HEADER] = "WF_NoDelete,InitialBody"

        if retries is not None:
            base_headers["Upstash-Callback-Retries"] = str(retries)
            base_headers["Upstash-Failure-Callback-Retries"] = str(retries)
    elif retries is not None:
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
    content_type = content_type or DEFAULT_CONTENT_TYPE

    if step and step.call_headers is not None:
        forwarded_headers = {
            f"Upstash-Forward-{header}": value
            for header, value in step.call_headers.items()
        }

        return {
            "headers": {
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
        }

    return {"headers": base_headers}


async def verify_request(body, signature, verifier):
    if not verifier:
        return

    try:
        if not signature:
            raise Exception("`Upstash-Signature` header is not passed.")
        is_valid = await verifier.verify(
            {
                "body": body,
                "signature": signature,
            }
        )
        if not is_valid:
            raise Exception("Signature in `Upstash-Signature` header is not valid")
    except Exception as error:
        raise QStashWorkflowError(
            f"Failed to verify that the Workflow request comes from QStash: {error}\n\n"
            + "If signature is missing, trigger the workflow endpoint by publishing your request to QStash instead of calling it directly.\n\n"
            + "If you want to disable QStash Verification, you should clear env variables QSTASH_CURRENT_SIGNING_KEY and QSTASH_NEXT_SIGNING_KEY"
        )

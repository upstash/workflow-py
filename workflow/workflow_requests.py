from workflow.error import QStashWorkflowError, QStashWorkflowAbort
from workflow.constants import (
    WORKFLOW_INIT_HEADER,
    WORKFLOW_ID_HEADER,
    WORKFLOW_URL_HEADER,
    WORKFLOW_PROTOCOL_VERSION,
    WORKFLOW_PROTOCOL_VERSION_HEADER,
    DEFAULT_CONTENT_TYPE,
)


async def trigger_first_invocation(
    workflow_context,
    retries,
):
    headers = get_headers(
        "true",
        workflow_context.workflow_run_id,
        workflow_context.url,
        workflow_context.headers,
        None,
        retries,
    )["headers"]

    await workflow_context.qstash_client.publish_json(
        {
            "headers": headers,
            "method": "POST",
            "body": workflow_context.request_payload,
            "url": workflow_context.url,
        }
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
    cancel,
):
    await workflow_context.qstash_client.http.request(
        path=[
            "v2",
            "workflows",
            "runs",
            f"{workflow_context.workflow_run_id}?cancel={str(cancel).lower()}",
        ],
        method="DELETE",
        parse_response_as_json=False,
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


def get_headers(
    init_header_value,
    workflow_run_id,
    workflow_url,
    user_headers,
    step,
    retries,
):
    base_headers = {
        WORKFLOW_INIT_HEADER: init_header_value,
        WORKFLOW_ID_HEADER: workflow_run_id,
        WORKFLOW_URL_HEADER: workflow_url,
    }

    base_headers[f"Upstash-Forward-{WORKFLOW_PROTOCOL_VERSION_HEADER}"] = (
        WORKFLOW_PROTOCOL_VERSION
    )

    if retries is not None:
        base_headers["Upstash-Retries"] = str(retries)

    if user_headers:
        for header in user_headers.keys():
            header_value = user_headers.get(header)
            if header_value is not None:
                if step and step.call_headers:
                    base_headers[f"Upstash-Callback-Forward-{header}"] = header_value
                else:
                    base_headers[f"Upstash-Forward-{header}"] = header_value

    content_type = user_headers.get("Content-Type") if user_headers else None
    content_type = content_type or DEFAULT_CONTENT_TYPE

    if step and step.call_headers:
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
                "Upstash-Callback-Forward-Upstash-Workflow-Callback": "true",
                "Upstash-Callback-Forward-Upstash-Workflow-StepId": str(step.step_id),
                "Upstash-Callback-Forward-Upstash-Workflow-StepName": step.step_name,
                "Upstash-Callback-Forward-Upstash-Workflow-StepType": step.step_type,
                "Upstash-Callback-Forward-Upstash-Workflow-Concurrent": str(
                    step.concurrent
                ).lower(),
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

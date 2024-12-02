import requests
from upstash_workflow.error import QStashWorkflowError, QStashWorkflowAbort
from upstash_workflow.constants import (
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

    requests.post(
        f"https://qstash.upstash.io/v2/publish/{workflow_context.url}",
        headers={
            "Authorization": f"Bearer {env.get("QSTASH_TOKEN", "")}",
            **headers,
        },
        json=workflow_context.request_payload,
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
    requests.delete(
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
        for header, value in user_headers.items():
            base_headers[f"Upstash-Forward-{header}"] = value

    content_type = user_headers.get("Content-Type") if user_headers else None
    content_type = content_type or DEFAULT_CONTENT_TYPE

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

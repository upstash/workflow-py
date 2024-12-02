import json
from upstash_workflow.workflow_types import Response
from upstash_workflow.workflow_parser import get_payload, validate_request, parse_request
from upstash_workflow.workflow_requests import (
    verify_request,
    recreate_user_headers,
    trigger_first_invocation,
    trigger_route_function,
    trigger_workflow_delete,
)
from upstash_workflow.serve.options import process_options, determine_urls
from upstash_workflow.error import format_workflow_error
from upstash_workflow.context.context import WorkflowContext


def serve(route_function, options):
    processed_options = process_options(options)
    qstash_client = processed_options.get("qstash_client")
    on_step_finish = processed_options.get("on_step_finish")
    initial_payload_parser = processed_options.get("initial_payload_parser")
    receiver = processed_options.get("receiver")
    base_url = processed_options.get("base_url")
    env = processed_options.get("env")
    retries = processed_options.get("retries")
    url = processed_options.get("url")

    async def _handler(request):
        workflow_url = (await determine_urls(request, url, base_url)).get(
            "workflow_url"
        )

        request_payload = await get_payload(request) or ""
        await verify_request(
            request_payload, request.headers.get("upstash-signature"), receiver
        )

        validate_request_response = validate_request(request)
        is_first_invocation = validate_request_response.get("is_first_invocation")
        workflow_run_id = validate_request_response.get("workflow_run_id")

        parse_request_response = await parse_request(
            request_payload, is_first_invocation
        )

        raw_initial_payload = parse_request_response.get("raw_initial_payload")
        steps = parse_request_response.get("steps")

        workflow_context = WorkflowContext(
            qstash_client=qstash_client,
            workflow_run_id=workflow_run_id,
            initial_payload=initial_payload_parser(raw_initial_payload),
            raw_initial_payload=raw_initial_payload,
            headers=recreate_user_headers(request.headers),
            steps=steps,
            url=workflow_url,
            env=env,
            retries=retries,
        )

        if is_first_invocation:
            await trigger_first_invocation(workflow_context, retries, env)
        else:

            async def on_step():
                return await route_function(workflow_context)

            async def on_cleanup():
                await trigger_workflow_delete(workflow_context)

            await trigger_route_function(on_step=on_step, on_cleanup=on_cleanup)

        return on_step_finish(workflow_context.workflow_run_id, "success")

    async def _safe_handler(request):
        try:
            return await _handler(request)
        except Exception as error:
            print(error)
            return Response(json.dumps(format_workflow_error(error)), status=500)

    return {"handler": _safe_handler}

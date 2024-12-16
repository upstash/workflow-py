import os
import json
import logging
from typing import Optional, Callable, Awaitable, Dict, Union, cast
from qstash import AsyncQStash, Receiver
from upstash_workflow.workflow_types import Response, Request
from upstash_workflow.workflow_parser import (
    get_payload,
    validate_request,
    parse_request,
)
from upstash_workflow.workflow_requests import (
    verify_request,
    recreate_user_headers,
    trigger_first_invocation,
    trigger_route_function,
    trigger_workflow_delete,
    handle_third_party_call_result,
)
from upstash_workflow.serve.options import process_options, determine_urls
from upstash_workflow.error import format_workflow_error
from upstash_workflow.context.context import WorkflowContext
from upstash_workflow.types import FinishCondition

_logger = logging.getLogger(__name__)


def serve[TInitialPayload, TRequest: Request, TResponse](
    route_function: Callable[[WorkflowContext[TInitialPayload]], Awaitable[None]],
    *,
    qstash_client: Optional[AsyncQStash] = None,
    on_step_finish: Optional[Callable[[str, FinishCondition], TResponse]] = None,
    initial_payload_parser: Optional[Callable[[str], TInitialPayload]] = None,
    receiver: Optional[Receiver] = None,
    base_url: Optional[str] = None,
    env: Optional[Union[Dict[str, Optional[str]], os._Environ[str]]] = None,
    retries: Optional[int] = None,
    url: Optional[str] = None,
) -> Dict[str, Callable[[TRequest], Awaitable[TResponse]]]:
    processed_options = process_options(
        qstash_client=qstash_client,
        on_step_finish=on_step_finish,
        initial_payload_parser=initial_payload_parser,
        receiver=receiver,
        base_url=base_url,
        env=env,
        retries=retries,
        url=url,
    )
    qstash_client = processed_options.qstash_client
    on_step_finish = processed_options.on_step_finish
    initial_payload_parser = processed_options.initial_payload_parser
    receiver = processed_options.receiver
    base_url = processed_options.base_url
    env = processed_options.env
    retries = processed_options.retries
    url = processed_options.url

    async def _handler(request: TRequest):
        workflow_url = (
            await determine_urls(cast(Request, request), url, base_url)
        ).get("workflow_url")

        request_payload = await get_payload(request) or ""
        await verify_request(
            request_payload,
            None if not request.headers else request.headers.get("upstash-signature"),
            receiver,
        )

        validate_request_response = validate_request(request)
        is_first_invocation = validate_request_response.get("is_first_invocation")
        workflow_run_id = validate_request_response.get("workflow_run_id")

        parse_request_response = await parse_request(
            request_payload, is_first_invocation
        )

        raw_initial_payload = parse_request_response.get("raw_initial_payload")
        steps = parse_request_response.get("steps")

        workflow_context = WorkflowContext[TInitialPayload](
            qstash_client=qstash_client,
            workflow_run_id=workflow_run_id,
            initial_payload=initial_payload_parser(raw_initial_payload),
            raw_initial_payload=raw_initial_payload,
            headers=recreate_user_headers(
                {} if not request.headers else request.headers
            ),
            steps=steps,
            url=workflow_url,
            env=env,
            retries=retries,
        )

        call_return_check = await handle_third_party_call_result(
            request,
            raw_initial_payload,
            qstash_client,
            workflow_url,
            retries,
        )

        if call_return_check == "continue-workflow":
            if is_first_invocation:
                await trigger_first_invocation(workflow_context, retries, env)
            else:

                async def on_step():
                    return await route_function(workflow_context)

                async def on_cleanup():
                    await trigger_workflow_delete(workflow_context)

                await trigger_route_function(on_step=on_step, on_cleanup=on_cleanup)

            return on_step_finish(workflow_context.workflow_run_id, "success")

        return on_step_finish("no-workflow-id", "fromCallback")

    async def _safe_handler(request: TRequest):
        try:
            return await _handler(request)
        except Exception as error:
            _logger.exception(error)
            return Response(json.dumps(format_workflow_error(error)), status=500)

    return {"handler": _safe_handler}

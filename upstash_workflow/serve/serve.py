import json
import logging
from typing import Optional, Callable, Awaitable, Dict, cast, TypeVar, Any
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
from upstash_workflow.serve.authorization import DisabledWorkflowContext

_logger = logging.getLogger(__name__)

TInitialPayload = TypeVar("TInitialPayload")
TRequest = TypeVar("TRequest", bound=Request)
TResponse = TypeVar("TResponse")


def serve(
    route_function: Callable[[WorkflowContext[TInitialPayload]], Awaitable[None]],
    *,
    qstash_client: Optional[AsyncQStash] = None,
    on_step_finish: Optional[Callable[[str, FinishCondition], TResponse]] = None,
    initial_payload_parser: Optional[Callable[[str], TInitialPayload]] = None,
    receiver: Optional[Receiver] = None,
    base_url: Optional[str] = None,
    env: Optional[Dict[str, Optional[str]]] = None,
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

    async def _handler(request: TRequest) -> TResponse:
        workflow_url = await determine_urls(cast(Request, request), url, base_url)

        request_payload = await get_payload(request) or ""
        await verify_request(
            request_payload,
            None if not request.headers else request.headers.get("upstash-signature"),
            receiver,
        )

        validate_request_response = validate_request(request)
        is_first_invocation = validate_request_response.is_first_invocation
        workflow_run_id = validate_request_response.workflow_run_id

        parse_request_response = await parse_request(
            request_payload, is_first_invocation
        )

        raw_initial_payload = parse_request_response.raw_initial_payload
        steps = parse_request_response.steps

        workflow_context = WorkflowContext(
            qstash_client=qstash_client,
            workflow_run_id=workflow_run_id,
            initial_payload=initial_payload_parser(raw_initial_payload),
            headers=recreate_user_headers(
                {} if not request.headers else request.headers
            ),
            steps=steps,
            url=workflow_url,
            env=env,
            retries=retries,
        )

        auth_check = await DisabledWorkflowContext[Any].try_authentication(
            route_function, workflow_context
        )

        if auth_check == "run-ended":
            return on_step_finish(
                (
                    "no-workflow-id"
                    if is_first_invocation
                    else workflow_context.workflow_run_id
                ),
                "auth-fail",
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
                await trigger_first_invocation(workflow_context, retries)
            else:

                async def on_step() -> None:
                    await route_function(workflow_context)

                async def on_cleanup() -> None:
                    await trigger_workflow_delete(workflow_context)

                await trigger_route_function(on_step=on_step, on_cleanup=on_cleanup)

            return on_step_finish(workflow_context.workflow_run_id, "success")

        return on_step_finish("no-workflow-id", "fromCallback")

    async def _safe_handler(request: TRequest) -> TResponse:
        try:
            return await _handler(request)
        except Exception as error:
            _logger.exception(error)
            return cast(
                TResponse,
                Response(json.dumps(format_workflow_error(error)), status=500),
            )

    return {"handler": _safe_handler}

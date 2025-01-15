import json
import logging
from typing import Optional, Callable, Awaitable, Dict, cast, TypeVar, Any
from qstash import AsyncQStash, Receiver
from upstash_workflow.workflow_types import _Response, _AsyncRequest
from upstash_workflow.asyncio.workflow_parser import (
    _get_payload,
)
from upstash_workflow.workflow_parser import _validate_request, _parse_request
from upstash_workflow.asyncio.workflow_requests import (
    _trigger_first_invocation,
    _trigger_route_function,
    _trigger_workflow_delete,
    _handle_third_party_call_result,
)
from upstash_workflow.workflow_requests import _verify_request, _recreate_user_headers
from upstash_workflow.serve.options import _determine_urls
from upstash_workflow.asyncio.serve.options import _process_options
from upstash_workflow.error import _format_workflow_error
from upstash_workflow import AsyncWorkflowContext
from upstash_workflow.types import _FinishCondition
from upstash_workflow.asyncio.serve.authorization import _DisabledWorkflowContext

_logger = logging.getLogger(__name__)

TInitialPayload = TypeVar("TInitialPayload")
TRequest = TypeVar("TRequest", bound=_AsyncRequest)
TResponse = TypeVar("TResponse")


def _serve_base(
    route_function: Callable[[AsyncWorkflowContext[TInitialPayload]], Awaitable[None]],
    *,
    qstash_client: Optional[AsyncQStash] = None,
    on_step_finish: Optional[Callable[[str, _FinishCondition], TResponse]] = None,
    initial_payload_parser: Optional[Callable[[str], TInitialPayload]] = None,
    receiver: Optional[Receiver] = None,
    base_url: Optional[str] = None,
    env: Optional[Dict[str, Optional[str]]] = None,
    retries: Optional[int] = None,
    url: Optional[str] = None,
) -> Dict[str, Callable[[TRequest], Awaitable[TResponse]]]:
    processed_options = _process_options(
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
        workflow_url = _determine_urls(cast(_AsyncRequest, request), url, base_url)

        request_payload = await _get_payload(request) or ""
        _verify_request(
            request_payload,
            None if not request.headers else request.headers.get("upstash-signature"),
            receiver,
        )

        validate_request_response = _validate_request(request)
        is_first_invocation = validate_request_response.is_first_invocation
        workflow_run_id = validate_request_response.workflow_run_id

        parse_request_response = _parse_request(request_payload, is_first_invocation)

        raw_initial_payload = parse_request_response.raw_initial_payload
        steps = parse_request_response.steps

        workflow_context = AsyncWorkflowContext(
            qstash_client=qstash_client,
            workflow_run_id=workflow_run_id,
            initial_payload=initial_payload_parser(raw_initial_payload),
            headers=_recreate_user_headers(
                {} if not request.headers else request.headers
            ),
            steps=steps,
            url=workflow_url,
            env=env,
            retries=retries,
        )

        auth_check = await _DisabledWorkflowContext[Any].try_authentication(
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

        call_return_check = await _handle_third_party_call_result(
            request,
            raw_initial_payload,
            qstash_client,
            workflow_url,
            retries,
        )

        if call_return_check == "continue-workflow":
            if is_first_invocation:
                await _trigger_first_invocation(workflow_context, retries)
            else:

                async def on_step() -> None:
                    await route_function(workflow_context)

                async def on_cleanup() -> None:
                    await _trigger_workflow_delete(workflow_context)

                await _trigger_route_function(on_step=on_step, on_cleanup=on_cleanup)

            return on_step_finish(workflow_context.workflow_run_id, "success")

        return on_step_finish("no-workflow-id", "fromCallback")

    async def _safe_handler(request: TRequest) -> TResponse:
        try:
            return await _handler(request)
        except Exception as error:
            _logger.exception(error)
            return cast(
                TResponse,
                _Response(json.dumps(_format_workflow_error(error)), status=500),
            )

    return {"handler": _safe_handler}


def serve(
    route_function: Callable[[AsyncWorkflowContext[TInitialPayload]], Awaitable[None]],
    *,
    qstash_client: Optional[AsyncQStash] = None,
    initial_payload_parser: Optional[Callable[[str], TInitialPayload]] = None,
    receiver: Optional[Receiver] = None,
    base_url: Optional[str] = None,
    env: Optional[Dict[str, Optional[str]]] = None,
    retries: Optional[int] = None,
    url: Optional[str] = None,
) -> Dict[str, Callable[[TRequest], Awaitable[TResponse]]]:
    """
    Creates a method that handles incoming requests and runs the provided
    route function as a workflow.

    :param route_function: A function that uses AsyncWorkflowContext as a parameter and runs a workflow.
    :param qstash_client: AsyncQStash client
    :param on_step_finish: Function called to return a response after each step execution
    :param initial_payload_parser: Function to parse the initial payload passed by the user
    :param receiver: Receiver to verify *all* requests by checking if they come from QStash. By default, a receiver is created from the env variables QSTASH_CURRENT_SIGNING_KEY and QSTASH_NEXT_SIGNING_KEY if they are set.
    :param base_url: Base Url of the workflow endpoint. Can be used to set if there is a local tunnel or a proxy between QStash and the workflow endpoint. Will be set to the env variable UPSTASH_WORKFLOW_URL if not passed. If the env variable is not set, the url will be infered as usual from the `request.url` or the `url` parameter in `serve` options.
    :param env: Optionally, one can pass an env object mapping environment variables to their keys. Useful in cases like cloudflare with hono.
    :param retries: Number of retries to use in workflow requests, 3 by default
    :param url: Url of the endpoint where the workflow is set up. If not set, url will be inferred from the request.
    :return: An method that consumes incoming requests and runs the workflow.
    """
    return _serve_base(
        route_function,
        qstash_client=qstash_client,
        initial_payload_parser=initial_payload_parser,
        receiver=receiver,
        base_url=base_url,
        env=env,
        retries=retries,
        url=url,
    )

import json
import logging
from typing import Optional, Callable, Dict, cast, TypeVar, Any
from qstash import QStash, Receiver
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
    route_function: Callable[[WorkflowContext[TInitialPayload]], None],
    *,
    qstash_client: Optional[QStash] = None,
    on_step_finish: Optional[Callable[[str, FinishCondition], TResponse]] = None,
    initial_payload_parser: Optional[Callable[[str], TInitialPayload]] = None,
    receiver: Optional[Receiver] = None,
    base_url: Optional[str] = None,
    env: Optional[Dict[str, Optional[str]]] = None,
    retries: Optional[int] = None,
    url: Optional[str] = None,
) -> Dict[str, Callable[[TRequest], TResponse]]:
    """
    Creates a method that handles incoming requests and runs the provided
    route function as a workflow.

    :param route_function: A function that uses WorkflowContext as a parameter and runs a workflow.
    :param qstash_client: QStash client
    :param on_step_finish: Function called to return a response after each step execution
    :param initial_payload_parser: Function to parse the initial payload passed by the user
    :param receiver: Receiver to verify *all* requests by checking if they come from QStash. By default, a receiver is created from the env variables QSTASH_CURRENT_SIGNING_KEY and QSTASH_NEXT_SIGNING_KEY if they are set.
    :param base_url: Base Url of the workflow endpoint. Can be used to set if there is a local tunnel or a proxy between QStash and the workflow endpoint. Will be set to the env variable UPSTASH_WORKFLOW_URL if not passed. If the env variable is not set, the url will be infered as usual from the `request.url` or the `url` parameter in `serve` options.
    :param env: Optionally, one can pass an env object mapping environment variables to their keys. Useful in cases like cloudflare with hono.
    :param retries: Number of retries to use in workflow requests, 3 by default
    :param url: Url of the endpoint where the workflow is set up. If not set, url will be inferred from the request.
    :return: An method that consumes incoming requests and runs the workflow.
    """
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

    def _handler(request: TRequest) -> TResponse:
        """
        Handles the incoming request, triggering the appropriate workflow steps.
        Calls `trigger_first_invocation()` if it's the first invocation.
        Otherwise, starts calling `trigger_route_function()` to execute steps in the workflow.
        Finally, calls `trigger_workflow_delete()` to remove the workflow from QStash.

        :param request: The incoming request to handle.
        :return: A response.
        """
        workflow_url = determine_urls(cast(Request, request), url, base_url)

        request_payload = get_payload(request) or ""
        verify_request(
            request_payload,
            None if not request.headers else request.headers.get("upstash-signature"),
            receiver,
        )

        validate_request_response = validate_request(request)
        is_first_invocation = validate_request_response.is_first_invocation
        workflow_run_id = validate_request_response.workflow_run_id

        parse_request_response = parse_request(request_payload, is_first_invocation)

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

        auth_check = DisabledWorkflowContext[Any].try_authentication(
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

        call_return_check = handle_third_party_call_result(
            request,
            raw_initial_payload,
            qstash_client,
            workflow_url,
            retries,
        )

        if call_return_check == "continue-workflow":
            if is_first_invocation:
                trigger_first_invocation(workflow_context, retries)
            else:

                def on_step() -> None:
                    route_function(workflow_context)

                def on_cleanup() -> None:
                    trigger_workflow_delete(workflow_context)

                trigger_route_function(on_step=on_step, on_cleanup=on_cleanup)

            return on_step_finish(workflow_context.workflow_run_id, "success")

        return on_step_finish("no-workflow-id", "fromCallback")

    def _safe_handler(request: TRequest) -> TResponse:
        try:
            return _handler(request)
        except Exception as error:
            _logger.exception(error)
            return cast(
                TResponse,
                Response(json.dumps(format_workflow_error(error)), status=500),
            )

    return {"handler": _safe_handler}

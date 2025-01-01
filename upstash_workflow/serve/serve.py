import os
import json
import logging
from typing import Optional, Callable, Dict, Union, cast, TypeVar, Tuple, List
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
    trigger_workflow_delete_sync,
    handle_third_party_call_result,
)
from upstash_workflow.serve.options import process_options, determine_urls
from upstash_workflow.error import format_workflow_error
from upstash_workflow.context.context import WorkflowContext
from upstash_workflow.types import FinishCondition, Step

_logger = logging.getLogger(__name__)

TInitialPayload = TypeVar("TInitialPayload")
TRequest = TypeVar("TRequest", bound=Request)
TResponse = TypeVar("TResponse")


def serve(
    route_function: Callable[[WorkflowContext], None],
    *,
    qstash_client: Optional[QStash] = None,
    on_step_finish: Optional[Callable[[str, FinishCondition], TResponse]] = None,
    initial_payload_parser: Optional[Callable[[str], TInitialPayload]] = None,
    receiver: Optional[Receiver] = None,
    base_url: Optional[str] = None,
    env: Optional[Union[Dict[str, Optional[str]], os._Environ]] = None,
    retries: Optional[int] = None,
    url: Optional[str] = None,
) -> Dict[str, Callable[[TRequest], TResponse]]:
    qstash_client = qstash_client or QStash(
        cast(str, (env if env is not None else os.environ).get("QSTASH_TOKEN", "")),
    )

    (
        on_step_finish,
        initial_payload_parser,
        receiver,
        base_url,
        env,
        retries,
        url,
    ) = process_options(
        on_step_finish,
        initial_payload_parser,
        receiver,
        base_url,
        env,
        retries,
        url,
    )

    def _handler(request: TRequest):
        request_payload = get_payload(request) or ""

        (
            workflow_url,
            is_first_invocation,
            raw_initial_payload,
            workflow_run_id,
            steps,
        ) = process_request(
            request,
            receiver,
            base_url,
            url,
            cast(str, request_payload),
        )

        workflow_context = WorkflowContext(
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

        generator_handle_third_party_call_result = handle_third_party_call_result(
            request,
            raw_initial_payload,
            workflow_url,
            retries,
        )

        call_return_check = next(generator_handle_third_party_call_result)

        if isinstance(call_return_check, dict):
            qstash_client.message.publish_json(
                headers=call_return_check["headers"],
                body=call_return_check["body"],
                url=call_return_check["url"],
            )
            call_return_check = next(generator_handle_third_party_call_result)

        if call_return_check == "continue-workflow":
            if is_first_invocation:
                trigger_first_invocation(workflow_context, retries)
            else:

                def on_step():
                    return route_function(workflow_context)

                def on_cleanup():
                    trigger_workflow_delete_sync(workflow_context)

                trigger_route_function(on_step=on_step, on_cleanup=on_cleanup)

            return on_step_finish(workflow_context.workflow_run_id, "success")

        return on_step_finish("no-workflow-id", "fromCallback")

    def _safe_handler(request: TRequest):
        try:
            return _handler(request)
        except Exception as error:
            _logger.exception(error)
            return Response(json.dumps(format_workflow_error(error)), status=500)

    return {"handler": _safe_handler}


def process_request(
    request: Request,
    receiver: Optional[Receiver],
    base_url: Optional[str],
    url: Optional[str],
    request_payload: str,
) -> Tuple[str, bool, str, str, List[Step]]:
    workflow_url = determine_urls(cast(Request, request), url, base_url)
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

    return (
        workflow_url,
        is_first_invocation,
        raw_initial_payload,
        workflow_run_id,
        steps,
    )

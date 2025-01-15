import json
from typing import Optional, List, Tuple, Union
from upstash_workflow.utils import _nanoid, _decode_base64
from upstash_workflow.constants import (
    WORKFLOW_PROTOCOL_VERSION,
    WORKFLOW_PROTOCOL_VERSION_HEADER,
    WORKFLOW_ID_HEADER,
    NO_CONCURRENCY,
)
from upstash_workflow.error import WorkflowError
from upstash_workflow.types import (
    Step,
    DefaultStep,
    _ValidateRequestResponse,
    _ParseRequestResponse,
)
from upstash_workflow.workflow_types import _SyncRequest, _AsyncRequest


def _get_payload(request: _SyncRequest) -> Optional[str]:
    """
    Gets the request body. If that fails, returns None

    :param request: request received in the workflow api
    :return: request body
    """
    try:
        return request.body
    except Exception:
        return None


def _parse_payload(raw_payload: str) -> Tuple[str, List[DefaultStep]]:
    """
    Parses a request coming from QStash. First parses the string as JSON, which will result
    in a list of objects with messageId & body fields. Body will be base64 encoded.

    Body of the first item will be the body of the first request received in the workflow API.
    Rest are steps in Upstash Workflow Step format.

    When returning steps, we add the initial payload as initial step. This is to make it simpler
    in the rest of the code.

    :param raw_payload: body of the request as a string as explained above
    :return: initial payload and list of steps
    """
    raw_steps = [step for step in json.loads(raw_payload)]

    encoded_initial_payload, *encoded_steps = raw_steps

    raw_initial_payload = _decode_base64(encoded_initial_payload["body"])

    initial_step = {
        "stepId": 0,
        "stepName": "init",
        "stepType": "Initial",
        "out": raw_initial_payload,
        "concurrent": NO_CONCURRENCY,
    }

    steps_to_decode = [step for step in encoded_steps if step["callType"] == "step"]

    other_steps = []
    for raw_step in steps_to_decode:
        step = json.loads(_decode_base64(raw_step["body"]))

        try:
            step["out"] = json.loads(step["out"])
        except json.JSONDecodeError:
            pass

        if step.get("waitEventId", None):
            new_out = {
                "event_data": _decode_base64(step["out"]) if step["out"] else None,
                "timeout": step.wait_timeout or False,
            }
            step["out"] = new_out

        other_steps.append(step)

    all_steps = [initial_step] + other_steps

    parsed_steps: List[DefaultStep] = []
    for step in all_steps:
        parsed_steps.append(
            Step(
                step_id=step["stepId"],
                step_name=step["stepName"],
                step_type=step["stepType"],
                out=step["out"],
                concurrent=step["concurrent"],
            )
        )

    return raw_initial_payload, parsed_steps


def _validate_request(
    request: Union[_SyncRequest, _AsyncRequest],
) -> _ValidateRequestResponse:
    """
    Validates the incoming request checking the workflow protocol
    version and whether it is the first invocation.

    Raises `WorkflowError` if:
    - it's not the first invocation and expected protocol version doesn't match
      the request.
    - it's not the first invocation but there is no workflow id in the headers.

    :param request: Request received
    :return: whether it's the first invocation and the workflow id
    """
    # Get version header
    version_header = (
        request.headers.get(WORKFLOW_PROTOCOL_VERSION_HEADER)
        if request.headers
        else None
    )
    is_first_invocation = not version_header

    # Verify workflow protocol version if not first invocation
    if not is_first_invocation and version_header != WORKFLOW_PROTOCOL_VERSION:
        raise WorkflowError(
            f"Incompatible workflow sdk protocol version. "
            f"Expected {WORKFLOW_PROTOCOL_VERSION}, "
            f"got {version_header} from the request."
        )

    # Generate or get workflow ID
    if is_first_invocation:
        workflow_run_id = f"wfr_{_nanoid()}"
    else:
        workflow_run_id = (
            request.headers.get(WORKFLOW_ID_HEADER, "") if request.headers else ""
        )

    if not workflow_run_id:
        raise WorkflowError("Couldn't get workflow id from header")

    return _ValidateRequestResponse(
        is_first_invocation=is_first_invocation, workflow_run_id=workflow_run_id
    )


def _parse_request(
    request_payload: Optional[str], is_first_invocation: bool
) -> _ParseRequestResponse:
    """
    Checks request headers and body
    - Reads the request body as raw text
    - Returns the steps. If it's the first invocation, steps are empty.
      Otherwise, steps are generated from the request body.

    :param request: Request received
    :return: raw initial payload and the steps
    """
    if is_first_invocation:
        return _ParseRequestResponse(
            raw_initial_payload=(request_payload or ""),
            steps=[],
        )
    else:
        if not request_payload:
            raise WorkflowError("Only first call can have an empty body")

        raw_initial_payload, steps = _parse_payload(request_payload)

        return _ParseRequestResponse(
            raw_initial_payload=raw_initial_payload, steps=steps
        )

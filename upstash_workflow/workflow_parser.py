import json
from typing import Optional, List, Tuple
from upstash_workflow.utils import nanoid, decode_base64
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
    ValidateRequestResponse,
    ParseRequestResponse,
)
from upstash_workflow.workflow_types import Request


def get_payload(request: Request) -> Optional[str]:
    try:
        return json.dumps(request.json())
    except Exception:
        return None


def parse_payload(raw_payload: str) -> Tuple[str, List[DefaultStep]]:
    raw_steps = [step for step in json.loads(raw_payload)]

    encoded_initial_payload, *encoded_steps = raw_steps

    raw_initial_payload = decode_base64(encoded_initial_payload["body"])

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
        step = json.loads(decode_base64(raw_step["body"]))

        try:
            step["out"] = json.loads(step["out"])
        except json.JSONDecodeError:
            pass

        if step.get("waitEventId", None):
            new_out = {
                "event_data": decode_base64(step["out"]) if step["out"] else None,
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


def validate_request(request: Request) -> ValidateRequestResponse:
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
        workflow_run_id = f"wfr_{nanoid()}"
    else:
        workflow_run_id = (
            request.headers.get(WORKFLOW_ID_HEADER, "") if request.headers else ""
        )

    if not workflow_run_id:
        raise WorkflowError("Couldn't get workflow id from header")

    return ValidateRequestResponse(
        is_first_invocation=is_first_invocation, workflow_run_id=workflow_run_id
    )


def parse_request(
    request_payload: Optional[str], is_first_invocation: bool
) -> ParseRequestResponse:
    if is_first_invocation:
        return ParseRequestResponse(
            raw_initial_payload=(request_payload or ""),
            steps=[],
        )
    else:
        if not request_payload:
            raise WorkflowError("Only first call can have an empty body")

        raw_initial_payload, steps = parse_payload(request_payload)

        return ParseRequestResponse(
            raw_initial_payload=raw_initial_payload, steps=steps
        )

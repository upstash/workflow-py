import json
from workflow.utils import nanoid, decode_base64
from workflow.constants import (
    WORKFLOW_PROTOCOL_VERSION,
    WORKFLOW_PROTOCOL_VERSION_HEADER,
    WORKFLOW_ID_HEADER,
    NO_CONCURRENCY,
)
from workflow.error import QStashWorkflowError


async def get_payload(request):
    try:
        return await request.text()
    except Exception:
        return None


async def parse_payload(raw_payload):
    raw_steps = [step for step in json.loads(raw_payload)]

    encoded_initial_payload, *encoded_steps = raw_steps

    raw_initial_payload = await decode_base64(encoded_initial_payload.body)

    initial_step = {
        "step_id": 0,
        "step_name": "init",
        "step_type": "Initial",
        "out": raw_initial_payload,
        "concurrent": NO_CONCURRENCY,
    }

    steps_to_decode = [step for step in encoded_steps if step.call_type == "step"]

    other_steps = []
    for raw_step in steps_to_decode:
        step = json.loads(await decode_base64(raw_step.body))

        try:
            step.out = json.loads(step.out)
        except json.JSONDecodeError:
            pass

        if step.wait_event_id:
            new_out = {
                "event_data": await decode_base64(step.out) if step.out else None,
                "timeout": step.wait_timeout or False,
            }
            step.out = new_out

        other_steps.append(step)

    all_steps = [initial_step] + other_steps

    return {"raw_initial_payload": raw_initial_payload, "steps": all_steps}


def validate_request(request):
    # Get version header
    version_header = request.headers.get(WORKFLOW_PROTOCOL_VERSION_HEADER)
    is_first_invocation = not version_header

    # Verify workflow protocol version if not first invocation
    if not is_first_invocation and version_header != WORKFLOW_PROTOCOL_VERSION:
        raise QStashWorkflowError(
            f"Incompatible workflow sdk protocol version. "
            f"Expected {WORKFLOW_PROTOCOL_VERSION}, "
            f"got {version_header} from the request."
        )

    # Generate or get workflow ID
    if is_first_invocation:
        workflow_run_id = f"wfr_{nanoid()}"
    else:
        workflow_run_id = request.headers.get(WORKFLOW_ID_HEADER) or ""

    if not workflow_run_id:
        raise QStashWorkflowError("Couldn't get workflow id from header")

    return {is_first_invocation: is_first_invocation, workflow_run_id: workflow_run_id}


async def parse_request(request_payload, is_first_invocation):
    if is_first_invocation:
        return {
            raw_initial_payload: request_payload or "",
            steps: [],
        }
    else:
        if not request_payload:
            raise QStashWorkflowError("Only first call can have an empty body")

        parsed_data = await parse_payload(request_payload)
        raw_initial_payload = parsed_data["raw_initial_payload"]
        steps = parsed_data["steps"]

        return {
            raw_initial_payload: raw_initial_payload,
            steps: steps,
        }

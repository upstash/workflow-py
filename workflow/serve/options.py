import os
import json
import re
from qstash import QStash, Receiver
from workflow.workflow_types import Response
from workflow.constants import DEFAULT_RETRIES


def process_options(options):
    environment = options.env if options and options.env is not None else os.environ

    receiver_environment_variables_set = bool(
        environment.get("QSTASH_CURRENT_SIGNING_KEY")
        and environment.get("QSTASH_NEXT_SIGNING_KEY")
    )

    def _on_step_finish(workflow_run_id, finish_condition):
        return Response(body={"workflowRunId": workflow_run_id}, status=200)

    def _initial_payload_parser(initial_request):
        # If there is no payload, return None
        if not initial_request:
            return None

        # Try to parse the payload
        try:
            return json.loads(initial_request)
        except json.JSONDecodeError:
            # If parsing fails, return the raw string
            return initial_request
        except Exception as error:
            # If not a JSON parsing error, re-raise
            raise error

    # Create default options
    default_options = {
        "qstash_client": QStash(
            environment.get("QSTASH_TOKEN", ""),
        ),
        "on_step_finish": _on_step_finish,
        "initial_payload_parser": _initial_payload_parser,
        "receiver": (
            Receiver(
                current_signing_key=environment.get("QSTASH_CURRENT_SIGNING_KEY", ""),
                next_signing_key=environment.get("QSTASH_NEXT_SIGNING_KEY", ""),
            )
            if receiver_environment_variables_set
            else None
        ),
        "base_url": environment.get("UPSTASH_WORKFLOW_URL"),
        "env": environment,
        "retries": DEFAULT_RETRIES,
        # **options,
    }

    # If options were provided, update defaults with provided values
    if options:
        for key, value in options.__dict__.items():
            setattr(default_options, key, value)

    return default_options


async def determine_urls(
    request,
    url,
    base_url,
):
    initial_workflow_url = str(url if url is not None else request.url)

    if base_url:

        def replace_base(match: re.Match) -> str:
            matched_base_url, path = match.groups()
            return base_url + (path or "")

        workflow_url = re.sub(
            r"^(https?://[^/]+)(/.*)?$", replace_base, initial_workflow_url
        )
    else:
        workflow_url = initial_workflow_url

    return {
        "workflow_url": workflow_url,
    }

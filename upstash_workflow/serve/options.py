import os
import json
import re
from typing import Callable, Dict, Optional, cast, Union
from qstash import AsyncQStash, Receiver
from upstash_workflow.workflow_types import Response
from upstash_workflow.constants import DEFAULT_RETRIES
from upstash_workflow.types import (
    FinishCondition,
    WorkflowServeOptions,
)


def process_options[
    TResponse, TInitialPayload
](
    *,
    qstash_client: Optional[AsyncQStash] = None,
    on_step_finish: Optional[Callable[[str, FinishCondition], TResponse]] = None,
    initial_payload_parser: Optional[Callable[[str], TInitialPayload]] = None,
    receiver: Optional[Receiver] = None,
    base_url: Optional[str] = None,
    env: Optional[Union[Dict[str, Optional[str]], os._Environ[str]]] = None,
    retries: Optional[int] = DEFAULT_RETRIES,
    url: Optional[str] = None,
) -> WorkflowServeOptions[TResponse, TInitialPayload]:
    environment = env if env is not None else os.environ

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

    return WorkflowServeOptions[TResponse, TInitialPayload](
        qstash_client=qstash_client
        or AsyncQStash(
            cast(str, environment.get("QSTASH_TOKEN", "")),
        ),
        on_step_finish=on_step_finish or _on_step_finish,
        initial_payload_parser=initial_payload_parser or _initial_payload_parser,
        receiver=receiver
        or (
            Receiver(
                current_signing_key=cast(
                    str, environment.get("QSTASH_CURRENT_SIGNING_KEY", "")
                ),
                next_signing_key=cast(
                    str, environment.get("QSTASH_NEXT_SIGNING_KEY", "")
                ),
            )
            if receiver_environment_variables_set
            else None
        ),
        base_url=base_url or environment.get("UPSTASH_WORKFLOW_URL"),
        env=environment,
        retries=retries or DEFAULT_RETRIES,
        url=url,
    )


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

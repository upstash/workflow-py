import os
import json
import re
import logging
from typing import (
    Callable,
    Dict,
    Optional,
    cast,
    TypeVar,
    Match,
    Union,
    Any,
    Generic,
    Tuple,
)
from qstash import QStash, Receiver
from upstash_workflow.workflow_types import _Response, _SyncRequest, _AsyncRequest
from upstash_workflow.constants import DEFAULT_RETRIES
from upstash_workflow.types import (
    _FinishCondition,
)
from upstash_workflow import WorkflowContext
from dataclasses import dataclass

_logger = logging.getLogger(__name__)

TResponse = TypeVar("TResponse")
TInitialPayload = TypeVar("TInitialPayload")


@dataclass
class ServeOptions(Generic[TInitialPayload, TResponse]):
    qstash_client: QStash
    initial_payload_parser: Callable[[str], TInitialPayload]
    receiver: Optional[Receiver]
    base_url: Optional[str]
    env: Dict[str, Optional[str]]
    retries: int
    url: Optional[str]
    failure_function: Optional[
        Callable[[WorkflowContext[TInitialPayload], int, str, Dict[str, str]], Any]
    ]
    failure_url: Optional[str]


@dataclass
class ServeBaseOptions(
    Generic[TInitialPayload, TResponse], ServeOptions[TInitialPayload, TResponse]
):
    on_step_finish: Callable[[str, _FinishCondition], TResponse]


def _process_options(
    *,
    qstash_client: Optional[QStash] = None,
    on_step_finish: Optional[Callable[[str, _FinishCondition], TResponse]] = None,
    initial_payload_parser: Optional[Callable[[str], TInitialPayload]] = None,
    receiver: Optional[Receiver] = None,
    base_url: Optional[str] = None,
    env: Optional[Dict[str, Optional[str]]] = None,
    retries: Optional[int] = DEFAULT_RETRIES,
    url: Optional[str] = None,
    failure_function: Optional[
        Callable[[WorkflowContext, int, str, Dict[str, str]], Any]
    ] = None,
    failure_url: Optional[str] = None,
) -> ServeBaseOptions[TInitialPayload, TResponse]:
    """
    Fills the options with default values if they are not provided.

    Default values for:
    - qstash_client: QStash client created with QSTASH_TOKEN env var
    - on_step_finish: returns a Response with workflowRunId in the body (status: 200)
    - initial_payload_parser: calls json.loads if initial request body exists.
    - receiver: a Receiver if the required env vars are set
    - base_url: env variable UPSTASH_WORKFLOW_URL
    - env: os.environ
    - retries: DEFAULT_RETRIES
    - url: None
    """
    environment = env if env is not None else dict(os.environ)

    receiver_environment_variables_set = bool(
        environment.get("QSTASH_CURRENT_SIGNING_KEY")
        and environment.get("QSTASH_NEXT_SIGNING_KEY")
    )

    def _on_step_finish(
        workflow_run_id: str, finish_condition: _FinishCondition
    ) -> TResponse:
        if finish_condition == "auth-fail":
            _logger.error(AUTH_FAIL_MESSAGE)
            return cast(
                TResponse,
                _Response(
                    body={
                        "message": AUTH_FAIL_MESSAGE,
                        "workflowRunId": workflow_run_id,
                    },
                    status=400,
                ),
            )

        return cast(
            TResponse, _Response(body={"workflowRunId": workflow_run_id}, status=200)
        )

    def _initial_payload_parser(initial_request: str) -> TInitialPayload:
        # If there is no payload, return None
        if not initial_request:
            return cast(TInitialPayload, None)

        # Try to parse the payload
        try:
            return cast(TInitialPayload, json.loads(initial_request))
        except json.JSONDecodeError:
            # If parsing fails, return the raw string
            return cast(TInitialPayload, initial_request)
        except Exception as error:
            # If not a JSON parsing error, re-raise
            raise error

    return ServeBaseOptions[TInitialPayload, TResponse](
        qstash_client=qstash_client
        or QStash(
            cast(str, environment.get("QSTASH_TOKEN")),
            base_url=(environment.get("QSTASH_URL")),
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
        retries=DEFAULT_RETRIES if retries is None else retries,
        url=url,
        failure_url=failure_url,
        failure_function=failure_function,
    )


def _determine_urls(
    request: Union[_SyncRequest, _AsyncRequest],
    url: Optional[str],
    base_url: Optional[str],
    failure_function_exists: bool,
    failure_url: Optional[str],
) -> Tuple[str, Optional[str]]:
    initial_workflow_url = str(url if url is not None else request.url)

    if base_url:

        def replace_base(match: Match[str]) -> str:
            matched_base_url, path = match.groups()
            return base_url + (path or "")

        workflow_url = re.sub(
            r"^(https?://[^/]+)(/.*)?$", replace_base, initial_workflow_url
        )
    else:
        workflow_url = initial_workflow_url

    workflow_failure_url = workflow_url if failure_function_exists else failure_url
    return (workflow_url, workflow_failure_url)


AUTH_FAIL_MESSAGE = "Failed to authenticate Workflow request. If this is unexpected, see the caveat https://upstash.com/docs/workflow/basics/caveats#avoid-non-deterministic-code-outside-context-run"

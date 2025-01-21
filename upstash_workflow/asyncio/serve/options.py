import os
import json
import logging
from typing import Callable, Dict, Optional, cast, TypeVar
from qstash import AsyncQStash, Receiver
from upstash_workflow.workflow_types import _Response
from upstash_workflow.constants import DEFAULT_RETRIES
from upstash_workflow.types import (
    _FinishCondition,
)
from upstash_workflow.asyncio.types import ServeBaseOptions

_logger = logging.getLogger(__name__)

TResponse = TypeVar("TResponse")
TInitialPayload = TypeVar("TInitialPayload")


def _process_options(
    *,
    qstash_client: Optional[AsyncQStash] = None,
    on_step_finish: Optional[Callable[[str, _FinishCondition], TResponse]] = None,
    initial_payload_parser: Optional[Callable[[str], TInitialPayload]] = None,
    receiver: Optional[Receiver] = None,
    base_url: Optional[str] = None,
    env: Optional[Dict[str, Optional[str]]] = None,
    retries: Optional[int] = DEFAULT_RETRIES,
    url: Optional[str] = None,
) -> ServeBaseOptions[TInitialPayload, TResponse]:
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
        or AsyncQStash(
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
        retries=retries or DEFAULT_RETRIES,
        url=url,
    )


AUTH_FAIL_MESSAGE = "Failed to authenticate Workflow request. If this is unexpected, see the caveat https://upstash.com/docs/workflow/basics/caveats#avoid-non-deterministic-code-outside-context-run"

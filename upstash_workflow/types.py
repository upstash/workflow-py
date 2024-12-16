import os
from typing import Callable, Literal, Optional, Dict, Union
from qstash import AsyncQStash, Receiver
from dataclasses import dataclass


FinishCondition = Literal[
    "success",
    "duplicate-step",
    "fromCallback",
    "auth-fail",
    "failure-callback",
]


@dataclass
class WorkflowServeOptions[TResponse, TInitialPayload]:
    qstash_client: AsyncQStash
    on_step_finish: Callable[[str, FinishCondition], TResponse]
    initial_payload_parser: Callable[[str], TInitialPayload]
    receiver: Optional[Receiver]
    base_url: Optional[str]
    env: Union[Dict[str, Optional[str]], os._Environ[str]]
    retries: int
    url: Optional[str]


StepTypes = [
    "Initial",
    "Run",
    "SleepFor",
    "SleepUntil",
    "Call",
    "Wait",
    "Notify",
]

StepType = Literal[
    "Initial",
    "Run",
    "SleepFor",
    "SleepUntil",
    "Call",
    "Wait",
    "Notify",
]

HTTPMethods = Literal["GET", "POST", "PUT", "DELETE", "PATCH"]


@dataclass
class Step[TResult, TBody]:
    step_id: int
    step_name: str
    step_type: StepType
    out: Optional[TResult]
    sleep_for: Optional[Union[int, str]]
    sleep_until: Optional[int]
    concurrent: int
    target_step: Optional[int]

    call_url: Optional[str]
    call_method: Optional[HTTPMethods]
    call_body: Optional[TBody]
    call_headers: Optional[Dict[str, str]]

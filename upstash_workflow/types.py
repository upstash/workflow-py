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
    qstash_client: Optional[AsyncQStash]
    on_step_finish: Optional[Callable[[str, FinishCondition], TResponse]]
    initial_payload_parser: Optional[Callable[[str], TInitialPayload]]
    receiver: Optional[Receiver]
    base_url: Optional[str]
    env: Optional[Union[Dict[str, Optional[str]], os._Environ[str]]]
    retries: Optional[int]
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

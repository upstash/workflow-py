import os
from typing import (
    Callable,
    Literal,
    Optional,
    Dict,
    Union,
    List,
    TypeVar,
    Generic,
    Tuple,
)
from qstash import QStash, AsyncQStash, Receiver
from dataclasses import dataclass


FinishCondition = Literal[
    "success",
    "duplicate-step",
    "fromCallback",
    "auth-fail",
    "failure-callback",
]

TInitialPayload = TypeVar("TInitialPayload")
TResponse = TypeVar("TResponse")


WorkflowServeOptions = Tuple[
    Callable[[str, FinishCondition], TResponse],
    Callable[[str], TInitialPayload],
    Optional[Receiver],
    Optional[str],
    Union[Dict[str, Optional[str]], os._Environ],
    int,
    Optional[str],
]


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


TResult = TypeVar("TResult")
TBody = TypeVar("TBody")


@dataclass
class Step(Generic[TResult, TBody]):
    step_id: int
    step_name: str
    step_type: StepType
    concurrent: int

    out: Optional[TResult] = None
    sleep_for: Optional[Union[int, str]] = None
    sleep_until: Optional[int] = None
    target_step: Optional[int] = None

    call_method: Optional[HTTPMethods] = None
    call_body: Optional[TBody] = None
    call_headers: Optional[Dict[str, str]] = None
    call_url: Optional[str] = None


@dataclass
class ValidateRequestResponse:
    is_first_invocation: bool
    workflow_run_id: str


@dataclass
class ParseRequestResponse:
    raw_initial_payload: str
    steps: List[Step]

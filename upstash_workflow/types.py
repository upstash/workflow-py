from typing import (
    Literal,
    Optional,
    Dict,
    Union,
    List,
    TypeVar,
    Generic,
    Any,
    TypedDict,
)
from dataclasses import dataclass

_FinishCondition = Literal[
    "success",
    "duplicate-step",
    "fromCallback",
    "auth-fail",
    "failure-callback",
]

TInitialPayload = TypeVar("TInitialPayload")
TResponse = TypeVar("TResponse")


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


DefaultStep = Step[Any, Any]


@dataclass
class _ValidateRequestResponse:
    is_first_invocation: bool
    workflow_run_id: str


@dataclass
class _ParseRequestResponse:
    raw_initial_payload: str
    steps: List[DefaultStep]


@dataclass
class _HeadersResponse:
    headers: Dict[str, str]
    timeout_headers: Optional[Dict[str, List[str]]] = None


@dataclass
class CallResponse(Generic[TResult]):
    status: int
    body: TResult
    header: Dict[str, List[str]]


class CallResponseDict(TypedDict):
    status: int
    body: Any
    header: Dict[str, List[str]]

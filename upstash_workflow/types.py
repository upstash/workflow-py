from typing import (
    Callable,
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
from qstash import QStash, Receiver
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


@dataclass
class ServeOptions(Generic[TInitialPayload, TResponse]):
    qstash_client: QStash
    initial_payload_parser: Callable[[str], TInitialPayload]
    receiver: Optional[Receiver]
    base_url: Optional[str]
    env: Dict[str, Optional[str]]
    retries: int
    url: Optional[str]


@dataclass
class ServeBaseOptions(
    Generic[TInitialPayload, TResponse], ServeOptions[TInitialPayload, TResponse]
):
    on_step_finish: Callable[[str, _FinishCondition], TResponse]


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

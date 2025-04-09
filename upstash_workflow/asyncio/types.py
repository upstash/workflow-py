from typing import (
    Callable,
    Optional,
    Dict,
    Generic,
    TypeVar,
    Any,
)
from qstash import AsyncQStash, Receiver
from dataclasses import dataclass
from upstash_workflow.types import _FinishCondition
from upstash_workflow import AsyncWorkflowContext

TInitialPayload = TypeVar("TInitialPayload")
TResponse = TypeVar("TResponse")


@dataclass
class ServeOptions(Generic[TInitialPayload, TResponse]):
    qstash_client: AsyncQStash
    initial_payload_parser: Callable[[str], TInitialPayload]
    receiver: Optional[Receiver]
    base_url: Optional[str]
    env: Dict[str, Optional[str]]
    retries: int
    url: Optional[str]
    failure_function: Optional[
        Callable[[AsyncWorkflowContext, int, str, Dict[str, str]], Any]
    ]
    failure_url: Optional[str]


@dataclass
class ServeBaseOptions(
    Generic[TInitialPayload, TResponse], ServeOptions[TInitialPayload, TResponse]
):
    on_step_finish: Callable[[str, _FinishCondition], TResponse]

from typing import (
    Callable,
    Optional,
    Dict,
    Generic,
    TypeVar,
)
from qstash import AsyncQStash, Receiver
from dataclasses import dataclass
from upstash_workflow.types import _FinishCondition

TInitialPayload = TypeVar("TInitialPayload")
TResponse = TypeVar("TResponse")


@dataclass
class PublicServeOptions(Generic[TInitialPayload, TResponse]):
    qstash_client: AsyncQStash
    initial_payload_parser: Callable[[str], TInitialPayload]
    receiver: Optional[Receiver]
    base_url: Optional[str]
    env: Dict[str, Optional[str]]
    retries: int
    url: Optional[str]


@dataclass
class WorkflowServeOptions(
    Generic[TInitialPayload, TResponse], PublicServeOptions[TInitialPayload, TResponse]
):
    on_step_finish: Callable[[str, _FinishCondition], TResponse]

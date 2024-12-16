from typing import Callable, Awaitable, TypeVar, Protocol, Literal
from qstash import AsyncQStash


class WorkflowClient(AsyncQStash):
    pass


FinishCondition = Literal[
    "success",
    "duplicate-step",
    "fromCallback",
    "auth-fail",
    "failure-callback",
]

StepTypes = Literal[
    "Initial",
    "Run",
    "SleepFor",
    "SleepUntil",
    "Call",
    "Wait",
    "Notify",
]

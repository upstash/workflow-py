import json
import os
from typing import (
    List,
    Dict,
    Union,
    Optional,
    Callable,
    Awaitable,
    TypeVar,
    Any,
    cast,
    Generic,
)
from qstash import AsyncQStash
from upstash_workflow.constants import DEFAULT_RETRIES
from upstash_workflow.context.auto_executor import AutoExecutor
from upstash_workflow.context.steps import LazyFunctionStep, LazySleepStep, LazyCallStep
from upstash_workflow.types import (
    DefaultStep,
    HTTPMethods,
    CallResponse,
    CallResponseDict,
)
from upstash_workflow.context.steps import BaseLazyStep

TInitialPayload = TypeVar("TInitialPayload")
TResult = TypeVar("TResult")


class WorkflowContext(Generic[TInitialPayload]):
    def __init__(
        self,
        qstash_client: AsyncQStash,
        workflow_run_id: str,
        headers: Dict[str, str],
        steps: List[DefaultStep],
        url: str,
        initial_payload: TInitialPayload,
        env: Optional[Dict[str, Optional[str]]] = None,
        retries: Optional[int] = None,
    ):
        self.qstash_client: AsyncQStash = qstash_client
        self.workflow_run_id: str = workflow_run_id
        self._steps: List[DefaultStep] = steps
        self.url: str = url
        self.headers: Dict[str, str] = headers
        self.request_payload: TInitialPayload = initial_payload
        self.env: Dict[str, Optional[str]] = env or {}
        self.retries: int = retries or DEFAULT_RETRIES
        self._executor: AutoExecutor = AutoExecutor(self, self._steps)

    async def run(
        self,
        step_name: str,
        step_function: Union[Callable[[], Any], Callable[[], Awaitable[Any]]],
    ) -> Any:
        return await self._add_step(LazyFunctionStep(step_name, step_function))

    async def sleep(self, step_name: str, duration: Union[int, str]) -> None:
        await self._add_step(LazySleepStep(step_name, duration))

    async def call(
        self,
        step_name: str,
        *,
        url: str,
        method: HTTPMethods = "GET",
        body: Any = None,
        headers: Optional[Dict[str, str]] = None,
        retries: int = 0,
        timeout: Optional[Union[int, str]] = None,
    ) -> CallResponse[Any]:
        headers = headers or {}

        result = await self._add_step(
            LazyCallStep[CallResponseDict](
                step_name, url, method, body, headers, retries, timeout
            )
        )

        try:
            return CallResponse(
                status=result["status"],
                body=json.loads(result["body"]),
                header=result["header"],
            )
        except:
            return cast(CallResponse[Any], result)

    async def _add_step(self, step: BaseLazyStep[TResult]) -> TResult:
        return await self._executor.add_step(step)

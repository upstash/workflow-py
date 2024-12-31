import json
import os
import datetime
from typing import List, Dict, Union, Optional, Callable, Awaitable, TypeVar
from qstash import AsyncQStash
from upstash_workflow.constants import DEFAULT_RETRIES
from upstash_workflow.context.auto_executor import AutoExecutor
from upstash_workflow.context.steps import (
    LazyFunctionStep,
    LazySleepStep,
    LazySleepUntilStep,
    LazyCallStep,
)
from upstash_workflow.types import Step, HTTPMethods
from upstash_workflow.context.steps import BaseLazyStep

TInitialPayload = TypeVar("TInitialPayload")
TResult = TypeVar("TResult")


class WorkflowContext:
    def __init__(
        self,
        qstash_client: AsyncQStash,
        workflow_run_id: str,
        headers: Dict[str, str],
        steps: List[Step],
        url: str,
        initial_payload: TInitialPayload,
        raw_initial_payload,
        env: Union[Dict[str, Optional[str]], os._Environ],
        retries: int,
    ):
        self.qstash_client: AsyncQStash = qstash_client
        self.workflow_run_id: str = workflow_run_id
        self._steps: List[Step] = steps
        self.url: str = url
        self.headers: Dict[str, str] = headers
        self.request_payload: TInitialPayload = initial_payload
        self.raw_initial_payload = raw_initial_payload or json.dumps(
            self.request_payload
        )
        self.env: Union[Dict[str, str], Dict[str, Optional[str]], os._Environ] = (
            env or os.environ.copy()
        )
        self.retries: int = retries or DEFAULT_RETRIES
        self._executor: AutoExecutor = AutoExecutor(self, self._steps)

    async def run(
        self,
        step_name: str,
        step_function: Union[Callable[[], TResult], Callable[[], Awaitable[TResult]]],
    ):
        return await self._add_step(LazyFunctionStep(step_name, step_function))

    async def sleep(self, step_name: str, duration: Union[int, str]):
        await self._add_step(LazySleepStep(step_name, duration))

    async def sleep_until(
        self, step_name: str, data_time: Union[datetime.datetime, str, float]
    ) -> None:
        if isinstance(data_time, (int, float)):
            time = data_time
        elif isinstance(data_time, str):
            time = datetime.datetime.fromisoformat(data_time).timestamp()
        else:
            time = data_time.timestamp()

        await self._add_step(LazySleepUntilStep(step_name, round(time)))

    async def call(
        self,
        step_name: str,
        *,
        url: str,
        method: HTTPMethods = "GET",
        body=None,
        headers: Optional[Dict[str, str]] = None,
        retries: int = 0,
        timeout: Optional[Union[int, str]] = None,
    ):
        headers = headers or {}

        result = await self._add_step(
            LazyCallStep(step_name, url, method, body, headers, retries, timeout)
        )

        try:
            return {**result, "body": json.loads(result["body"])}
        except:
            return result

    async def _add_step(self, step: BaseLazyStep):
        return await self._executor.add_step(step)

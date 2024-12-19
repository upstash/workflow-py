import json
import os
from typing import List, Dict, Union, Optional, Callable, Awaitable
from qstash import AsyncQStash
from upstash_workflow.constants import DEFAULT_RETRIES
from upstash_workflow.context.auto_executor import AutoExecutor
from upstash_workflow.context.steps import LazyFunctionStep, LazySleepStep, LazyCallStep
from upstash_workflow.types import Step, HTTPMethods
from upstash_workflow.context.steps import BaseLazyStep


class WorkflowContext[TInitialPayload]:
    def __init__(
        self,
        qstash_client: AsyncQStash,
        workflow_run_id: str,
        headers: Dict[str, str],
        steps: List[Step],
        url: str,
        initial_payload: TInitialPayload,
        raw_initial_payload,
        env: Union[Dict[str, Optional[str]], os._Environ[str]],
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
        self.env: Union[Dict[str, str], Dict[str, Optional[str]], os._Environ[str]] = (
            env or os.environ.copy()
        )
        self.retries: int = retries or DEFAULT_RETRIES
        self._executor: AutoExecutor = AutoExecutor(self, self._steps)

    async def run[TResult](
        self,
        step_name: str,
        step_function: Union[Callable[[], TResult], Callable[[], Awaitable[TResult]]],
    ):
        return await self._add_step(LazyFunctionStep(step_name, step_function))

    async def sleep(self, step_name: str, duration: Union[int, str]):
        await self._add_step(LazySleepStep(step_name, duration))

    async def call[TResult](
        self,
        step_name: str,
        *,
        url: str,
        method: HTTPMethods = "GET",
        body=None,
        headers: Optional[Dict[str, str]] = None,
        retries: int = 0,
    ):
        headers = headers or {}

        result = await self._add_step(
            LazyCallStep(step_name, url, method, body, headers, retries)
        )

        try:
            return {**result, "body": json.loads(result["body"])}
        except:
            return result

    async def _add_step[TResult](self, step: BaseLazyStep[TResult]):
        return await self._executor.add_step(step)

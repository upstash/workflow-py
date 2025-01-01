import json
import os
from typing import List, Dict, Union, Optional, Callable, Awaitable, TypeVar
from inspect import isawaitable
from qstash import AsyncQStash
from upstash_workflow.context.auto_executor import AutoExecutor
from upstash_workflow.context.steps import LazyFunctionStep, LazySleepStep, LazyCallStep
from upstash_workflow.types import Step, HTTPMethods
from upstash_workflow.context.steps import BaseLazyStep
from upstash_workflow.context.context import BaseWorkflowContext

TInitialPayload = TypeVar("TInitialPayload")
TResult = TypeVar("TResult")


class WorkflowContext(BaseWorkflowContext):
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
        super().__init__(
            workflow_run_id,
            headers,
            steps,
            url,
            initial_payload,
            raw_initial_payload,
            env,
            retries,
        )
        self._executor: AutoExecutor = AutoExecutor(self, self._steps)
        self.qstash_client: AsyncQStash = qstash_client

    async def run(
        self,
        step_name: str,
        step_function: Union[Callable[[], TResult], Callable[[], Awaitable[TResult]]],
    ):
        return await self._add_step(LazyFunctionStep(step_name, step_function))

    async def sleep(self, step_name: str, duration: Union[int, str]):
        await self._add_step(LazySleepStep(step_name, duration))

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
        generator_add_step = self._executor.add_step(step)
        result = next(generator_add_step)
        if isinstance(result, dict):
            return result["step_out"]
        if step.step_type == "Run":
            if isawaitable(result):
                result = await result
            batch_requests = generator_add_step.send(result)
        else:
            batch_requests = result
        await self.qstash_client.message.batch_json(batch_requests)
        return next(generator_add_step)

import json
import os
from typing import List, Dict, Union, Optional, Callable, Awaitable, TypeVar
from abc import ABC, abstractmethod
from qstash import QStash
from upstash_workflow.constants import DEFAULT_RETRIES
from upstash_workflow.context.auto_executor import AutoExecutor
from upstash_workflow.context.steps import LazyFunctionStep, LazySleepStep, LazyCallStep
from upstash_workflow.types import Step, HTTPMethods
from upstash_workflow.context.steps import BaseLazyStep

TInitialPayload = TypeVar("TInitialPayload")
TResult = TypeVar("TResult")


class BaseWorkflowContext(ABC):
    def __init__(
        self,
        workflow_run_id: str,
        headers: Dict[str, str],
        steps: List[Step],
        url: str,
        initial_payload: TInitialPayload,
        raw_initial_payload,
        env: Union[Dict[str, Optional[str]], os._Environ],
        retries: int,
    ):
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

    @abstractmethod
    def run(
        self,
        step_name: str,
        step_function: Union[Callable[[], TResult], Callable[[], Awaitable[TResult]]],
    ):
        pass

    @abstractmethod
    def sleep(self, step_name: str, duration: Union[int, str]):
        pass

    @abstractmethod
    def call(
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
        pass

    @abstractmethod
    def _add_step(self, step: BaseLazyStep):
        pass


class WorkflowContext(BaseWorkflowContext):
    def __init__(
        self,
        qstash_client: QStash,
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
        self.qstash_client: QStash = qstash_client

    def run(
        self,
        step_name: str,
        step_function: Union[Callable[[], TResult], Callable[[], Awaitable[TResult]]],
    ):
        return self._add_step(LazyFunctionStep(step_name, step_function))

    def sleep(self, step_name: str, duration: Union[int, str]):
        self._add_step(LazySleepStep(step_name, duration))

    def call(
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

        result = self._add_step(
            LazyCallStep(step_name, url, method, body, headers, retries, timeout)
        )

        try:
            return {**result, "body": json.loads(result["body"])}
        except:
            return result

    def _add_step(self, step: BaseLazyStep):
        generator_add_step = self._executor.add_step(step)
        result = next(generator_add_step)
        if isinstance(result, dict):
            return result["step_out"]
        if step.step_type == "Run":
            batch_requests = generator_add_step.send(result)
        else:
            batch_requests = result
        self.qstash_client.message.batch_json(batch_requests)
        return next(generator_add_step)

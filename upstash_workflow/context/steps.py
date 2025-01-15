from abc import ABC, abstractmethod
from upstash_workflow.error import WorkflowError
from typing import (
    Optional,
    Union,
    Callable,
    Dict,
    Any,
    TypeVar,
    Generic,
)
from upstash_workflow.types import StepType, Step, DefaultStep, HTTPMethods

TResult = TypeVar("TResult")
TBody = TypeVar("TBody")


class _BaseLazyStep(ABC, Generic[TResult]):
    def __init__(self, step_name: str):
        if not step_name:
            raise WorkflowError(
                "A workflow step name cannot be undefined or an empty string. Please provide a name for your workflow step."
            )
        self.step_name = step_name
        self.step_type: Optional[StepType] = None

    @abstractmethod
    def get_plan_step(self, concurrent: int, target_step: int) -> Step[None, Any]:
        pass

    @abstractmethod
    def get_result_step(self, concurrent: int, step_id: int) -> Step[TResult, Any]:
        pass


class _LazyFunctionStep(_BaseLazyStep[TResult]):
    def __init__(
        self,
        step_name: str,
        step_function: Union[Callable[[], TResult], Callable[[], TResult]],
    ):
        super().__init__(step_name)
        self.step_function: Union[Callable[[], TResult], Callable[[], TResult]] = (
            step_function
        )
        self.step_type: StepType = "Run"

    def get_plan_step(self, concurrent: int, target_step: int) -> Step[None, Any]:
        return Step(
            step_id=0,
            step_name=self.step_name,
            step_type=self.step_type,
            concurrent=concurrent,
            target_step=target_step,
        )

    def get_result_step(self, concurrent: int, step_id: int) -> Step[TResult, Any]:
        result = self.step_function()

        return Step[TResult, Any](
            step_id=step_id,
            step_name=self.step_name,
            step_type=self.step_type,
            out=result,
            concurrent=concurrent,
        )


class _LazySleepStep(_BaseLazyStep[Any]):
    def __init__(self, step_name: str, sleep: Union[int, str]):
        super().__init__(step_name)
        self.sleep: Union[int, str] = sleep
        self.step_type: StepType = "SleepFor"

    def get_plan_step(self, concurrent: int, target_step: int) -> Step[None, Any]:
        return Step(
            step_id=0,
            step_name=self.step_name,
            step_type=self.step_type,
            sleep_for=self.sleep,
            concurrent=concurrent,
            target_step=target_step,
        )

    def get_result_step(self, concurrent: int, step_id: int) -> DefaultStep:
        return Step(
            step_id=step_id,
            step_name=self.step_name,
            step_type=self.step_type,
            sleep_for=self.sleep,
            concurrent=concurrent,
        )


class _LazySleepUntilStep(_BaseLazyStep[Any]):
    def __init__(self, step_name: str, sleep_until: int):
        super().__init__(step_name)
        self.sleep_until: int = sleep_until
        self.step_type: StepType = "SleepUntil"

    def get_plan_step(self, concurrent: int, target_step: int) -> Step[None, Any]:
        return Step(
            step_id=0,
            step_name=self.step_name,
            step_type=self.step_type,
            sleep_until=self.sleep_until,
            concurrent=concurrent,
            target_step=target_step,
        )

    def get_result_step(self, concurrent: int, step_id: int) -> DefaultStep:
        return Step(
            step_id=step_id,
            step_name=self.step_name,
            step_type=self.step_type,
            sleep_until=self.sleep_until,
            concurrent=concurrent,
        )


class _LazyCallStep(_BaseLazyStep[TResult]):
    def __init__(
        self,
        step_name: str,
        url: str,
        method: HTTPMethods,
        body: TBody,
        headers: Dict[str, str],
        retries: int,
        timeout: Optional[Union[int, str]],
    ):
        super().__init__(step_name)
        self.url: str = url
        self.method: HTTPMethods = method
        self.body: TBody = body
        self.headers: Dict[str, str] = headers
        self.retries: int = retries
        self.timeout: Optional[Union[int, str]] = timeout
        self.step_type: StepType = "Call"

    def get_plan_step(self, concurrent: int, target_step: int) -> Step[None, Any]:
        return Step(
            step_id=0,
            step_name=self.step_name,
            step_type=self.step_type,
            concurrent=concurrent,
            target_step=target_step,
        )

    def get_result_step(self, concurrent: int, step_id: int) -> Step[TResult, Any]:
        return Step(
            step_id=step_id,
            step_name=self.step_name,
            step_type=self.step_type,
            concurrent=concurrent,
            call_url=self.url,
            call_method=self.method,
            call_body=self.body,
            call_headers=self.headers,
        )

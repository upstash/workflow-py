from abc import ABC, abstractmethod
import asyncio
from typing import Optional, Awaitable, Union, Callable, cast, Dict
from upstash_workflow.types import StepType, Step, HTTPMethods


class BaseLazyStep[TResult](ABC):
    def __init__(self, step_name: str):
        self.step_name = step_name
        self.step_type: Optional[StepType] = None

    @abstractmethod
    def get_plan_step(self, concurrent: int, target_step: int) -> Step:
        pass

    @abstractmethod
    async def get_result_step(
        self, concurrent, step_id
    ) -> Awaitable[Step[TResult, None]]:
        pass


class LazyFunctionStep[TResult](BaseLazyStep):
    def __init__(
        self,
        step_name: str,
        step_function: Union[Callable[[], TResult], Callable[[], Awaitable[TResult]]],
    ):
        super().__init__(step_name)
        self.step_function: Union[
            Callable[[], TResult], Callable[[], Awaitable[TResult]]
        ] = step_function
        self.step_type: StepType = "Run"

    def get_plan_step(self, concurrent: int, target_step: int) -> Step:
        return Step(
            step_id=0,
            step_name=self.step_name,
            step_type=self.step_type,
            concurrent=concurrent,
            target_step=target_step,
        )

    async def get_result_step(
        self, concurrent: int, step_id: int
    ) -> Awaitable[Step[TResult, None]]:
        result = self.step_function()
        if asyncio.iscoroutine(result):
            result = await result

        return cast(
            Awaitable[Step[TResult, None]],
            Step(
                step_id=step_id,
                step_name=self.step_name,
                step_type=self.step_type,
                out=result,
                concurrent=concurrent,
            ),
        )


class LazySleepStep(BaseLazyStep):
    def __init__(self, step_name: str, sleep: Union[int, str]):
        super().__init__(step_name)
        self.sleep: Union[int, str] = sleep
        self.step_type: StepType = "SleepFor"

    def get_plan_step(self, concurrent: int, target_step: int) -> Step:
        return Step(
            step_id=0,
            step_name=self.step_name,
            step_type=self.step_type,
            sleep_for=self.sleep,
            concurrent=concurrent,
            target_step=target_step,
        )

    async def get_result_step(self, concurrent: int, step_id: int) -> Awaitable[Step]:
        return cast(
            Awaitable[Step],
            Step(
                step_id=step_id,
                step_name=self.step_name,
                step_type=self.step_type,
                sleep_for=self.sleep,
                concurrent=concurrent,
            ),
        )


class LazyCallStep[TResult, TBody](BaseLazyStep):
    def __init__(
        self,
        step_name: str,
        url: str,
        method: HTTPMethods,
        body: TBody,
        headers: Dict[str, str],
        retries: int,
    ):
        super().__init__(step_name)
        self.url: str = url
        self.method: HTTPMethods = method
        self.body: TBody = body
        self.headers: Dict[str, str] = headers
        self.retries: int = retries
        self.step_type: StepType = "Call"

    def get_plan_step(self, concurrent: int, target_step: int) -> Step:
        return Step(
            step_id=0,
            step_name=self.step_name,
            step_type=self.step_type,
            concurrent=concurrent,
            target_step=target_step,
        )

    async def get_result_step(
        self, concurrent: int, step_id: int
    ) -> Awaitable[Step[TResult, None]]:
        return cast(
            Awaitable[Step[TResult, None]],
            Step(
                step_id=step_id,
                step_name=self.step_name,
                step_type=self.step_type,
                concurrent=concurrent,
                call_url=self.url,
                call_method=self.method,
                call_body=self.body,
                call_headers=self.headers,
            ),
        )

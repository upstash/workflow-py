import json
import datetime
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
from upstash_workflow.asyncio.context.auto_executor import _AutoExecutor
from upstash_workflow.asyncio.context.steps import (
    _LazyFunctionStep,
    _LazySleepStep,
    _LazySleepUntilStep,
    _LazyCallStep,
    _BaseLazyStep,
)
from upstash_workflow.types import (
    DefaultStep,
    HTTPMethods,
    CallResponse,
    CallResponseDict,
)

TInitialPayload = TypeVar("TInitialPayload")
TResult = TypeVar("TResult")


class WorkflowContext(Generic[TInitialPayload]):
    """
    Upstash Workflow context

    See the docs for fields and methods https://upstash.com/docs/workflow/basics/context
    """

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
        self._executor: _AutoExecutor = _AutoExecutor(self, self._steps)

    async def run(
        self,
        step_name: str,
        step_function: Union[Callable[[], Any], Callable[[], Awaitable[Any]]],
    ) -> Any:
        """
        Executes a workflow step
        ```python
        async def _step1() -> str:
            return "result"
        result = await context.run("step1", _step1)
        ```

        :param step_name: name of the step
        :param step_function: step function to be executed
        :return: result of the step function
        """
        return await self._add_step(_LazyFunctionStep(step_name, step_function))

    async def sleep(self, step_name: str, duration: Union[int, str]) -> None:
        """
        Stops the execution for the duration provided.

        ```python
        await context.sleep("sleep1", 3)  # wait for three seconds
        ```

        :param step_name: name of the step
        :param duration: sleep duration in seconds
        :return: None
        """
        await self._add_step(_LazySleepStep(step_name, duration))

    async def sleep_until(
        self, step_name: str, date_time: Union[datetime.datetime, str, float]
    ) -> None:
        """
        Stops the execution until the date time provided.

        ```python
        await context.sleep_until("sleep1", time.time() + 3)  # wait for three seconds
        ```

        :param step_name: name of the step
        :param date_time: time to sleep until. Can be provided as a number (in unix seconds), datetime object or string in iso format
        :return: None
        """
        if isinstance(date_time, (int, float)):
            time = date_time
        elif isinstance(date_time, str):
            time = datetime.datetime.fromisoformat(date_time).timestamp()
        else:
            time = date_time.timestamp()

        await self._add_step(_LazySleepUntilStep(step_name, round(time)))

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
        """
        Makes a third party call through QStash in order to make a network call without consuming any runtime.

        ```python
        response = await context.call(
            "post-call-step",
            url="https://www.some-endpoint.com/api",
            method="POST",
            body={"message": "my-message"},
        )
        status, body, header = response.status, response.body, response.header
        ```

        tries to parse the result of the request as JSON. If it's not a JSON which can be parsed, simply returns the response body as it is.

        :param step_name: name of the step
        :param url: url to call
        :param method: call method. "GET" by default
        :param body: call body
        :param headers: call headers
        :param retries: number of call retries. 0 by default
        :param timeout: max duration to wait for the endpoint to respond. in seconds.
        :return: CallResponse object containing status, body and header
        """
        headers = headers or {}

        result = await self._add_step(
            _LazyCallStep[CallResponseDict](
                step_name, url, method, body, headers, retries, timeout
            )
        )

        try:
            return CallResponse(
                status=result["status"],
                body=json.loads(result["body"]),
                header=result["header"],
            )
        except Exception:
            return cast(CallResponse[Any], result)

    async def _add_step(self, step: _BaseLazyStep[TResult]) -> TResult:
        """
        Adds steps to the executor. Needed so that it can be overwritten in
        DisabledWorkflowContext.
        """
        return await self._executor.add_step(step)

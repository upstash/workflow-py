from __future__ import annotations
from typing import TYPE_CHECKING, List, Union, Literal, cast, Any, TypeVar
import json
from qstash.message import BatchJsonRequest
from upstash_workflow.constants import NO_CONCURRENCY
from upstash_workflow.error import WorkflowError, WorkflowAbort
from upstash_workflow.workflow_requests import _get_headers
from upstash_workflow.types import DefaultStep, HTTPMethods
from upstash_workflow.asyncio.context.steps import _BaseLazyStep, _LazyCallStep

if TYPE_CHECKING:
    from upstash_workflow import AsyncWorkflowContext

TResult = TypeVar("TResult")


class _AutoExecutor:
    def __init__(self, context: AsyncWorkflowContext[Any], steps: List[DefaultStep]):
        self.context: AsyncWorkflowContext[Any] = context
        self.steps: List[DefaultStep] = steps
        self.non_plan_step_count: int = len(
            [
                step
                for step in steps
                if not (hasattr(step, "target_step") and step.target_step)
            ]
        )
        self.step_count: int = 0
        self.plan_step_count: int = 0
        self.executing_step: Union[str, Literal[False]] = False
        self._already_executed: bool = False

    async def add_step(self, step_info: _BaseLazyStep[TResult]) -> TResult:
        self.step_count += 1
        return cast(TResult, await self.run_single(step_info))

    async def run_single(self, lazy_step: _BaseLazyStep[TResult]) -> Any:
        """
        Executes a step:
        - If the step result is available in the steps, returns the result
        - If the result is not avaiable, runs the function
        - Sends the result to QStash

        :param lazy_step: lazy step to execute
        :return: step result
        """
        if self.step_count < self.non_plan_step_count:
            step = self.steps[self.step_count + self.plan_step_count]
            _validate_step(lazy_step, step)
            return step.out

        if self._already_executed:
            raise WorkflowError(
                "Running parallel steps is not yet available in workflow-py. Ensure that you are awaiting the steps sequentially."
            )
        self._already_executed = True

        result_step = await lazy_step.get_result_step(NO_CONCURRENCY, self.step_count)
        await self.submit_steps_to_qstash([result_step], [lazy_step])
        return result_step.out

    async def submit_steps_to_qstash(
        self, steps: List[DefaultStep], lazy_steps: List[_BaseLazyStep[Any]]
    ) -> None:
        """
        sends the steps to QStash as batch

        :param steps: steps to send
        """
        if not steps:
            raise WorkflowError(
                f"Unable to submit steps to QStash. Provided list is empty. Current step: {self.step_count}"
            )

        batch_requests = []
        for index, single_step in enumerate(steps):
            lazy_step = lazy_steps[index]
            headers = _get_headers(
                "false",
                self.context.workflow_run_id,
                self.context.url,
                self.context.headers,
                single_step,
                self.context.retries,
                lazy_step.retries if isinstance(lazy_step, _LazyCallStep) else None,
                lazy_step.timeout if isinstance(lazy_step, _LazyCallStep) else None,
            ).headers

            will_wait = (
                single_step.concurrent == NO_CONCURRENCY or single_step.step_id == 0
            )

            single_step.out = json.dumps(single_step.out)

            batch_requests.append(
                BatchJsonRequest(
                    headers=headers,
                    method=cast(HTTPMethods, single_step.call_method),
                    body=single_step.call_body,
                    url=single_step.call_url,
                )
                if single_step.call_url
                else (
                    BatchJsonRequest(
                        headers=headers,
                        body={
                            "method": "POST",
                            "stepId": single_step.step_id,
                            "stepName": single_step.step_name,
                            "stepType": single_step.step_type,
                            "out": single_step.out,
                            "sleepFor": single_step.sleep_for,
                            "sleepUntil": single_step.sleep_until,
                            "concurrent": single_step.concurrent,
                            "targetStep": single_step.target_step,
                            "callUrl": single_step.call_url,
                            "callMethod": single_step.call_method,
                            "callBody": single_step.call_body,
                            "callHeaders": single_step.call_headers,
                        },
                        url=self.context.url,
                        not_before=cast(  # TODO: Change not_before type in BatchJsonRequest
                            Any, single_step.sleep_until if will_wait else None
                        ),
                        delay=cast(Any, single_step.sleep_for if will_wait else None),
                    )
                )
            )
        await self.context.qstash_client.message.batch_json(batch_requests)
        raise WorkflowAbort(steps[0].step_name, steps[0])


def _validate_step(
    lazy_step: _BaseLazyStep[Any], step_from_request: DefaultStep
) -> None:
    """
    Given a BaseLazyStep which is created during execution and a Step parsed
    from the incoming request; compare the step names and types to make sure
    that they are the same.

    Raises `WorkflowError` if there is a difference.

    :param lazy_step: lazy step created during execution
    :param step_from_request: step parsed from incoming request
    """
    if lazy_step.step_name != step_from_request.step_name:
        raise WorkflowError(
            f"Incompatible step name. Expected '{lazy_step.step_name}', "
            f"got '{step_from_request.step_name}' from the request"
        )

    if lazy_step.step_type != step_from_request.step_type:
        raise WorkflowError(
            f"Incompatible step type. Expected '{lazy_step.step_type}', "
            f"got '{step_from_request.step_type}' from the request"
        )

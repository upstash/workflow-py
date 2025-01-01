from __future__ import annotations
from typing import TYPE_CHECKING, List, Union, Literal, cast, Any
from collections.abc import Generator
import json
from qstash.message import BatchJsonRequest
from upstash_workflow.constants import NO_CONCURRENCY
from upstash_workflow.error import WorkflowError, WorkflowAbort
from upstash_workflow.workflow_requests import get_headers
from upstash_workflow.types import Step, HTTPMethods
from upstash_workflow.context.steps import BaseLazyStep, LazyCallStep

if TYPE_CHECKING:
    from upstash_workflow.context.context import WorkflowContext
    from upstash_workflow.asyncio.context.context import (
        WorkflowContext as AsyncWorkflowContext,
    )


class AutoExecutor:
    def __init__(
        self, context: Union[WorkflowContext, AsyncWorkflowContext], steps: List[Step]
    ):
        self.context: Union[WorkflowContext, AsyncWorkflowContext] = context
        self.steps: List[Step] = steps
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

    def add_step(self, step_info: BaseLazyStep) -> Generator:
        self.step_count += 1
        generator_run_single = self.run_single(step_info)
        if step_info.step_type == "Run":
            result = yield next(generator_run_single)
            yield generator_run_single.send(result)
        else:
            yield next(generator_run_single)
        yield next(generator_run_single)

    def run_single(self, lazy_step: BaseLazyStep) -> Generator:
        if self.step_count < self.non_plan_step_count:
            step = self.steps[self.step_count + self.plan_step_count]
            validate_step(lazy_step, step)
            yield {"step_out": step.out}
            return
        generator_get_result_step = lazy_step.get_result_step(
            NO_CONCURRENCY, self.step_count
        )
        if lazy_step.step_type == "Run":
            result = yield next(generator_get_result_step)
            result_step = generator_get_result_step.send(result)
        else:
            result_step = next(generator_get_result_step)
        generator_submit_steps_to_qstash = self.submit_steps_to_qstash(
            [result_step], [lazy_step]
        )
        yield next(generator_submit_steps_to_qstash)
        next(generator_submit_steps_to_qstash)
        yield result_step.out

    def submit_steps_to_qstash(
        self, steps: List[Step], lazy_steps: List[BaseLazyStep]
    ) -> Generator:
        if not steps:
            raise WorkflowError(
                f"Unable to submit steps to QStash. Provided list is empty. Current step: {self.step_count}"
            )

        batch_requests = []
        for index, single_step in enumerate(steps):
            lazy_step = lazy_steps[index]
            headers = get_headers(
                "false",
                self.context.workflow_run_id,
                self.context.url,
                self.context.headers,
                single_step,
                self.context.retries,
                lazy_step.retries if isinstance(lazy_step, LazyCallStep) else None,
                lazy_step.timeout if isinstance(lazy_step, LazyCallStep) else None,
            )

            will_wait = (
                single_step.concurrent == NO_CONCURRENCY or single_step.step_id == 0
            )

            single_step.out = json.dumps(single_step.out)

            batch_requests.append(
                BatchJsonRequest(
                    headers=headers["headers"],
                    method=cast(HTTPMethods, single_step.call_method),
                    body=single_step.call_body,
                    url=single_step.call_url,
                )
                if single_step.call_url
                else (
                    BatchJsonRequest(
                        headers=headers["headers"],
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
        yield batch_requests

        raise WorkflowAbort(steps[0].step_name, steps[0])


def validate_step(lazy_step: BaseLazyStep, step_from_request) -> None:
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

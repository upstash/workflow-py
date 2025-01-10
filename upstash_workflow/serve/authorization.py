import os
from typing import Callable, Awaitable, Literal, TypeVar, Generic
from qstash import AsyncQStash
from upstash_workflow.context.context import WorkflowContext
from upstash_workflow.context.steps import BaseLazyStep
from upstash_workflow.error import WorkflowAbort

TInitialPayload = TypeVar("TInitialPayload")
TResult = TypeVar("TResult")


class DisabledWorkflowContext(
    Generic[TInitialPayload], WorkflowContext[TInitialPayload]
):
    __disabled_message = "disabled-qstash-worklfow-run"

    async def _add_step(self, _step: BaseLazyStep[TResult]) -> TResult:
        raise WorkflowAbort(self.__disabled_message)

    async def cancel(self) -> None:
        return

    @classmethod
    async def try_authentication(
        cls,
        route_function: Callable[[WorkflowContext[TInitialPayload]], Awaitable[None]],
        context: WorkflowContext[TInitialPayload],
    ) -> Literal["run-ended", "step-found"]:
        disabled_context = DisabledWorkflowContext(
            qstash_client=AsyncQStash(
                base_url="disabled-client", token="disabled-client"
            ),
            workflow_run_id=context.workflow_run_id,
            headers=context.headers,
            steps=[],
            url=context.url,
            initial_payload=context.request_payload,
            env=context.env,
            retries=context.retries,
        )

        try:
            await route_function(disabled_context)
        except WorkflowAbort as error:
            if error.step_name == cls.__disabled_message:
                return "step-found"
            raise error
        except Exception as error:
            raise error

        return "run-ended"

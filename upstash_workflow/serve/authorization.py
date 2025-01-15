from typing import Callable, Literal, TypeVar, Generic
from qstash import QStash
from upstash_workflow import WorkflowContext
from upstash_workflow.context.steps import _BaseLazyStep
from upstash_workflow.error import WorkflowAbort

TInitialPayload = TypeVar("TInitialPayload")
TResult = TypeVar("TResult")


class _DisabledWorkflowContext(
    Generic[TInitialPayload], WorkflowContext[TInitialPayload]
):
    """
    Workflow context which throws `WorkflowAbort` before running the steps.

    Used for making a dry run before running any steps to check authentication.

    Consider an endpoint like this:
    ```python
    @serve.post("/auth")
    async def auth(context: WorkflowContext[str]) -> None:
        if context.headers.get("authentication" != "Bearer secret_password"):
            print("Authentication failed.")
            return
        # ...
    ```

    the `serve` method will first call the route_function with a `DisabledWorkflowContext`.
    Here is the action we take in different cases:
    - "step-found": we will run the workflow related sections of `serve`.
    - "run-ended": simply return success and end the workflow
    - error: returns 500.
    """

    __disabled_message = "disabled-qstash-worklfow-run"

    def _add_step(self, _step: _BaseLazyStep[TResult]) -> TResult:
        """
        Overwrite the `WorkflowContext._add_step` method to always raise `WorkflowAbort`
        error in order to stop the execution whenever we encounter a step.

        :param _step:
        """
        raise WorkflowAbort(self.__disabled_message)

    def cancel(self) -> None:
        """
        overwrite cancel method to do nothing
        """
        return

    @classmethod
    def try_authentication(
        cls,
        route_function: Callable[[WorkflowContext[TInitialPayload]], None],
        context: WorkflowContext[TInitialPayload],
    ) -> Literal["run-ended", "step-found"]:
        """
        copies the passed context to create a DisabledWorkflowContext. Then, runs the
        route function with the new context.

        - returns "run-ended" if there are no steps found or
            if the auth failed and user called `return`
        - returns "step-found" if DisabledWorkflowContext._add_step is called.
        - if there is another error, returns the error.

        :param route_function:
        """
        disabled_context = _DisabledWorkflowContext(
            qstash_client=QStash(base_url="disabled-client", token="disabled-client"),
            workflow_run_id=context.workflow_run_id,
            headers=context.headers,
            steps=[],
            url=context.url,
            initial_payload=context.request_payload,
            env=context.env,
            retries=context.retries,
        )

        try:
            route_function(disabled_context)
        except WorkflowAbort as error:
            if error.step_name == cls.__disabled_message:
                return "step-found"
            raise error
        except Exception as error:
            raise error

        return "run-ended"

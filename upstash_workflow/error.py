from typing import Optional, Dict
from qstash.errors import QStashError
from upstash_workflow.types import DefaultStep


class WorkflowError(QStashError):
    """
    Error raised during Workflow execution
    """

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.name = "WorkflowError"


class WorkflowAbort(Exception):
    """
    Raised when the workflow executes a function successfully and aborts to end the execution
    """

    def __init__(
        self,
        step_name: str,
        step_info: Optional[DefaultStep] = None,
        cancel_workflow: bool = False,
    ) -> None:
        self.step_name: str = step_name
        self.step_info: Optional[DefaultStep] = step_info
        self.cancel_workflow: bool = cancel_workflow

        message = (
            "This is an Upstash Workflow error thrown after a step executes. It is expected to be raised."
            " Make sure that you await for each step. Also, if you are using try/except blocks, you should not wrap"
            " context.run/sleep/sleep_until/call methods with try/except."
            f" Aborting workflow after executing step '{step_name}'."
        )

        super().__init__(message)
        self.name = "WorkflowAbort"


def _format_workflow_error(error: object) -> Dict[str, str]:
    """
    Formats an unknown error to match the FailureFunctionPayload format

    :param error:
    :return:
    """
    if isinstance(error, Exception):
        return {"error": error.__class__.__name__, "message": str(error)}
    return {"error": "Error", "message": "An error occurred while executing workflow."}

from typing import Optional
from qstash.errors import QStashError
from upstash_workflow.types import Step


class WorkflowError(QStashError):
    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.name = "WorkflowError"


class WorkflowAbort(Exception):
    def __init__(
        self, step_name: str, step_info: Optional[Step], cancel_workflow: bool = False
    ) -> None:
        self.step_name: str = step_name
        self.step_info: Optional[Step] = step_info
        self.cancel_workflow: bool = cancel_workflow

        message = (
            "This is an Upstash Workflow error thrown after a step executes. It is expected to be raised."
            " Make sure that you await for each step. Also, if you are using try/except blocks, you should not wrap"
            " context.run/sleep/sleep_until/call methods with try/except."
            f" Aborting workflow after executing step '{step_name}'."
        )

        super().__init__(message)
        self.name = "WorkflowAbort"


def format_workflow_error(error: object):
    if isinstance(error, Exception):
        return {"error": error.__class__.__name__, "message": str(error)}
    return {"error": "Error", "message": "An error occurred while executing workflow."}

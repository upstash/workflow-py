class QStashError(Exception): ...


class QStashWorkflowError(QStashError):
    def __init__(self, *args: object) -> None:
        super().__init__(*args)


class QStashWorkflowAbort(Exception):
    def __init__(self, step_name, step_info):
        self.step_name = step_name
        self.step_info = step_info

        message = (
            "This is an Upstash Workflow error thrown after a step executes. It is expected to be raised."
            " Make sure that you await for each step. Also, if you are using try/catch blocks, you should not wrap"
            " context.run/sleep/sleepUntil/call methods with try/catch."
            f" Aborting workflow after executing step '{step_name}'."
        )

        super().__init__(message)
        self.name = "QStashWorkflowAbort"


def format_workflow_error(error: Exception):
    if isinstance(error, Exception):
        return {"error": error.__class__.__name__, "message": str(error)}
    return {"error": "Error", "message": "An error occurred while executing workflow."}

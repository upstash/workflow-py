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
            " Make sure that you await for each step. Also, if you are using try/except blocks, you should not wrap"
            " context.run/sleep/sleep_until/call methods with try/except."
            f" Aborting workflow after executing step '{step_name}'."
        )

        super().__init__(message)
        self.name = "QStashWorkflowAbort"


def format_workflow_error(error: Exception):
    if isinstance(error, Exception):
        return {"error": error.__class__.__name__, "message": str(error)}
    return {"error": "Error", "message": "An error occurred while executing workflow."}

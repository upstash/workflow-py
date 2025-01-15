from flask import Flask
from typing import Dict
import time
from upstash_workflow.flask import Serve
from upstash_workflow import WorkflowContext, CallResponse

app = Flask(__name__)
serve = Serve(app)


@app.route("/api/py/")
def root() -> Dict[str, str]:
    return {"message": "Hello World"}


def some_work(input: str) -> str:
    return f"processed '{input}'"


@serve.route("/api/py/sleep")
def sleep(context: WorkflowContext[str]) -> None:
    input = context.request_payload

    def _step1() -> str:
        output = some_work(input)
        print("step 1 input", input, "output", output)
        return output

    result1: str = context.run("step1", _step1)

    context.sleep_until("sleep1", time.time() + 3)

    def _step2() -> str:
        output = some_work(result1)
        print("step 2 input", result1, "output", output)
        return output

    result2: str = context.run("step2", _step2)

    context.sleep("sleep2", 2)

    def _step3() -> None:
        output = some_work(result2)
        print("step 3 input", result2, "output", output)

    context.run("step3", _step3)


@app.route("/api/py/get-data", methods=["POST"])
def get_data() -> Dict[str, str]:
    return {"message": "get data response"}


@serve.route("/api/py/call")
def call(context: WorkflowContext[str]) -> None:
    input = context.request_payload

    def _step1() -> str:
        output = some_work(input)
        print("step 1 input", input, "output", output)
        return output

    result1: str = context.run("step1", _step1)

    response: CallResponse[Dict[str, str]] = context.call(
        "get-data",
        url=f"{context.env.get('UPSTASH_WORKFLOW_URL', 'http://localhost:8000')}/api/py/get-data",
        method="POST",
        body={"message": result1},
    )

    def _step2() -> str:
        output = some_work(response.body["message"])
        print("step 2 input", response, "output", output)
        return output

    context.run("step2", _step2)


@serve.route("/api/py/auth")
def auth(context: WorkflowContext[str]) -> None:
    if context.headers.get("Authentication") != "Bearer secret_password":
        print("Authentication failed.")
        return

    def _step1() -> str:
        return "output 1"

    context.run("step1", _step1)

    def _step2() -> str:
        return "output 2"

    context.run("step2", _step2)

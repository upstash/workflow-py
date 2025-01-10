from fastapi import FastAPI
from typing import Dict
from upstash_workflow.fastapi import Serve
from upstash_workflow.context.context import WorkflowContext
from upstash_workflow.types import CallResponse

app = FastAPI()
serve = Serve(app)


@app.get("/")
async def root() -> Dict[str, str]:
    return {"message": "Hello World"}


def some_work(input: str) -> str:
    return f"processed '{input}'"


@serve.post("/sleep")
async def sleep(context: WorkflowContext[str]) -> None:
    input = context.request_payload

    async def _step1() -> str:
        output = some_work(input)
        print("step 1 input", input, "output", output)
        return output

    result1: str = await context.run("step1", _step1)

    await context.sleep("sleep1", 3)

    async def _step2() -> str:
        output = some_work(result1)
        print("step 2 input", result1, "output", output)
        return output

    result2: str = await context.run("step2", _step2)

    await context.sleep("sleep2", 2)

    async def _step3() -> None:
        output = some_work(result2)
        print("step 3 input", result2, "output", output)

    await context.run("step3", _step3)


@app.post("/get-data")
async def get_data() -> Dict[str, str]:
    return {"message": "get data response"}


@serve.post("/call")
async def call(context: WorkflowContext[str]) -> None:
    input = context.request_payload

    async def _step1() -> str:
        output = some_work(input)
        print("step 1 input", input, "output", output)
        return output

    result1: str = await context.run("step1", _step1)

    response: CallResponse[Dict[str, str]] = await context.call(
        "get-data",
        url=f"{context.env.get('UPSTASH_WORKFLOW_URL', 'http://localhost:8000')}/get-data",
        method="POST",
        body={"message": result1},
    )

    async def _step2() -> str:
        output = some_work(response.body["message"])
        print("step 2 input", response, "output", output)
        return output

    await context.run("step2", _step2)


@serve.post("/auth")
async def auth(context):
    if context.headers.get("authentication") != "Bearer secret_password":
        print("Authentication failed.")
        return

    async def _step1():
        return "output 1"

    await context.run("step1", _step1)

    async def _step2():
        return "output 2"

    await context.run("step2", _step2)

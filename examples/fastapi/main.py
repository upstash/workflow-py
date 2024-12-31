from fastapi import FastAPI
from upstash_workflow.fastapi import Serve
import time

app = FastAPI()
serve = Serve(app)


@app.get("/")
async def root():
    return {"message": "Hello World"}


def some_work(input: str) -> str:
    return f"processed '{input}'"


@serve.post("/sleep")
async def sleep(context):
    input = context.request_payload

    async def _step1():
        output = some_work(input)
        print("step 1 input", input, "output", output)
        return output

    result1 = await context.run("step1", _step1)

    await context.sleep_until("sleep1", time.time() + 3)

    async def _step2():
        output = some_work(result1)
        print("step 2 input", result1, "output", output)
        return output

    result2 = await context.run("step2", _step2)

    await context.sleep("sleep2", 2)

    async def _step3():
        output = some_work(result2)
        print("step 3 input", result2, "output", output)

    await context.run("step3", _step3)


@app.post("/get-data")
async def get_data():
    return {"message": "get data response"}


@serve.post("/call")
async def call(context):
    input = context.request_payload

    async def _step1():
        output = some_work(input)
        print("step 1 input", input, "output", output)
        return output

    result1 = await context.run("step1", _step1)

    response = await context.call(
        "get-data",
        url=f"{context.env.get('UPSTASH_WORKFLOW_URL', 'http://localhost:8000')}/get-data",
        method="POST",
        body={"message": result1},
    )

    async def _step2():
        output = some_work(response)
        print("step 2 input", response, "output", output)
        return output

    await context.run("step2", _step2)

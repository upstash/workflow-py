# Upstash Workflow SDK

**Upstash Workflow** lets you write durable, reliable and performant serverless functions. Get delivery guarantees, automatic retries on failure, scheduling and more without managing any infrastructure.

See [the documentation](https://upstash.com/docs/workflow/getstarted) for more details

## Quick Start

Here, we will briefly showcase how you can get started with Upstash Workflow using FastAPI.

Alternatively, you can check [our quickstarts for different frameworks](https://upstash.com/docs/workflow/quickstarts/platforms), including [FastAPI](https://upstash.com/docs/workflow/quickstarts/fastapi) and [Next.js & FastAPI](https://upstash.com/docs/workflow/quickstarts/nextjs-fastapi).

### Install

First, create a new directory and set up a virtual environment:

```sh
python -m venv venv
source venv/bin/activate
```

Then, install the required packages:

```sh
pip install fastapi uvicorn upstash-workflow
```

### Get QStash token

Go to [Upstash Console](https://console.upstash.com/qstash) and copy the `QSTASH_TOKEN`, set it in the `.env` file.

```sh
export QSTASH_TOKEN=
```

### Define a Workflow Endpoint

To declare workflow endpoints, use the `@serve.post` decorator. Save the following code to `main.py`:

```python
from fastapi import FastAPI
from upstash_workflow.fastapi import Serve
from upstash_workflow import AsyncWorkflowContext

app = FastAPI()
serve = Serve(app)

# mock function
def some_work(input: str) -> str:
    return f"processed '{input}'"

# serve endpoint which expects a string payload:
@serve.post("/example")
async def example(context: AsyncWorkflowContext[str]) -> None:
    # get request body:
    input = context.request_payload

    async def _step1() -> str:
        output = some_work(input)
        print("step 1 input", input, "output", output)
        return output

    # run the first step:
    result: str = await context.run("step1", _step1)

    async def _step2() -> None:
        output = some_work(result)
        print("step 2 input", result, "output", output)

    # run the second step:
    await context.run("step2", _step2)
```

In the example, you can see that steps are declared through the `context` object.

The kinds of steps which are available are:

* `context.run`: execute a function
* `context.sleep`: sleep for some time
* `context.sleep_until`: sleep until some timestamp
* `context.call`: make a third party call without consuming any runtime

You can [learn more about these methods from our documentation](https://upstash.com/docs/workflow/basics/context).

### Run the Server

Upstash Workflow needs a public URL to orchestrate the workflow. Check out our [Local Development](https://upstash.com/docs/workflow/howto/local-development) guide to learn how to set up a local tunnel.

Create the tunnel and set the `UPSTASH_WORKFLOW_URL` environment variable in the `.env` file with the public URL:

```sh
ngrok http localhost:8000
```

```sh
export UPSTASH_WORKFLOW_URL=
```

Then, set the environment variables:

```sh
source .env
```

Finally, run the server:

```sh
uvicorn main:app --reload
```

FastAPI server will be running at `localhost:8000`.

## Contributing

### Development

1. Clone the repository
2. Install [Poetry](https://python-poetry.org/docs/#installation)
3. Install dependencies with `poetry install`
4. Create a .env file with `cp .env.example .env` and fill in the environment variables
5. Run tests with `poetry run pytest`
6. Format with `poetry run ruff format .`
7. Check with `poetry run ruff check .`
8. Type check with `poetry run mypy --show-error-codes .`

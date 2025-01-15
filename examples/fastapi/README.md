# Upstash Workflow FastAPI Example

This is an example of how to use Upstash Workflow in a FastAPI project. You can learn more in [Workflow documentation for FastAPI](https://upstash.com/docs/workflow/quickstarts/fastapi).

## Development

> \[!TIP]
> You can use [the `bootstrap.sh` script](https://github.com/upstash/workflow-py/tree/master/examples) to run this example with a local tunnel.
>
> Simply set the environment variables as explained below and run the following command in the `workflow-py/examples` directory:
>
> ```
> bash bootstrap.sh fastapi
> ```

1. Create a virtual environment

```sh
python -m venv venv
source venv/bin/activate
```

2. Install the dependencies

```bash
pip install fastapi uvicorn upstash-workflow
```

3. Get the credentials from the [Upstash Console](https://console.upstash.com/qstash) and add them to the `.env` file.

```bash
export QSTASH_TOKEN=
```

4. Open a local tunnel to port of the development server. Check out our [Local Development](https://upstash.com/docs/workflow/howto/local-development) guide to learn how to set up a local tunnel.

```bash
ngrok http 8000
```

Also, set the `UPSTASH_WORKLFOW_URL` environment variable to the public url provided by ngrok.

```bash
export UPSTASH_WORKFLOW_URL=
```

5. Set the environment variables

```bash
source .env
```

6. Run the development server

```bash
uvicorn main:app --reload
```

7. Send a `POST` request to the `/sleep` endpoint.

```bash
curl -X POST "http://localhost:8000/sleep" -d '{"text": "hello world!"}'
```

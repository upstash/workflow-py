Create a Local Tunnel

```sh
ngrok http 8000
```

Fill Environment Variables

```sh
QSTASH_URL=
QSTASH_TOKEN=
UPSTASH_WORKFLOW_URL=
```

Install Dependencies

```sh
pip install -e .
pip install fastapi uvicorn
```

Run FastAPI

```sh
cd examples/fastapi
uvicorn main:app --reload
```

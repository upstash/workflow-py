Fill Environment Variables

```sh
QSTASH_URL=
QSTASH_TOKEN=
UPSTASH_WORKFLOW_URL=
```

Run `bootstrap.sh`

```sh
cd examples
bash bootstrap.sh fastapi
```

### Development

1. Clone the repository
2. Install [Poetry](https://python-poetry.org/docs/#installation)
3. Install dependencies with `poetry install`
4. Create a .env file with `cp .env.example .env` and fill in the environment variables
5. Format with `poetry run ruff format .`
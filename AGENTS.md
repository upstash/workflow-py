# Agents

## Linting and type checking

Before committing any changes, always run:

```
poetry run ruff format .
poetry run ruff check .
poetry run mypy --show-error-codes .
```

Fix all errors before committing. Do not commit code with unused imports, formatting issues, or type errors.

from fastapi import FastAPI, Request, Response
from typing import Callable, Awaitable, cast, TypeVar
from upstash_workflow.asyncio.serve.serve import serve
from upstash_workflow.asyncio.context.context import WorkflowContext

TInitialPayload = TypeVar("TInitialPayload")


class Serve:
    def __init__(self, app: FastAPI):
        self.app = app

    def post(self, path):
        def decorator(
            route_function: Callable[[WorkflowContext], Awaitable[None]],
        ):
            handler = cast(
                Callable[[Request], Awaitable[Response]],
                serve(route_function).get("handler"),
            )

            async def _handler_wrapper(request: Request):
                return await handler(request)

            self.app.add_api_route(path, _handler_wrapper, methods=["POST"])
            return route_function

        return decorator

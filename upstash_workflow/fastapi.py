from fastapi import FastAPI, Request, Response
from typing import Callable, Awaitable, cast
from upstash_workflow.serve.serve import serve
from upstash_workflow.context.context import WorkflowContext


class Serve:
    def __init__(self, app: FastAPI):
        self.app = app

    def post[TInitialPayload](self, path):
        def decorator(
            route_function: Callable[
                [WorkflowContext[TInitialPayload]], Awaitable[None]
            ]
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

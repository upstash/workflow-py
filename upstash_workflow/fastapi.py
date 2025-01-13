from inspect import iscoroutinefunction
from fastapi import FastAPI, Request, Response
from typing import Callable, Awaitable, cast, TypeVar, Union
from upstash_workflow.serve.serve import serve
from upstash_workflow.context.context import WorkflowContext
from upstash_workflow.asyncio.serve.serve import serve as async_serve
from upstash_workflow.asyncio.context.context import (
    WorkflowContext as AsyncWorkflowContext,
)

TInitialPayload = TypeVar("TInitialPayload")

RouteFunction = Callable[[WorkflowContext[TInitialPayload]], None]
AsyncRouteFunction = Callable[[AsyncWorkflowContext[TInitialPayload]], Awaitable[None]]


class Serve:
    def __init__(self, app: FastAPI):
        self.app = app

    def post(
        self, path: str
    ) -> Callable[
        [Union[RouteFunction[TInitialPayload], AsyncRouteFunction[TInitialPayload]]],
        Union[RouteFunction[TInitialPayload], AsyncRouteFunction[TInitialPayload]],
    ]:
        def decorator(
            route_function: Union[
                RouteFunction[TInitialPayload], AsyncRouteFunction[TInitialPayload]
            ],
        ) -> Union[RouteFunction[TInitialPayload], AsyncRouteFunction[TInitialPayload]]:
            if iscoroutinefunction(route_function):
                sync_handler = cast(
                    Callable[[Request], Awaitable[Response]],
                    async_serve(
                        cast(AsyncRouteFunction[TInitialPayload], route_function)
                    ).get("handler"),
                )

                async def _sync_handler_wrapper(request: Request) -> Response:
                    return await sync_handler(request)

                self.app.add_api_route(path, _sync_handler_wrapper, methods=["POST"])

            else:
                async_handler = cast(
                    Callable[[Request], Response],
                    serve(cast(RouteFunction[TInitialPayload], route_function)).get(
                        "handler"
                    ),
                )

                def _async_handler_wrapper(request: Request) -> Response:
                    return async_handler(request)

                self.app.add_api_route(path, _async_handler_wrapper, methods=["POST"])

            return route_function

        return decorator

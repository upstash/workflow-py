from inspect import iscoroutinefunction
from flask import Flask, request
from werkzeug.wrappers import Request, Response
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
    def __init__(self, app: Flask):
        self.app = app

    def post(self, path: str) -> Callable[
        [Union[RouteFunction[TInitialPayload], AsyncRouteFunction[TInitialPayload]]],
        Union[RouteFunction[TInitialPayload], AsyncRouteFunction[TInitialPayload]],
    ]:
        def decorator(
            route_function: Union[
                RouteFunction[TInitialPayload], AsyncRouteFunction[TInitialPayload]
            ],
        ) -> Union[RouteFunction[TInitialPayload], AsyncRouteFunction[TInitialPayload]]:
            if iscoroutinefunction(route_function):
                async_handler = cast(
                    Callable[[Request], Awaitable[Response]],
                    async_serve(
                        cast(AsyncRouteFunction[TInitialPayload], route_function)
                    ).get("handler"),
                )

                async def _async_handler_wrapper() -> Response:
                    return await async_handler(request)

                self.app.add_url_rule(
                    path,
                    route_function.__name__,
                    _async_handler_wrapper,
                    methods=["POST"],
                )

            else:
                sync_handler = cast(
                    Callable[[Request], Response],
                    serve(cast(RouteFunction[TInitialPayload], route_function)).get(
                        "handler"
                    ),
                )

                def _sync_handler_wrapper() -> Response:
                    print(request.get_json())
                    return sync_handler(request)

                self.app.add_url_rule(
                    path,
                    route_function.__name__,
                    _sync_handler_wrapper,
                    methods=["POST"],
                )

            return route_function

        return decorator

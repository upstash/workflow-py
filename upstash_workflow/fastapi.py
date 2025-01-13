from inspect import iscoroutinefunction
from fastapi import FastAPI, Request, Response
from typing import Callable, Awaitable, cast, TypeVar, Union, Optional, Dict
from qstash import QStash, AsyncQStash, Receiver
from upstash_workflow.serve.serve import serve
from upstash_workflow.context.context import WorkflowContext
from upstash_workflow.asyncio.serve.serve import serve as async_serve
from upstash_workflow.asyncio.context.context import (
    WorkflowContext as AsyncWorkflowContext,
)
from upstash_workflow.types import FinishCondition

TInitialPayload = TypeVar("TInitialPayload")
TResponse = TypeVar("TResponse")

RouteFunction = Callable[[WorkflowContext[TInitialPayload]], None]
AsyncRouteFunction = Callable[[AsyncWorkflowContext[TInitialPayload]], Awaitable[None]]


class Serve:
    def __init__(self, app: FastAPI):
        self.app = app

    def post(
        self,
        path: str,
        *,
        qstash_client: Optional[Union[QStash, AsyncQStash]] = None,
        on_step_finish: Optional[Callable[[str, FinishCondition], TResponse]] = None,
        initial_payload_parser: Optional[Callable[[str], TInitialPayload]] = None,
        receiver: Optional[Receiver] = None,
        base_url: Optional[str] = None,
        env: Optional[Dict[str, Optional[str]]] = None,
        retries: Optional[int] = None,
        url: Optional[str] = None,
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
                if qstash_client and not isinstance(qstash_client, AsyncQStash):
                    raise ValueError(
                        "qstash_client must be an instance of AsyncQStash when using an async route function"
                    )
                async_handler = cast(
                    Callable[[Request], Awaitable[Response]],
                    async_serve(
                        cast(AsyncRouteFunction[TInitialPayload], route_function),
                        qstash_client=cast(AsyncQStash, qstash_client),
                        on_step_finish=on_step_finish,
                        initial_payload_parser=initial_payload_parser,
                        receiver=receiver,
                        base_url=base_url,
                        env=env,
                        retries=retries,
                        url=url,
                    ).get("handler"),
                )

                async def _async_handler_wrapper(request: Request) -> Response:
                    return await async_handler(request)

                self.app.add_api_route(path, _async_handler_wrapper, methods=["POST"])

            else:
                if qstash_client and not isinstance(qstash_client, QStash):
                    raise ValueError(
                        "qstash_client must be an instance of QStash when using a sync route function"
                    )
                sync_handler = cast(
                    Callable[[Request], Response],
                    serve(
                        cast(RouteFunction[TInitialPayload], route_function),
                        qstash_client=cast(QStash, qstash_client),
                        on_step_finish=on_step_finish,
                        initial_payload_parser=initial_payload_parser,
                        receiver=receiver,
                        base_url=base_url,
                        env=env,
                        retries=retries,
                        url=url,
                    ).get("handler"),
                )

                def _sync_handler_wrapper(request: Request) -> Response:
                    return sync_handler(request)

                self.app.add_api_route(path, _sync_handler_wrapper, methods=["POST"])

            return route_function

        return decorator

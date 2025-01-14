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
        """
        Decorator to serve a Upstash Workflow in a FastAPI project.

        :param route_function: A function that uses WorkflowContext as a parameter and runs a workflow.
        :param qstash_client: QStash client
        :param on_step_finish: Function called to return a response after each step execution
        :param initial_payload_parser: Function to parse the initial payload passed by the user
        :param receiver: Receiver to verify *all* requests by checking if they come from QStash. By default, a receiver is created from the env variables QSTASH_CURRENT_SIGNING_KEY and QSTASH_NEXT_SIGNING_KEY if they are set.
        :param base_url: Base Url of the workflow endpoint. Can be used to set if there is a local tunnel or a proxy between QStash and the workflow endpoint. Will be set to the env variable UPSTASH_WORKFLOW_URL if not passed. If the env variable is not set, the url will be infered as usual from the `request.url` or the `url` parameter in `serve` options.
        :param env: Optionally, one can pass an env object mapping environment variables to their keys. Useful in cases like cloudflare with hono.
        :param retries: Number of retries to use in workflow requests, 3 by default
        :param url: Url of the endpoint where the workflow is set up. If not set, url will be inferred from the request.
        :return:
        """

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

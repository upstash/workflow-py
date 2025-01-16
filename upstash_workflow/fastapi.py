from inspect import iscoroutinefunction
import json
import os
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from typing import Callable, Awaitable, cast, TypeVar, Optional, Dict
from qstash import AsyncQStash, Receiver
from upstash_workflow import async_serve, AsyncWorkflowContext
from upstash_workflow.workflow_types import _Response as WorkflowResponse

TInitialPayload = TypeVar("TInitialPayload")
TResponse = TypeVar("TResponse")

AsyncRouteFunction = Callable[[AsyncWorkflowContext[TInitialPayload]], Awaitable[None]]


class Serve:
    def __init__(self, app: FastAPI):
        self.app = app

    def post(
        self,
        path: str,
        *,
        qstash_client: Optional[AsyncQStash] = None,
        initial_payload_parser: Optional[Callable[[str], TInitialPayload]] = None,
        receiver: Optional[Receiver] = None,
        base_url: Optional[str] = None,
        env: Optional[Dict[str, Optional[str]]] = None,
        retries: Optional[int] = None,
        url: Optional[str] = None,
    ) -> Callable[
        [AsyncRouteFunction[TInitialPayload]], AsyncRouteFunction[TInitialPayload]
    ]:
        """
        Decorator to serve a Upstash Workflow in a FastAPI project.

        :param route_function: A function that uses AsyncWorkflowContext as a parameter and runs a workflow.
        :param qstash_client: AsyncQStash client
        :param initial_payload_parser: Function to parse the initial payload passed by the user
        :param receiver: Receiver to verify *all* requests by checking if they come from QStash. By default, a receiver is created from the env variables QSTASH_CURRENT_SIGNING_KEY and QSTASH_NEXT_SIGNING_KEY if they are set.
        :param base_url: Base Url of the workflow endpoint. Can be used to set if there is a local tunnel or a proxy between QStash and the workflow endpoint. Will be set to the env variable UPSTASH_WORKFLOW_URL if not passed. If the env variable is not set, the url will be infered as usual from the `request.url` or the `url` parameter in `serve` options.
        :param env: Optionally, one can pass an env object mapping environment variables to their keys. Useful in cases like cloudflare with hono.
        :param retries: Number of retries to use in workflow requests, 3 by default
        :param url: Url of the endpoint where the workflow is set up. If not set, url will be inferred from the request.
        :return:
        """

        if not (
            qstash_client
            or (env is not None and env.get("QSTASH_TOKEN"))
            or (env is None and os.getenv("QSTASH_TOKEN"))
        ):
            raise ValueError(
                "QSTASH_TOKEN is missing. Make sure to set it in the environment variables or pass qstash_client or env as an argument."
            )

        def decorator(
            route_function: AsyncRouteFunction[TInitialPayload],
        ) -> AsyncRouteFunction[TInitialPayload]:
            if iscoroutinefunction(route_function):
                if qstash_client and not isinstance(qstash_client, AsyncQStash):
                    raise ValueError(
                        "qstash_client must be an instance of AsyncQStash when using an async route function"
                    )
                async_handler = cast(
                    Callable[[Request], Awaitable[WorkflowResponse]],
                    async_serve(
                        cast(AsyncRouteFunction[TInitialPayload], route_function),
                        qstash_client=cast(AsyncQStash, qstash_client),
                        initial_payload_parser=initial_payload_parser,
                        receiver=receiver,
                        base_url=base_url,
                        env=env,
                        retries=retries,
                        url=url,
                    ).get("handler"),
                )

                async def _async_handler_wrapper(request: Request) -> JSONResponse:
                    workflow_response: WorkflowResponse = await async_handler(request)
                    return JSONResponse(
                        content=json.loads(workflow_response.body),
                        status_code=workflow_response.status,
                        headers=workflow_response.headers,
                    )

                self.app.add_api_route(path, _async_handler_wrapper, methods=["POST"])

            else:
                raise ValueError(
                    "route_function must be an async function when using the @serve.post decorator"
                )

            return route_function

        return decorator

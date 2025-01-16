from inspect import iscoroutinefunction
import os
from flask import Flask, request
from werkzeug.wrappers import Response
from typing import Callable, cast, TypeVar, Optional, Dict
from qstash import QStash, Receiver
from upstash_workflow import serve, WorkflowContext
from upstash_workflow.workflow_types import (
    _SyncRequest as WorkflowRequest,
    _Response as WorkflowResponse,
)


TInitialPayload = TypeVar("TInitialPayload")
TResponse = TypeVar("TResponse")

RouteFunction = Callable[[WorkflowContext[TInitialPayload]], None]


class Serve:
    def __init__(self, app: Flask):
        self.app = app

    def route(
        self,
        path: str,
        *,
        qstash_client: Optional[QStash] = None,
        initial_payload_parser: Optional[Callable[[str], TInitialPayload]] = None,
        receiver: Optional[Receiver] = None,
        base_url: Optional[str] = None,
        env: Optional[Dict[str, Optional[str]]] = None,
        retries: Optional[int] = None,
        url: Optional[str] = None,
    ) -> Callable[
        [RouteFunction[TInitialPayload]],
        RouteFunction[TInitialPayload],
    ]:
        """
        Decorator to serve a Upstash Workflow in a Flask project.

        :param route_function: A function that uses WorkflowContext as a parameter and runs a workflow.
        :param qstash_client: QStash client
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
            route_function: RouteFunction[TInitialPayload],
        ) -> RouteFunction[TInitialPayload]:
            if iscoroutinefunction(route_function):
                raise ValueError(
                    "route_function must be a sync function when using the @serve.route decorator"
                )

            else:
                if qstash_client and not isinstance(qstash_client, QStash):
                    raise ValueError(
                        "qstash_client must be an instance of QStash when using a sync route function"
                    )
                sync_handler = cast(
                    Callable[[WorkflowRequest], WorkflowResponse],
                    serve(
                        route_function,
                        qstash_client=cast(QStash, qstash_client),
                        initial_payload_parser=initial_payload_parser,
                        receiver=receiver,
                        base_url=base_url,
                        env=env,
                        retries=retries,
                        url=url,
                    ).get("handler"),
                )

                def _sync_handler_wrapper() -> Response:
                    workflow_response: WorkflowResponse = sync_handler(
                        WorkflowRequest(
                            body=request.data.decode("utf-8"),
                            headers=cast(Dict[str, str], request.headers),
                            method=request.method,
                            url=request.url,
                            query=request.args,
                        )
                    )
                    return Response(
                        workflow_response.body,
                        status=workflow_response.status,
                        headers=workflow_response.headers,
                    )

                self.app.add_url_rule(
                    path,
                    route_function.__name__,
                    _sync_handler_wrapper,
                    methods=["POST"],
                )

            return route_function

        return decorator

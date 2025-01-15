from inspect import iscoroutinefunction
from flask import Flask, request
from werkzeug.wrappers import Response
from typing import Callable, cast, TypeVar, Optional, Dict
from qstash import QStash, Receiver
from upstash_workflow import _serve_base, WorkflowContext
from upstash_workflow.types import _FinishCondition
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
        on_step_finish: Optional[Callable[[str, _FinishCondition], TResponse]] = None,
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
                    _serve_base(
                        route_function,
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

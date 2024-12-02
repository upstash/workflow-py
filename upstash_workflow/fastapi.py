from fastapi import FastAPI, Request
from upstash_workflow.serve.serve import serve


class Serve:
    def __init__(self, app: FastAPI):
        self.app = app

    def post(self, path):
        def decorator(route_function):
            handler = serve(route_function, {}).get("handler")

            async def _handler_wrapper(request: Request):
                return await handler(request)

            self.app.add_api_route(path, _handler_wrapper, methods=["POST"])
            return route_function

        return decorator

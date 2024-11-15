from fastapi import FastAPI
from workflow.serve.serve import serve


class Serve:
    def __init__(self, app: FastAPI):
        self.app = app

    def post(self, path):
        def decorator(route_function):
            handler = serve(route_function, {}).get("handler")
            self.app.add_api_route(path, handler, methods=["POST"])
            return route_function

        return decorator

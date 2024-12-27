import json
from aiohttp import web
from typing import Any, Dict, Optional, Union, Callable

WORKFLOW_ENDPOINT = "https://www.my-website.com/api"
MOCK_QSTASH_SERVER_PORT = 8080
MOCK_QSTASH_SERVER_URL = f"http://localhost:{MOCK_QSTASH_SERVER_PORT}"


class ResponseFields:
    def __init__(self, body: Any, status: int):
        self.body = body
        self.status = status


class RequestFields:
    def __init__(
        self,
        method: str,
        url: str,
        token: str,
        body: Optional[Any] = None,
        headers: Optional[Dict[str, Optional[str]]] = None,
    ):
        self.method = method
        self.url = url
        self.token = token
        self.body = body
        self.headers = headers


async def mock_qstash_server(
    execute: Callable,
    response_fields: ResponseFields,
    receives_request: Union[RequestFields, bool],
):
    should_be_called = bool(receives_request)
    called = False

    async def handler(request: web.Request) -> web.Response:
        nonlocal called
        called = True

        if not receives_request:
            return web.Response(
                text="assertion in mock QStash failed. fetch shouldn't have been called.",
                status=400,
            )

        try:
            assert isinstance(receives_request, RequestFields)
            assert request.method == receives_request.method
            assert str(request.url) == receives_request.url
            assert (
                request.headers.get("authorization")
                == f"Bearer {receives_request.token}"
            )

            if receives_request.body:
                request_body = await request.text()
                try:
                    parsed_body = json.loads(request_body)
                except json.JSONDecodeError:
                    parsed_body = request_body
                assert parsed_body == receives_request.body
            else:
                request_body = await request.text()
                assert not request_body

            if receives_request.headers:
                for header, value in receives_request.headers.items():
                    assert request.headers.get(header) == value

        except AssertionError as error:
            return web.Response(
                text=f"assertion in mock QStash failed: {str(error)}", status=400
            )

        return web.json_response(
            data=[{"messageId": response_fields.body, "deduplicated": False}],
            status=response_fields.status,
        )

    app = web.Application()
    app.router.add_route("*", "/{tail:.*}", handler)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "localhost", MOCK_QSTASH_SERVER_PORT)

    try:
        await site.start()
        await execute()
        assert called == should_be_called
    finally:
        await runner.cleanup()

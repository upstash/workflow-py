import json
from aiohttp import web
from typing import Any, Union, Callable
from tests.utils import MOCK_QSTASH_SERVER_PORT, RequestFields, ResponseFields


async def mock_qstash_server(
    execute: Callable[[], Any],
    response_fields: ResponseFields,
    receives_request: Union[RequestFields, bool],
) -> None:
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

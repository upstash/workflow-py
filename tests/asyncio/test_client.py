import pytest
from upstash_workflow.asyncio import AsyncClient
from tests.utils import MOCK_QSTASH_SERVER_URL
import json
import asyncio
from aiohttp import web


@pytest.fixture
def client() -> AsyncClient:
    return AsyncClient(token="mock-token", base_url=MOCK_QSTASH_SERVER_URL)


async def create_mock_server(handler, port=8080):
    """Helper to create a mock HTTP server for testing."""
    app = web.Application()
    app.router.add_route("*", "/{tail:.*}", handler)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "localhost", port)
    await site.start()

    return runner


@pytest.mark.asyncio
async def test_notify_without_workflow_run_id(client: AsyncClient) -> None:
    event_id = "event-id-123"
    event_data = {"data": "notify-data-456"}

    async def handler(request):
        assert request.method == "POST"
        assert request.path == f"/v2/notify/{event_id}"
        assert request.headers.get("authorization") == "Bearer mock-token"

        body = await request.text()
        parsed_body = json.loads(body)
        assert parsed_body == event_data

        response_data = [
            {
                "messageId": "msg-123",
                "url": "https://example.com",
                "workflowRunId": "wfr-123",
            }
        ]

        return web.json_response(response_data)

    runner = await create_mock_server(handler)

    try:
        result = await client.notify(event_id=event_id, event_data=event_data)
        assert isinstance(result, list)
        assert len(result) == 1
        assert result[0].message_id == "msg-123"
    finally:
        await runner.cleanup()


@pytest.mark.asyncio
async def test_notify_with_workflow_run_id(client: AsyncClient) -> None:
    event_id = "event-id-123"
    event_data = {"data": "notify-data-456"}
    workflow_run_id = "wfr_789"

    async def handler(request):
        assert request.method == "POST"
        assert request.path == f"/v2/notify/{workflow_run_id}/{event_id}"
        assert request.headers.get("authorization") == "Bearer mock-token"

        body = await request.text()
        parsed_body = json.loads(body)
        assert parsed_body == event_data

        response_data = [
            {
                "messageId": "msg-123",
                "url": "https://example.com",
                "workflowRunId": workflow_run_id,
            }
        ]

        return web.json_response(response_data)

    runner = await create_mock_server(handler)

    try:
        result = await client.notify(
            event_id=event_id, event_data=event_data, workflow_run_id=workflow_run_id
        )
        assert isinstance(result, list)
        assert len(result) == 1
        assert result[0].workflow_run_id == workflow_run_id
    finally:
        await runner.cleanup()


@pytest.mark.asyncio
async def test_cancel(client: AsyncClient) -> None:
    workflow_run_id = "wfr_123"

    async def handler(request):
        assert request.method == "DELETE"
        assert request.path == f"/v2/workflows/runs/{workflow_run_id}"
        assert "cancel=true" in request.query_string
        assert request.headers.get("authorization") == "Bearer mock-token"

        return web.Response(status=200)

    runner = await create_mock_server(handler)

    try:
        result = await client.cancel(workflow_run_id=workflow_run_id)
        assert result is True
    finally:
        await runner.cleanup()


@pytest.mark.asyncio
async def test_get_waiters(client: AsyncClient) -> None:
    event_id = "event-id-123"

    async def handler(request):
        assert request.method == "GET"
        assert request.path == f"/v2/waiters/{event_id}"
        assert request.headers.get("authorization") == "Bearer mock-token"

        response_data = [
            {
                "workflowRunId": "wfr-123",
                "eventId": event_id,
                "eventData": "some-data",
                "timeout": 3600,
            }
        ]

        return web.json_response(response_data)

    runner = await create_mock_server(handler)

    try:
        result = await client.get_waiters(event_id=event_id)
        assert isinstance(result, list)
        assert len(result) == 1
        assert result[0].event_id == event_id
    finally:
        await runner.cleanup()

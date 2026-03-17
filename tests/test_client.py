import pytest
from upstash_workflow import Client
from tests.utils import (
    mock_qstash_server,
    RequestFields,
    ResponseFields,
    MOCK_QSTASH_SERVER_URL,
)


@pytest.fixture
def client() -> Client:
    return Client(token="mock-token", base_url=MOCK_QSTASH_SERVER_URL)


def test_notify_without_workflow_run_id(client: Client) -> None:
    event_id = "event-id-123"
    event_data = {"data": "notify-data-456"}

    def execute() -> None:
        result = client.notify(event_id=event_id, event_data=event_data)
        assert isinstance(result, list)

    # Update the mock server to return the expected notify response
    class CustomResponseFields(ResponseFields):
        def __init__(self, body, status):
            super().__init__(body, status)

    # Create a custom mock that returns notify response format
    import json

    class NotifyRequestHandler:
        pass

    import http.server
    import socketserver
    import threading

    called = [False]

    class RequestHandler(http.server.BaseHTTPRequestHandler):
        def do_POST(self) -> None:
            called[0] = True

            assert self.command == "POST"
            assert f"http://localhost:8080{self.path}" == f"{MOCK_QSTASH_SERVER_URL}/v2/notify/{event_id}"
            assert self.headers.get("authorization") == "Bearer mock-token"

            request_body = self.rfile.read(int(self.headers.get("Content-Length", 0))).decode("utf-8")
            parsed_body = json.loads(request_body)
            assert parsed_body == event_data

            response_data = json.dumps([
                {
                    "messageId": "msg-123",
                    "url": "https://example.com",
                    "workflowRunId": "wfr-123"
                }
            ])

            self.send_response(200)
            self.send_header("Content-type", "application/json")
            self.end_headers()
            self.wfile.write(response_data.encode())

        def log_message(self, format, *args):
            pass  # Suppress logging

    server = socketserver.TCPServer(("localhost", 8080), RequestHandler)
    server.allow_reuse_address = True

    server_thread = threading.Thread(target=server.serve_forever)
    server_thread.daemon = True
    server_thread.start()

    try:
        execute()
        assert called[0]
    finally:
        server.shutdown()
        server.server_close()
        if server_thread.is_alive():
            server_thread.join(timeout=1)


def test_notify_with_workflow_run_id(client: Client) -> None:
    event_id = "event-id-123"
    event_data = {"data": "notify-data-456"}
    workflow_run_id = "wfr_789"

    def execute() -> None:
        result = client.notify(event_id=event_id, event_data=event_data, workflow_run_id=workflow_run_id)
        assert isinstance(result, list)

    import json
    import http.server
    import socketserver
    import threading

    called = [False]

    class RequestHandler(http.server.BaseHTTPRequestHandler):
        def do_POST(self) -> None:
            called[0] = True

            assert self.command == "POST"
            assert f"http://localhost:8080{self.path}" == f"{MOCK_QSTASH_SERVER_URL}/v2/notify/{workflow_run_id}/{event_id}"
            assert self.headers.get("authorization") == "Bearer mock-token"

            request_body = self.rfile.read(int(self.headers.get("Content-Length", 0))).decode("utf-8")
            parsed_body = json.loads(request_body)
            assert parsed_body == event_data

            response_data = json.dumps([
                {
                    "messageId": "msg-123",
                    "url": "https://example.com",
                    "workflowRunId": workflow_run_id
                }
            ])

            self.send_response(200)
            self.send_header("Content-type", "application/json")
            self.end_headers()
            self.wfile.write(response_data.encode())

        def log_message(self, format, *args):
            pass  # Suppress logging

    server = socketserver.TCPServer(("localhost", 8080), RequestHandler)
    server.allow_reuse_address = True

    server_thread = threading.Thread(target=server.serve_forever)
    server_thread.daemon = True
    server_thread.start()

    try:
        execute()
        assert called[0]
    finally:
        server.shutdown()
        server.server_close()
        if server_thread.is_alive():
            server_thread.join(timeout=1)


def test_cancel(client: Client) -> None:
    workflow_run_id = "wfr_123"

    def execute() -> None:
        result = client.cancel(workflow_run_id=workflow_run_id)
        assert result is True

    import http.server
    import socketserver
    import threading

    called = [False]

    class RequestHandler(http.server.BaseHTTPRequestHandler):
        def do_DELETE(self) -> None:
            called[0] = True

            assert self.command == "DELETE"
            assert f"http://localhost:8080{self.path}" == f"{MOCK_QSTASH_SERVER_URL}/v2/workflows/runs/{workflow_run_id}?cancel=true"
            assert self.headers.get("authorization") == "Bearer mock-token"

            self.send_response(200)
            self.send_header("Content-type", "application/json")
            self.end_headers()
            self.wfile.write(b"")

        def log_message(self, format, *args):
            pass  # Suppress logging

    server = socketserver.TCPServer(("localhost", 8080), RequestHandler)
    server.allow_reuse_address = True

    server_thread = threading.Thread(target=server.serve_forever)
    server_thread.daemon = True
    server_thread.start()

    try:
        execute()
        assert called[0]
    finally:
        server.shutdown()
        server.server_close()
        if server_thread.is_alive():
            server_thread.join(timeout=1)


def test_get_waiters(client: Client) -> None:
    event_id = "event-id-123"

    def execute() -> None:
        result = client.get_waiters(event_id=event_id)
        assert isinstance(result, list)

    import json
    import http.server
    import socketserver
    import threading

    called = [False]

    class RequestHandler(http.server.BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            called[0] = True

            assert self.command == "GET"
            assert f"http://localhost:8080{self.path}" == f"{MOCK_QSTASH_SERVER_URL}/v2/waiters/{event_id}"
            assert self.headers.get("authorization") == "Bearer mock-token"

            response_data = json.dumps([
                {
                    "workflowRunId": "wfr-123",
                    "eventId": event_id,
                    "eventData": "some-data",
                    "timeout": 3600
                }
            ])

            self.send_response(200)
            self.send_header("Content-type", "application/json")
            self.end_headers()
            self.wfile.write(response_data.encode())

        def log_message(self, format, *args):
            pass  # Suppress logging

    server = socketserver.TCPServer(("localhost", 8080), RequestHandler)
    server.allow_reuse_address = True

    server_thread = threading.Thread(target=server.serve_forever)
    server_thread.daemon = True
    server_thread.start()

    try:
        execute()
        assert called[0]
    finally:
        server.shutdown()
        server.server_close()
        if server_thread.is_alive():
            server_thread.join(timeout=1)

import json
import http.server
import socketserver
import threading
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


class ThreadedTCPServer(socketserver.TCPServer):
    allow_reuse_address = True
    daemon_threads = True


def mock_qstash_server(
    execute: Callable[[], Any],
    response_fields: ResponseFields,
    receives_request: Union[RequestFields, bool],
) -> None:
    should_be_called = bool(receives_request)
    called = [False]

    class RequestHandler(http.server.BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            self.handle_request()

        def do_POST(self) -> None:
            self.handle_request()

        def do_PUT(self) -> None:
            self.handle_request()

        def do_DELETE(self) -> None:
            self.handle_request()

        def handle_request(self) -> None:
            called[0] = True

            if not receives_request:
                self.send_response(400)
                self.send_header("Content-type", "text/plain")
                self.end_headers()
                self.wfile.write(
                    b"assertion in mock QStash failed. fetch shouldn't have been called."
                )
                return

            try:
                assert isinstance(receives_request, RequestFields)
                assert self.command == receives_request.method
                assert (
                    f"http://localhost:{MOCK_QSTASH_SERVER_PORT}{self.path}"
                    == receives_request.url
                )
                assert (
                    self.headers.get("authorization")
                    == f"Bearer {receives_request.token}"
                )

                if receives_request.body:
                    request_body = self.rfile.read(
                        int(self.headers.get("Content-Length", 0))
                    ).decode("utf-8")
                    try:
                        parsed_body = json.loads(request_body)
                    except json.JSONDecodeError:
                        parsed_body = request_body
                    assert parsed_body == receives_request.body
                else:
                    request_body = self.rfile.read(
                        int(self.headers.get("Content-Length", 0))
                    ).decode("utf-8")
                    assert not request_body
                if receives_request.headers:
                    for header, value in receives_request.headers.items():
                        assert self.headers.get(header.lower()) == value

            except AssertionError as error:
                self.send_response(400)
                self.send_header("Content-type", "text/plain")
                self.end_headers()
                self.wfile.write(
                    f"assertion in mock QStash failed: {str(error)}".encode()
                )
                return

            response_data = json.dumps(
                [{"messageId": response_fields.body, "deduplicated": False}]
            )

            self.send_response(response_fields.status)
            self.send_header("Content-type", "application/json")
            self.end_headers()
            self.wfile.write(response_data.encode())

    server = None
    server_thread = None

    try:
        server = ThreadedTCPServer(
            ("localhost", MOCK_QSTASH_SERVER_PORT), RequestHandler
        )

        server_thread = threading.Thread(target=server.serve_forever)
        server_thread.daemon = True
        server_thread.start()

        execute()
        assert called[0] == should_be_called

    finally:
        if server:
            server.shutdown()
            server.server_close()

        if server_thread and server_thread.is_alive():
            server_thread.join(timeout=1)

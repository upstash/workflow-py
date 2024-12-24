from dataclasses import dataclass
from typing import Any, Dict, Optional
import json


@dataclass
class Response:
    body: str
    status: int
    headers: Optional[Dict[str, str]] = None

    def __init__(
        self, body: Any, status: int = 200, headers: Optional[Dict[str, str]] = None
    ):
        self.body = json.dumps(body) if not isinstance(body, str) else body
        self.status = status
        self.headers = headers or {"Content-Type": "application/json"}


@dataclass
class Request:
    body: str
    headers: Optional[Dict[str, str]] = None
    method: str = "GET"
    url: str = ""
    query_params: Optional[Dict[str, str]] = None

    def __init__(
        self,
        body: Any = None,
        headers: Optional[Dict[str, str]] = None,
        method: str = "GET",
        url: str = "",
        query_params: Optional[Dict[str, str]] = None,
    ):
        self.body = (
            json.dumps(body) if body and not isinstance(body, str) else body or ""
        )
        self.headers = headers or {"Content-Type": "application/json"}
        self.method = method.upper()
        self.url = url
        self.query_params = query_params or {}

    def json(self) -> Any:
        if not self.body:
            return {}
        return json.loads(self.body)

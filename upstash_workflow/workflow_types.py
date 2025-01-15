from dataclasses import dataclass, field
from typing import Any, Dict, Optional
import json


@dataclass
class _Response:
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
class _SyncRequest:
    body: str = ""
    headers: Optional[Dict[str, str]] = field(default_factory=dict)
    query: Optional[Dict[str, str]] = field(default_factory=dict)
    method: str = "GET"
    url: str = ""


@dataclass
class _AsyncRequest:
    _body: bytes = b""
    headers: Optional[Dict[str, str]] = field(default_factory=dict)
    query: Optional[Dict[str, str]] = field(default_factory=dict)
    method: str = "GET"
    url: str = ""

    async def body(self) -> bytes:
        return self._body

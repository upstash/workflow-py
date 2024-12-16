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

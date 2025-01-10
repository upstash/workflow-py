import json
from typing import Optional
from upstash_workflow.workflow_types import Request


async def get_payload(request: Request) -> Optional[str]:
    try:
        return json.dumps(await request.json())
    except Exception:
        return None

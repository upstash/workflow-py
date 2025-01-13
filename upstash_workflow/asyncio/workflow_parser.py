import json
from typing import Optional
from upstash_workflow.workflow_types import Request


async def get_payload(request: Request) -> Optional[str]:
    """
    Gets the request body. If that fails, returns None

    :param request: request received in the workflow api
    :return: request body
    """
    try:
        return json.dumps(await request.json())
    except Exception:
        return None

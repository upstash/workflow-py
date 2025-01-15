from typing import Optional
from upstash_workflow.workflow_types import AsyncRequest


async def get_payload(request: AsyncRequest) -> Optional[str]:
    """
    Gets the request body. If that fails, returns None

    :param request: request received in the workflow api
    :return: request body
    """
    try:
        return (await request.body()).decode()
    except Exception:
        return None

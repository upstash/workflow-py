from typing import Optional
from upstash_workflow.workflow_types import _AsyncRequest


async def _get_payload(request: _AsyncRequest) -> Optional[str]:
    """
    Gets the request body. If that fails, returns None

    :param request: request received in the workflow api
    :return: request body
    """
    try:
        return (await request.body()).decode()
    except Exception:
        return None

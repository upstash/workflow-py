from typing import Any, List, Optional
from qstash import QStash
from upstash_workflow.types import NotifyResponse, Waiter


class Client:
    """
    Workflow client for canceling & notifying workflows and getting waiters of an event.

    Example:
        ```python
        from upstash_workflow import Client

        client = Client(token="<QSTASH_TOKEN>")
        ```
    """

    def __init__(self, token: str, base_url: Optional[str] = None):
        """
        Initialize the Workflow client.

        :param token: QStash token
        :param base_url: Optional base URL for QStash API
        """
        kwargs = {"token": token}
        if base_url:
            kwargs["base_url"] = base_url
        self.client = QStash(**kwargs)

    def notify(
        self,
        event_id: str,
        event_data: Optional[Any] = None,
        workflow_run_id: Optional[str] = None,
    ) -> List[NotifyResponse]:
        """
        Notify a workflow run waiting for an event.

        Example:
            ```python
            from upstash_workflow import Client

            client = Client(token="<QSTASH_TOKEN>")
            await client.notify(
                event_id="my-event-id",
                event_data="my-data"  # data passed to the workflow run
            )
            ```

        Optionally, you can target a specific workflow run with lookback support:

            ```python
            await client.notify(
                event_id="my-event-id",
                event_data="my-data",
                workflow_run_id="wfr_123"  # target specific workflow run
            )
            ```

        When `workflow_run_id` is provided, the notify will have lookback capability,
        meaning it will work even if called before waitForEvent.

        :param event_id: event id to notify
        :param event_data: data to provide to the workflow
        :param workflow_run_id: optional workflow run id to target a specific workflow run
        :return: list of NotifyResponse objects
        """
        if workflow_run_id:
            path = f"/v2/notify/{workflow_run_id}/{event_id}"
        else:
            path = f"/v2/notify/{event_id}"

        import json

        body = event_data if isinstance(event_data, str) else json.dumps(event_data)

        result = self.client.http.request(
            path=path,
            method="POST",
            body=body,
            headers={"Content-Type": "application/json"},
            parse_response=True,
        )

        # Convert result to list of NotifyResponse objects
        if isinstance(result, list):
            return [
                NotifyResponse(
                    message_id=item["messageId"],
                    url=item["url"],
                    workflow_run_id=item["workflowRunId"],
                )
                for item in result
            ]
        return []

    def cancel(
        self,
        workflow_run_id: str,
    ) -> bool:
        """
        Cancel an ongoing workflow.

        Returns True if workflow is canceled successfully. Otherwise, throws error.

        Example:
            ```python
            await client.cancel(workflow_run_id="<WORKFLOW_RUN_ID>")
            ```

        :param workflow_run_id: run id of the workflow to cancel
        :return: True if workflow is successfully canceled
        """
        self.client.http.request(
            path=f"/v2/workflows/runs/{workflow_run_id}?cancel=true",
            method="DELETE",
            parse_response=False,
        )
        return True

    def get_waiters(self, event_id: str) -> List[Waiter]:
        """
        Check waiters of an event.

        Example:
            ```python
            from upstash_workflow import Client

            client = Client(token="<QSTASH_TOKEN>")
            result = await client.get_waiters(event_id="my-event-id")
            ```

        :param event_id: event id to check
        :return: list of Waiter objects
        """
        result = self.client.http.request(
            path=f"/v2/waiters/{event_id}",
            method="GET",
            parse_response=True,
        )

        if isinstance(result, list):
            return [
                Waiter(
                    workflow_run_id=item["workflowRunId"],
                    event_id=item["eventId"],
                    event_data=item.get("eventData"),
                    timeout=item.get("timeout"),
                )
                for item in result
            ]
        return []

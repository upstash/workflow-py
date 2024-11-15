import json
import os
from workflow.constants import DEFAULT_RETRIES
from workflow.context.auto_executor import AutoExecutor
from workflow.context.steps import LazyFunctionStep, LazySleepStep


class WorkflowContext:
    def __init__(
        self,
        qstash_client,
        workflow_run_id,
        headers,
        steps,
        url,
        initial_payload,
        raw_initial_payload,
        env,
        retries,
    ):
        self.qstash_client = qstash_client
        self.workflow_run_id = workflow_run_id
        self.steps = steps
        self.url = url
        self.headers = headers
        self.request_payload = initial_payload
        self.raw_initial_payload = raw_initial_payload or json.dumps(
            self.request_payload
        )
        self.env = env or os.environ.copy()
        self.retries = retries or DEFAULT_RETRIES
        self.executor = AutoExecutor(self, self.steps)

    async def run(self, step_name, step_function):
        return await self._add_step(LazyFunctionStep(step_name, step_function))

    async def sleep(self, step_name, duration):
        await self._add_step(LazySleepStep(step_name, duration))

    async def _add_step(self, step):
        return await self.executor.add_step(step)

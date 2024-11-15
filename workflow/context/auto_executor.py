import json
from workflow.constants import NO_CONCURRENCY
from workflow.error import QStashWorkflowError, QStashWorkflowAbort
from workflow.workflow_requests import get_headers


class AutoExecutor:
    def __init__(self, context, steps):
        self.context = context
        self.steps = steps
        self.non_plan_step_count = len([step for step in steps if not step.target_step])
        self.step_count = 0
        self.plan_step_count = 0
        self.executing_step = False

    async def add_step(self, step_info):
        return await self.run_single(step_info)

    async def run_single(self, lazy_step):
        if self.step_count < self.non_plan_step_count:
            step = self.steps[self.step_count + self.plan_step_count]
            validate_step(lazy_step, step)
            return step.out

        result_step = await lazy_step.get_result_step(NO_CONCURRENCY, self.step_count)
        await self.submit_steps_to_qstash([result_step])
        return result_step.out

    async def submit_steps_to_qstash(self, steps):
        if not steps:
            raise QStashWorkflowError(
                f"Unable to submit steps to QStash. Provided list is empty. Current step: {self.step_count}"
            )

        requests = []
        for single_step in steps:
            headers = get_headers(
                "false",
                self.context.workflow_run_id,
                self.context.url,
                self.context.headers,
                single_step,
                self.context.retries,
            )

            will_wait = (
                single_step.concurrent == NO_CONCURRENCY or single_step.step_id == 0
            )
            single_step.out = json.dumps(single_step.out)

            requests.append(
                {
                    "headers": headers["headers"],
                    "method": "POST",
                    "body": single_step,
                    "url": self.context.url,
                    "not_before": single_step.sleep_until if will_wait else None,
                    "delay": single_step.sleep_for if will_wait else None,
                }
            )

        await self.context.qstash_client.batch_json(requests)
        raise QStashWorkflowAbort(steps[0].step_name, steps[0])


def validate_step(lazy_step, step_from_request):
    if lazy_step.step_name != step_from_request.step_name:
        raise QStashWorkflowError(
            f"Incompatible step name. Expected '{lazy_step.step_name}', "
            f"got '{step_from_request.step_name}' from the request"
        )

    if lazy_step.step_type != step_from_request.step_type:
        raise QStashWorkflowError(
            f"Incompatible step type. Expected '{lazy_step.step_type}', "
            f"got '{step_from_request.step_type}' from the request"
        )

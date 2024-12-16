import json
from upstash_workflow.constants import NO_CONCURRENCY
from upstash_workflow.error import QStashWorkflowError, QStashWorkflowAbort
from upstash_workflow.workflow_requests import get_headers


class AutoExecutor:
    def __init__(self, context, steps):
        self.context = context
        self.steps = steps
        self.non_plan_step_count = len(
            [step for step in steps if not step.get("target_step", None)]
        )
        self.step_count = 0
        self.plan_step_count = 0
        self.executing_step = False

    async def add_step(self, step_info):
        self.step_count += 1
        return await self.run_single(step_info)

    async def run_single(self, lazy_step):
        if self.step_count < self.non_plan_step_count:
            step = self.steps[self.step_count + self.plan_step_count]
            validate_step(lazy_step, step)
            return step["out"]

        result_step = await lazy_step.get_result_step(NO_CONCURRENCY, self.step_count)
        await self.submit_steps_to_qstash([result_step])
        return result_step["out"]

    async def submit_steps_to_qstash(self, steps):
        if not steps:
            raise QStashWorkflowError(
                f"Unable to submit steps to QStash. Provided list is empty. Current step: {self.step_count}"
            )

        batch_requests = []
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

            batch_requests.append(
                {
                    "headers": headers["headers"],
                    "method": single_step.call_method,
                    "body": single_step.call_body,
                    "url": single_step.call_url,
                }
                if single_step.call_url
                else {
                    "headers": headers["headers"],
                    "method": "POST",
                    "body": {
                        "stepId": single_step.step_id,
                        "stepName": single_step.step_name,
                        "stepType": single_step.step_type,
                        "out": single_step.out,
                        "sleepFor": single_step.sleep_for,
                        "sleepUntil": single_step.sleep_until,
                        "concurrent": single_step.concurrent,
                        "targetStep": single_step.target_step,
                        "callUrl": single_step.call_url,
                        "callMethod": single_step.call_method,
                        "callBody": single_step.call_body,
                        "callHeaders": single_step.call_headers,
                    },
                    "url": self.context.url,
                    "notBefore": (single_step.sleep_until if will_wait else None),
                    "delay": single_step.sleep_for if will_wait else None,
                }
            )
        response = await self.context.qstash_client.message.batch_json(batch_requests)
        raise QStashWorkflowAbort(steps[0].step_name, steps[0])


def validate_step(lazy_step, step_from_request):
    if lazy_step.step_name != step_from_request["stepName"]:
        raise QStashWorkflowError(
            f"Incompatible step name. Expected '{lazy_step.step_name}', "
            f"got '{step_from_request["stepName"]}' from the request"
        )

    if lazy_step.step_type != step_from_request["stepType"]:
        raise QStashWorkflowError(
            f"Incompatible step type. Expected '{lazy_step.step_type}', "
            f"got '{step_from_request["stepType"]}' from the request"
        )

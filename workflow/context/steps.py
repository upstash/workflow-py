from abc import ABC, abstractmethod
import asyncio


class BaseLazyStep(ABC):
    def __init__(self, step_name):
        self.step_name = step_name
        self.step_type = None

    @abstractmethod
    def get_plan_step(self, concurrent, target_step):
        pass

    @abstractmethod
    async def get_result_step(self, concurrent, step_id):
        pass


class LazyFunctionStep(BaseLazyStep):
    def __init__(self, step_name, step_function):
        super().__init__(step_name)
        self.step_function = step_function
        self.step_type = "Run"

    def get_plan_step(self, concurrent, target_step):
        return {
            "stepId": 0,
            "stepName": self.step_name,
            "stepType": self.step_type,
            "concurrent": concurrent,
            "targetStep": target_step,
        }

    async def get_result_step(self, concurrent, step_id):
        result = self.step_function()
        if asyncio.iscoroutine(result):
            result = await result

        return {
            "stepId": step_id,
            "stepName": self.step_name,
            "stepType": self.step_type,
            "out": result,
            "concurrent": concurrent,
        }


class LazySleepStep(BaseLazyStep):
    def __init__(self, step_name, sleep):
        super().__init__(step_name)
        self.sleep = sleep
        self.step_type = "SleepFor"

    def get_plan_step(self, concurrent, target_step):
        return {
            "stepId": 0,
            "stepName": self.step_name,
            "stepType": self.step_type,
            "sleepFor": self.sleep,
            "concurrent": concurrent,
            "targetStep": target_step,
        }

    async def get_result_step(self, concurrent, step_id):
        return {
            "stepId": step_id,
            "stepName": self.step_name,
            "stepType": self.step_type,
            "sleepFor": self.sleep,
            "concurrent": concurrent,
        }

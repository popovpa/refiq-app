from collections.abc import Awaitable, Callable
from typing import Any

from fastapi import BackgroundTasks

JobFunc = Callable[..., Awaitable[None]]


class GenerationJobRunner:
    def submit(self, func: JobFunc, *args: Any) -> None:
        raise NotImplementedError


class BackgroundTaskRunner(GenerationJobRunner):
    def __init__(self, background_tasks: BackgroundTasks):
        self._tasks = background_tasks

    def submit(self, func: JobFunc, *args: Any) -> None:
        self._tasks.add_task(func, *args)


class DeferredJobRunner(GenerationJobRunner):
    """Test helper: queue jobs so callers can assert PROCESSING, then drain."""

    def __init__(self) -> None:
        self.jobs: list[tuple[JobFunc, tuple[Any, ...]]] = []

    def submit(self, func: JobFunc, *args: Any) -> None:
        self.jobs.append((func, args))

    async def run_all(self) -> None:
        while self.jobs:
            func, args = self.jobs.pop(0)
            await func(*args)


_test_runner: DeferredJobRunner | None = None


def set_job_runner(runner: DeferredJobRunner | None) -> None:
    global _test_runner
    _test_runner = runner


def has_test_job_runner() -> bool:
    return _test_runner is not None


def get_test_job_runner() -> DeferredJobRunner:
    if _test_runner is None:
        raise RuntimeError("Test job runner is not active")
    return _test_runner


def get_job_runner(background_tasks: BackgroundTasks | None = None) -> GenerationJobRunner:
    if _test_runner is not None:
        return _test_runner
    if background_tasks is None:
        raise RuntimeError("BackgroundTasks required for async generation")
    return BackgroundTaskRunner(background_tasks)

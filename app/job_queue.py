from __future__ import annotations

import threading
from concurrent.futures import CancelledError, Future
from dataclasses import dataclass
from queue import Empty, Queue
from typing import Callable

from app.job_runner import Job, JobProgress, JobResult, JobRunner
from app.structured_logging import StructuredLogger


@dataclass(frozen=True)
class _QueueItem:
    job: Job
    on_progress: Callable[[JobProgress], None] | None
    future: Future[JobResult]


class JobQueue:
    """Run jobs sequentially on a single worker thread."""

    def __init__(
        self,
        runner: JobRunner | None = None,
        logger: StructuredLogger | None = None,
        time_provider: Callable[[], float] | None = None,
    ) -> None:
        if runner and (logger or time_provider):
            raise ValueError("Provide either runner or logger/time_provider, not both")
        self._runner = runner or JobRunner(logger=logger, time_provider=time_provider)
        self._queue: Queue[_QueueItem | object] = Queue()
        self._shutdown = threading.Event()
        self._sentinel = object()
        self._lock = threading.Lock()
        self._items_by_future: dict[Future[JobResult], _QueueItem] = {}
        self._thread = threading.Thread(
            target=self._worker,
            name="job-queue",
            daemon=True,
        )
        self._thread.start()

    def submit(
        self,
        job: Job,
        on_progress: Callable[[JobProgress], None] | None = None,
    ) -> Future[JobResult]:
        if self._shutdown.is_set():
            raise RuntimeError("JobQueue is shut down")
        future: Future[JobResult] = Future()
        item = _QueueItem(job=job, on_progress=on_progress, future=future)
        with self._lock:
            self._items_by_future[future] = item
        self._queue.put(item)
        return future

    def cancel(self, future: Future[JobResult]) -> bool:
        with self._lock:
            item = self._items_by_future.get(future)
        if not item:
            return False
        item.job.cancel_token.cancel()
        future.cancel()
        return True

    def shutdown(self, wait: bool = True) -> None:
        if self._shutdown.is_set():
            if wait:
                self._thread.join()
            return
        self._shutdown.set()
        self._queue.put(self._sentinel)
        if wait:
            self._thread.join()

    def _worker(self) -> None:
        while True:
            try:
                item = self._queue.get(timeout=0.1)
            except Empty:
                if self._shutdown.is_set():
                    break
                continue

            if item is self._sentinel:
                break

            assert isinstance(item, _QueueItem)
            try:
                if not item.future.set_running_or_notify_cancel():
                    continue

                try:
                    result = self._runner.run(item.job, on_progress=item.on_progress)
                except CancelledError as exc:
                    item.future.set_exception(exc)
                except Exception as exc:  # noqa: BLE001
                    item.future.set_exception(exc)
                else:
                    item.future.set_result(result)
            finally:
                with self._lock:
                    self._items_by_future.pop(item.future, None)
                self._queue.task_done()

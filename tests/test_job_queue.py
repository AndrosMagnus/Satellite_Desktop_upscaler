from __future__ import annotations

import threading
import unittest

from app.job_queue import JobQueue
from app.job_runner import Job


class TestJobQueue(unittest.TestCase):
    def test_jobs_run_sequentially(self) -> None:
        queue = JobQueue()
        started = []
        finished = []
        lock = threading.Lock()
        first_release = threading.Event()
        second_started = threading.Event()

        def work_first(_: int) -> None:
            with lock:
                started.append("job-1")
            first_release.wait(timeout=2.0)
            with lock:
                finished.append("job-1")

        def work_second(_: int) -> None:
            with lock:
                started.append("job-2")
            second_started.set()
            with lock:
                finished.append("job-2")

        future_first = queue.submit(Job(job_id="job-1", total_units=1, work=work_first))
        future_second = queue.submit(Job(job_id="job-2", total_units=1, work=work_second))

        self.assertFalse(second_started.wait(timeout=0.2))
        self.assertEqual(started, ["job-1"])

        first_release.set()
        self.assertIsNotNone(future_first.result(timeout=2.0))
        self.assertIsNotNone(future_second.result(timeout=2.0))

        self.assertEqual(started, ["job-1", "job-2"])
        self.assertEqual(finished, ["job-1", "job-2"])

        queue.shutdown()

    def test_shutdown_prevents_new_jobs(self) -> None:
        queue = JobQueue()
        queue.shutdown()

        with self.assertRaises(RuntimeError):
            queue.submit(Job(job_id="job-3", total_units=1, work=lambda _: None))

    def test_job_failure_propagates(self) -> None:
        queue = JobQueue()

        def work(_: int) -> None:
            raise ValueError("boom")

        future = queue.submit(Job(job_id="job-4", total_units=1, work=work))

        with self.assertRaises(ValueError):
            future.result(timeout=2.0)

        queue.shutdown()

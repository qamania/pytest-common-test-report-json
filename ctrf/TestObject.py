from enum import Enum
from typing import Any

from pytest import TestReport


class TestStatus(Enum):
    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"
    PENDING = "pending"
    OTHER = "other"


class TestObject:
    name: str
    _status: TestStatus
    raw_status: str
    duration: float = 0
    start: float
    stop: float
    retries: int
    message: str

    worker_id: str
    file_path: str
    tags: list[str]
    browser: str
    trace: str

    def __init__(self, report: TestReport, worker_id: str or None = None):
        self.name = report.nodeid.split('[')[0]
        self._status = TestStatus.PENDING
        self._status = self.set_status(report)
        self.raw_status = None
        self.duration = 0
        self.start = 0
        self.stop = 0
        self.retries = 0
        self.message = None

        self.worker_id = worker_id
        self.file_path = report.location[0]
        self.tags = []
        self.browser = None
        self.trace = None

    @property
    def status(self) -> TestStatus:
        return self._status

    @status.setter
    def status(self, value: TestStatus) -> None:
        if self._status in (TestStatus.PENDING, TestStatus.PASSED):
            self._status = value
            return
        elif self._status in (TestStatus.SKIPPED, TestStatus.FAILED):
            return

    def set_status(self, report: TestReport) -> TestStatus:
        if self._status in (TestStatus.SKIPPED, TestStatus.FAILED):
            return self._status
        elif report.skipped:
            self._status = TestStatus.SKIPPED
        elif report.failed:
            self._status = TestStatus.FAILED
            self.raw_status = f"{report.when}_{report.outcome}"
            self.message = f"The test failed in the {report.when} phase"
            if hasattr(report, 'longreprtext'):
                if "AssertionError" in report.longreprtext:
                    self.message += " due to an assertion error"
                elif "Exception" in report.longreprtext:
                    self.message += " due to an exception"
        elif report.passed:
            self._status = TestStatus.PASSED
        else:
            self._status = TestStatus.OTHER
        return self._status

    def update(self, report: TestReport) -> None:
        self.set_status(report)
        self.duration += 1000 * report.duration  # pytest reports duration in seconds, CTRF requires milliseconds
        if report.when == "setup" and self.start == 0:
            self.start = report.start
        if report.when == "teardown" and self.stop == 0:
            self.stop = report.stop
        if report.longrepr and len(report.longreprtext) > 0:
            self.trace = report.longreprtext
        if hasattr(report, '_ctrf_metadata'):
            self.tags = report._ctrf_metadata.get('tags')
            self.browser = report._ctrf_metadata.get('browser')

    def serialize(self) -> dict:
        result: dict[str, Any] = {
            'name': self.name,
            'status': self._status.value,
            'raw_status': self.raw_status,
            'duration': self.duration,
            'start': self.start,
            'stop': self.stop,
            'retries': None if self.retries == 1 else self.retries,
            'file_path': self.file_path,
            'tags': self.tags,
            'browser': self.browser,
            'trace': self.trace,
            'message': self.message
        }
        if self.worker_id:
            result['extra'] = {'worker': self.worker_id}
        return {key: value for key, value in result.items() if value not in [None, '', []]}

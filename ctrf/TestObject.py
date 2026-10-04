from enum import Enum
from typing import Any, Optional, List, Dict

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
    raw_status: Optional[str]
    start: int
    stop: int
    retries: int
    message: Optional[str]

    worker_id: Optional[str]
    file_path: str
    suite: List[str]
    tags: List[str]
    browser: Optional[str]
    parameters: Optional[Dict[str, Any]]
    trace: Optional[str]
    retry_attempts: List[Dict[str, Any]]

    def __init__(self, report: TestReport, worker_id: Optional[str] = None):
        self.name = report.nodeid
        self.worker_id = worker_id
        self.file_path = report.location[0]
        self.suite = self._suite(report.nodeid)
        self.tags: List[str] = []
        self.browser = None
        self.parameters = None
        self.retry_attempts = []
        self._reset_attempt()

    def _reset_attempt(self) -> None:
        self._status = TestStatus.PENDING
        self.raw_status = None
        self.message = None
        self.trace = None
        self.start = 0
        self.stop = 0
        self._setup_seen = False

    @staticmethod
    def _suite(nodeid: str) -> List[str]:
        # "dir/test_file.py::TestClass::test_name[param]" -> ["dir/test_file.py", "TestClass"]
        # parameters are cut off first, they may contain "::"
        return nodeid.split('[', 1)[0].split('::')[:-1]

    @property
    def status(self) -> TestStatus:
        return self._status

    @property
    def retries(self) -> int:
        return len(self.retry_attempts)

    @property
    def flaky(self) -> bool:
        return self._status == TestStatus.PASSED and any(
            attempt['status'] == TestStatus.FAILED.value for attempt in self.retry_attempts)

    def _finish_attempt(self) -> None:
        attempt = {
            'attempt': len(self.retry_attempts) + 1,
            'status': self._status.value,
            'duration': max(self.stop - self.start, 0),
            'start': self.start,
            'stop': self.stop,
            'message': self.message,
            'trace': self.trace,
        }
        self.retry_attempts.append({key: value for key, value in attempt.items() if value is not None})
        self._reset_attempt()

    def set_status(self, report: TestReport) -> TestStatus:
        # the first non-passed outcome wins; message and trace are taken from that same report
        if self._status in (TestStatus.SKIPPED, TestStatus.FAILED, TestStatus.OTHER):
            return self._status
        elif report.skipped:
            self._status = TestStatus.SKIPPED
            if hasattr(report, 'wasxfail'):
                self.raw_status = 'xfailed'
                self.message = report.wasxfail or None
                self.trace = report.longreprtext or None
            else:
                self.message = self._skip_reason(report)
        elif report.failed or report.outcome == 'rerun':
            # "rerun" is a failed attempt that pytest-rerunfailures will run again
            self._status = TestStatus.FAILED
            self.raw_status = f"{report.when}_{report.outcome}"
            self.message = self._failure_message(report)
            self.trace = report.longreprtext or None
        elif report.passed:
            self._status = TestStatus.PASSED
        else:
            self._status = TestStatus.OTHER
        return self._status

    @staticmethod
    def _failure_message(report: TestReport) -> Optional[str]:
        # same text pytest shows in the short test summary, e.g. "AssertionError: assert 1 == 2"
        crash = getattr(report.longrepr, 'reprcrash', None)
        if crash is not None and crash.message:
            return crash.message
        # plain-text longrepr (some plugins, xdist worker crashes): the last line is usually the error
        lines = [line for line in report.longreprtext.splitlines() if line.strip()]
        return lines[-1].strip() if lines else None

    @staticmethod
    def _skip_reason(report: TestReport) -> Optional[str]:
        # for skips pytest stores longrepr as a (path, lineno, reason) tuple
        if isinstance(report.longrepr, tuple) and len(report.longrepr) == 3:
            reason = str(report.longrepr[2])
            if reason.startswith('Skipped: '):
                reason = reason[len('Skipped: '):]
            return reason or None
        return report.longreprtext or None

    def update(self, report: TestReport) -> None:
        if report.when == "setup":
            # every attempt starts with setup, a second one means the test is being rerun
            if self._setup_seen:
                self._finish_attempt()
            self._setup_seen = True
            self.start = int(report.start * 1000)
        self.set_status(report)
        if report.when == "teardown":
            self.stop = int(report.stop * 1000)
        if hasattr(report, '_ctrf_metadata'):
            self.tags = report._ctrf_metadata.get('tags')
            self.browser = report._ctrf_metadata.get('browser')
            self.parameters = report._ctrf_metadata.get('parameters')

    def serialize(self, test_type: Optional[str] = None) -> dict:
        result: Dict[str, Any] = {
            'name': self.name,
            'status': self._status.value,
            'rawStatus': self.raw_status,
            'duration': self.stop - self.start,
            'start': self.start,
            'stop': self.stop,
            'suite': self.suite,
            'type': test_type,
            'retries': self.retries,
            'retryAttempts': self.retry_attempts,
            'flaky': True if self.flaky else None,
            'filePath': self.file_path,
            'tags': self.tags,
            'browser': self.browser,
            'parameters': self.parameters,
            'trace': self.trace,
            'message': self.message
        }
        if self.worker_id:
            result['extra'] = {'worker': self.worker_id}
        return {key: value for key, value in result.items() if value not in [None, '', []]}

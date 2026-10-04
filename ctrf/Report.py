import os
import platform
import sys
import pytest
import time
import json
import warnings
from uuid import uuid4
from datetime import datetime, timezone
from pytest import TestReport
from collections import OrderedDict
from .TestObject import TestObject, TestStatus


class Report:
    def __init__(self):
        self.test_items = OrderedDict()
        self.start_time = None
        self.stop_time = None

    def start(self) -> None:
        self.start_time = int(time.time() * 1000)

    def stop(self) -> None:
        self.stop_time = int(time.time() * 1000)

    @staticmethod
    def _get_tool() -> dict:
        return {
            "name": "pytest",
            "version": str(pytest.__version__)
        }

    def list_tests_by_status(self, status: TestStatus) -> list:
        return [test for test in self.test_items.values() if test.status == status]

    def _get_summary(self) -> dict:
        tests = list(self.test_items.values())
        summary = {
            'tests': len(tests),
            'passed': len(self.list_tests_by_status(TestStatus.PASSED)),
            'failed': len(self.list_tests_by_status(TestStatus.FAILED)),
            'skipped': len(self.list_tests_by_status(TestStatus.SKIPPED)),
            'pending': len(self.list_tests_by_status(TestStatus.PENDING)),
            'other': len(self.list_tests_by_status(TestStatus.OTHER)),
            'flaky': len([test for test in tests if test.flaky]),
            # a suite is a file or class that directly contains tests
            'suites': len({tuple(test.suite) for test in tests if test.suite}),
            'start': self.start_time,
            'stop': self.stop_time,
        }
        if self.start_time is not None and self.stop_time is not None:
            summary['duration'] = self.stop_time - self.start_time
        return summary

    @staticmethod
    def _get_environment() -> dict:
        env = {
            "osPlatform": sys.platform,
            "osRelease": platform.release(),
            "osVersion": platform.version(),
        }
        for field, variable in (("buildName", "CTRF_BUILD_NAME"),
                                ("buildUrl", "CTRF_BUILD_URL"),
                                ("testEnvironment", "CTRF_TEST_ENVIRONMENT")):
            value = os.getenv(variable)
            if value:
                env[field] = value
        raw = os.getenv("CTRF_BUILD_NUMBER")
        if raw:
            try:
                env["buildNumber"] = int(raw)
            except ValueError:
                warnings.warn(f"CTRF_BUILD_NUMBER={raw!r} is not an integer; buildNumber omitted from the report")
        return env

    def collect(self, report: TestReport) -> None:
        if report.nodeid not in self.test_items.keys():
            worker_id = getattr(report, 'worker_id', None)
            test = TestObject(report, worker_id)
        else:
            test = self.test_items.get(report.nodeid)  # type: ignore
        test.update(report)
        self.test_items[report.nodeid] = test

    def get_report(self) -> dict:
        test_type = os.getenv("CTRF_TEST_TYPE") or None
        return {
            'reportFormat': 'CTRF',
            'specVersion': '1.0.0',
            'reportId': str(uuid4()),
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'generatedBy': 'pytest',
            'results': {
                "tool": self._get_tool(),
                "summary": self._get_summary(),
                "environment": self._get_environment(),
                "tests": [test.serialize(test_type) for test in self.test_items.values()]
            }
        }

    def save(self, report_file: str) -> None:
        dirname = os.path.dirname(report_file)
        if dirname:
            os.makedirs(dirname, exist_ok=True)
        with open(report_file, 'w') as file:
            json.dump(self.get_report(), file, default=str, indent=4)

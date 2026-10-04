import json
import os
import sys
import warnings
from pathlib import Path

import pytest
from pytest import Pytester, fixture

from ctrf.Report import Report

pytest_plugins = ["pytester", "xdist", "ctrf"]
test_file = "tests/test_example.py"
basic_test_args = ["-k", "test_example"]


@fixture
def ctrf_report_sync(pytester: Pytester):
    pytester.copy_example(test_file)
    pytester.runpytest(*[*basic_test_args, "--ctrf", "report.json"])
    with open(pytester.path / "report.json") as file:
        yield json.load(file)


@fixture
def ctrf_report_xdist(pytester: Pytester):
    pytester.copy_example(test_file)
    pytester.runpytest(*[*basic_test_args, "--ctrf", "report.json", "-n", "3"])
    with open(pytester.path / "report.json") as file:
        yield json.load(file)


def test_without_plugin_no_xdist(pytester: Pytester):
    pytester.copy_example(test_file)
    result = pytester.runpytest(*basic_test_args)
    result.assert_outcomes(passed=15, skipped=1, failed=3, errors=2)


def test_without_plugin_with_xdist(pytester: Pytester):
    pytester.copy_example(test_file)
    result = pytester.runpytest(*[*basic_test_args, "-n", "3"])
    result.assert_outcomes(passed=15, skipped=1, failed=3, errors=2)
    assert "created: 3/3 workers" in result.stdout.str()


def test_with_markers(pytester: Pytester):
    pytester.copy_example(test_file)
    args = [*basic_test_args, "--ctrf", "report.json", "-m smoke"]
    pytester.runpytest(*args)
    with open(pytester.path / "report.json") as file:
        report = json.load(file)
    assert report["results"]["summary"]["tests"] == 1
    assert report["results"]["summary"]["passed"] == 1
    assert report["results"]["summary"]["failed"] == 0
    assert report["results"]["summary"]["skipped"] == 0


def test_with_plugin_no_xdist(ctrf_report_sync):
    assert ctrf_report_sync["results"]["summary"]["tests"] == 20
    assert ctrf_report_sync["results"]["summary"]["passed"] == 14
    assert ctrf_report_sync["results"]["summary"]["failed"] == 5
    assert ctrf_report_sync["results"]["summary"]["skipped"] == 1


def test_with_plugin_failed_details(ctrf_report_sync):
    call_failed = [t for t in ctrf_report_sync["results"]["tests"] if t.get("rawStatus") == "call_failed"]
    assert call_failed
    for test in call_failed:
        assert test["status"] == "failed"
        assert test.get('trace') is not None
        assert test.get("message") is not None


def test_any_test_has_timestamps(ctrf_report_sync):
    for test in ctrf_report_sync["results"]["tests"]:
        assert test.get("start") is not None
        assert test.get("stop") is not None
        assert test.get("duration") is not None


def test_with_plugin_with_xdist(ctrf_report_xdist):
    assert ctrf_report_xdist["results"]["summary"]["tests"] == 20
    assert ctrf_report_xdist["results"]["summary"]["passed"] == 14
    assert ctrf_report_xdist["results"]["summary"]["failed"] == 5
    assert ctrf_report_xdist["results"]["summary"]["skipped"] == 1


def test_with_plugin_failed_details_xdist(ctrf_report_xdist):
    call_failed = [t for t in ctrf_report_xdist["results"]["tests"] if t.get("rawStatus") == "call_failed"]
    assert call_failed
    for test in call_failed:
        assert test["status"] == "failed"
        assert test.get('trace') is not None
        assert test.get("message") is not None


def test_any_test_has_timestamps_xdist(ctrf_report_xdist):
    for test in ctrf_report_xdist["results"]["tests"]:
        assert test.get("start") is not None
        assert test.get("stop") is not None
        assert test.get("duration") is not None

def test_parametrize_marker_not_in_tags(pytester: Pytester):
    pytester.makepyfile("""
        import pytest

        @pytest.mark.parametrize('param', [{'key': 'value', 'data': 'x' * 1000}, {'key': 'other', 'data': 'y' * 1000}], ids=['case1', 'case2'])
        def test_parametrized(param):
            assert True
    """)
    pytester.runpytest("--ctrf", "report.json")
    with open(pytester.path / "report.json") as file:
        report = json.load(file)
    for test in report["results"]["tests"]:
        tags = test.get("tags", [])
        assert all("parametrize" not in tag for tag in tags), (
            f"parametrize marker should not appear in tags, but got: {tags}"
        )


PARAMETRIZED_TESTS = """
    import pytest

    class Obj:
        def __repr__(self):
            return 'Obj()'

    @pytest.mark.parametrize('n', [1, 2])
    def test_numbers(n):
        assert True

    @pytest.mark.parametrize('obj, text', [(Obj(), 'z' * 500)], ids=['complex'])
    def test_complex(obj, text):
        assert True
"""


def _parametrized_report(pytester: Pytester, *args) -> dict:
    pytester.makepyfile(test_params=PARAMETRIZED_TESTS)
    pytester.runpytest("--ctrf", "report.json", *args)
    with open(pytester.path / "report.json") as file:
        report = json.load(file)
    return {test["name"]: test for test in report["results"]["tests"]}


def _check_parametrized_tests(tests: dict):
    assert set(tests) == {
        "test_params.py::test_numbers[1]",
        "test_params.py::test_numbers[2]",
        "test_params.py::test_complex[complex]",
    }
    assert tests["test_params.py::test_numbers[1]"]["parameters"] == {"n": 1}
    assert tests["test_params.py::test_numbers[2]"]["parameters"] == {"n": 2}
    complex_params = tests["test_params.py::test_complex[complex]"]["parameters"]
    assert complex_params["obj"] == "Obj()"
    assert complex_params["text"] == "z" * 200 + "..."


def test_parametrized_tests_have_unique_names_and_parameters(pytester: Pytester):
    _check_parametrized_tests(_parametrized_report(pytester))


def test_parametrized_tests_have_unique_names_and_parameters_xdist(pytester: Pytester):
    _check_parametrized_tests(_parametrized_report(pytester, "-n", "2"))


MESSAGE_TESTS = """
    import pytest

    @pytest.fixture
    def broken_setup():
        raise RuntimeError("db is down")

    @pytest.fixture
    def broken_teardown():
        yield
        raise RuntimeError("cleanup failed")

    def test_assert():
        x = "Exception handling"
        assert x == "y"

    def test_raise():
        raise ValueError("bad value")

    def test_setup_error(broken_setup):
        pass

    def test_call_and_teardown_fail(broken_teardown):
        assert 1 == 2

    def test_fail():
        pytest.fail("explicit failure", pytrace=False)

    @pytest.mark.skip(reason="nope")
    def test_skip_marker():
        pass

    def test_skip_inside():
        pytest.skip("not today")

    @pytest.mark.xfail(reason="known bug")
    def test_xfail():
        assert 0
"""


def _messages_report(pytester: Pytester, *args) -> dict:
    pytester.makepyfile(test_messages=MESSAGE_TESTS)
    pytester.runpytest("--ctrf", "report.json", *args)
    with open(pytester.path / "report.json") as file:
        report = json.load(file)
    return {test["name"].split("::")[-1]: test for test in report["results"]["tests"]}


def _check_messages(tests: dict):
    assert tests["test_assert"]["message"].startswith("AssertionError: assert 'Exception handling' == 'y'")
    assert tests["test_raise"]["message"] == "ValueError: bad value"
    assert tests["test_fail"]["message"] == "Failed: explicit failure"
    for name in ("test_assert", "test_raise", "test_fail"):
        assert tests[name]["rawStatus"] == "call_failed"
        assert "trace" in tests[name]

    setup_error = tests["test_setup_error"]
    assert setup_error["status"] == "failed"
    assert setup_error["rawStatus"] == "setup_failed"
    assert setup_error["message"] == "RuntimeError: db is down"
    assert "db is down" in setup_error["trace"]

    # the call failure is reported, and trace belongs to the same failure as message
    both = tests["test_call_and_teardown_fail"]
    assert both["rawStatus"] == "call_failed"
    assert both["message"].startswith("assert 1 == 2")
    assert "cleanup failed" not in both["trace"]

    assert tests["test_skip_marker"]["message"] == "nope"
    assert tests["test_skip_inside"]["message"] == "not today"
    for name in ("test_skip_marker", "test_skip_inside"):
        assert tests[name]["status"] == "skipped"
        assert "trace" not in tests[name]
        assert "rawStatus" not in tests[name]

    xfail = tests["test_xfail"]
    assert xfail["status"] == "skipped"
    assert xfail["rawStatus"] == "xfailed"
    assert xfail["message"] == "known bug"


def test_failure_and_skip_messages(pytester: Pytester):
    _check_messages(_messages_report(pytester))


def test_failure_and_skip_messages_xdist(pytester: Pytester):
    _check_messages(_messages_report(pytester, "-n", "2"))


RERUN_TESTS = """
    import pytest
    calls = {}

    def bump(name):
        calls[name] = calls.get(name, 0) + 1
        return calls[name]

    @pytest.mark.flaky(reruns=2)
    def test_flaky_call():
        assert bump("call") >= 3, "fails twice"

    @pytest.mark.flaky(reruns=1)
    def test_always_fails():
        assert False, "always"

    @pytest.fixture
    def flaky_setup():
        if bump("setup") < 2:
            raise RuntimeError("setup glitch")

    @pytest.mark.flaky(reruns=1)
    def test_flaky_setup(flaky_setup):
        pass

    def test_stable():
        pass
"""


def _rerun_report(pytester: Pytester, *args) -> dict:
    pytester.makepyfile(test_reruns=RERUN_TESTS)
    pytester.runpytest("--ctrf", "report.json", *args)
    with open(pytester.path / "report.json") as file:
        return json.load(file)


def _check_reruns(report: dict):
    tests = {test["name"].split("::")[-1]: test for test in report["results"]["tests"]}

    flaky_call = tests["test_flaky_call"]
    assert flaky_call["status"] == "passed"
    assert flaky_call["retries"] == 2
    assert flaky_call["flaky"] is True
    assert [a["attempt"] for a in flaky_call["retryAttempts"]] == [1, 2]
    assert all(a["status"] == "failed" for a in flaky_call["retryAttempts"])
    assert flaky_call["retryAttempts"][0]["message"].startswith("AssertionError: fails twice")
    # the final, passed attempt carries no trace from the failed ones
    assert "trace" not in flaky_call and "message" not in flaky_call

    always = tests["test_always_fails"]
    assert always["status"] == "failed"
    assert always["retries"] == 1
    assert "flaky" not in always
    assert always["message"].startswith("AssertionError: always")

    flaky_setup = tests["test_flaky_setup"]
    assert flaky_setup["flaky"] is True
    assert flaky_setup["retries"] == 1
    assert flaky_setup["retryAttempts"][0]["status"] == "failed"
    assert flaky_setup["retryAttempts"][0]["message"] == "RuntimeError: setup glitch"

    stable = tests["test_stable"]
    assert stable["retries"] == 0
    assert "retryAttempts" not in stable and "flaky" not in stable

    assert report["results"]["summary"]["flaky"] == 2
    assert report["results"]["summary"]["passed"] == 3
    assert report["results"]["summary"]["failed"] == 1


def test_reruns(pytester: Pytester):
    _check_reruns(_rerun_report(pytester))


def test_reruns_xdist(pytester: Pytester):
    _check_reruns(_rerun_report(pytester, "-n", "2"))


def test_suite_hierarchy(pytester: Pytester):
    pytester.makepyfile(test_suites="""
        import pytest

        def test_top():
            pass

        class TestOuter:
            def test_a(self):
                pass

            class TestInner:
                @pytest.mark.parametrize('v', ['a::b'])
                def test_b(self, v):
                    pass
    """)
    pytester.runpytest("--ctrf", "report.json")
    with open(pytester.path / "report.json") as file:
        report = json.load(file)
    suites = {test["name"]: test["suite"] for test in report["results"]["tests"]}
    assert suites == {
        "test_suites.py::test_top": ["test_suites.py"],
        "test_suites.py::TestOuter::test_a": ["test_suites.py", "TestOuter"],
        "test_suites.py::TestOuter::TestInner::test_b[a::b]": ["test_suites.py", "TestOuter", "TestInner"],
    }
    assert report["results"]["summary"]["suites"] == 3


def test_summary_counts_other_status(pytester: Pytester):
    # a plugin may report an outcome pytest itself does not have; it must be counted as "other"
    pytester.makeconftest("""
        import pytest

        @pytest.hookimpl(hookwrapper=True)
        def pytest_runtest_makereport(item, call):
            report = (yield).get_result()
            if item.name == "test_weird" and report.when == "call":
                report.outcome = "weird"
    """)
    pytester.makepyfile(test_other="""
        def test_weird():
            pass

        def test_normal():
            pass
    """)
    pytester.runpytest("--ctrf", "report.json")
    with open(pytester.path / "report.json") as file:
        summary = json.load(file)["results"]["summary"]
    assert summary["other"] == 1
    assert summary["passed"] == 1
    assert summary["tests"] == summary["passed"] + summary["failed"] + summary["skipped"] \
        + summary["pending"] + summary["other"]
    assert summary["duration"] == summary["stop"] - summary["start"]


def test_type_from_env(pytester: Pytester, monkeypatch):
    pytester.makepyfile(test_typed="def test_x(): pass")
    monkeypatch.setenv("CTRF_TEST_TYPE", "e2e")
    pytester.runpytest("--ctrf", "with_type.json")
    monkeypatch.delenv("CTRF_TEST_TYPE")
    pytester.runpytest("--ctrf", "without_type.json")
    with open(pytester.path / "with_type.json") as file:
        assert json.load(file)["results"]["tests"][0]["type"] == "e2e"
    with open(pytester.path / "without_type.json") as file:
        assert "type" not in json.load(file)["results"]["tests"][0]


ENV_VARIABLES = ("CTRF_BUILD_NAME", "CTRF_BUILD_URL", "CTRF_TEST_ENVIRONMENT", "CTRF_BUILD_NUMBER")


@fixture
def clean_env(monkeypatch):
    for variable in ENV_VARIABLES:
        monkeypatch.delenv(variable, raising=False)
    return monkeypatch


def test_environment_without_variables_has_only_detected_fields(clean_env):
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        env = Report._get_environment()
    assert env == {
        "osPlatform": sys.platform,
        "osRelease": env["osRelease"],
        "osVersion": env["osVersion"],
    }
    assert env["osRelease"] and env["osVersion"]


def test_environment_from_variables(clean_env):
    clean_env.setenv("CTRF_BUILD_NAME", "Nightly")
    clean_env.setenv("CTRF_BUILD_URL", "https://ci.example/1")
    clean_env.setenv("CTRF_TEST_ENVIRONMENT", "staging")
    clean_env.setenv("CTRF_BUILD_NUMBER", "42")
    env = Report._get_environment()
    assert env["buildName"] == "Nightly"
    assert env["buildUrl"] == "https://ci.example/1"
    assert env["testEnvironment"] == "staging"
    assert env["buildNumber"] == 42


def test_environment_empty_variable_is_omitted(clean_env):
    clean_env.setenv("CTRF_BUILD_NAME", "")
    clean_env.setenv("CTRF_BUILD_NUMBER", "")
    env = Report._get_environment()
    assert "buildName" not in env
    assert "buildNumber" not in env


@pytest.mark.parametrize("value", ["abc", "1.5", "12a"])
def test_environment_invalid_build_number_warns_and_is_omitted(clean_env, value):
    clean_env.setenv("CTRF_BUILD_NUMBER", value)
    with pytest.warns(UserWarning, match="CTRF_BUILD_NUMBER"):
        env = Report._get_environment()
    assert "buildNumber" not in env


def test_browser_name_from_parameters(pytester: Pytester):
    # pytest-playwright parametrizes tests with browser_name
    pytester.makepyfile(test_browser="""
        import pytest

        @pytest.mark.parametrize('browser_name', ['chromium'])
        def test_page(browser_name):
            pass
    """)
    pytester.runpytest("--ctrf", "report.json")
    with open(pytester.path / "report.json") as file:
        test = json.load(file)["results"]["tests"][0]
    assert test["browser"] == "chromium"
    assert test["parameters"] == {"browser_name": "chromium"}


def test_plain_text_failure_uses_last_line_as_message(pytester: Pytester):
    # some plugins and xdist worker crashes report the failure as plain text, without crash info
    pytester.makeconftest("""
        import pytest

        @pytest.hookimpl(hookwrapper=True)
        def pytest_runtest_makereport(item, call):
            report = (yield).get_result()
            if report.when == "call" and report.failed:
                report.longrepr = "worker log\\nRuntimeError: worker crashed\\n\\n"
    """)
    pytester.makepyfile(test_plain="def test_x(): assert False")
    pytester.runpytest("--ctrf", "report.json")
    with open(pytester.path / "report.json") as file:
        test = json.load(file)["results"]["tests"][0]
    assert test["status"] == "failed"
    assert test["message"] == "RuntimeError: worker crashed"


def test_no_report_without_option(pytester: Pytester):
    pytester.makepyfile(test_plain="def test_x(): pass")
    pytester.runpytest()
    assert not list(pytester.path.glob("*.json"))


PROJECT_ROOT = Path(__file__).parent.parent


def _schema_path() -> Path:
    configured = os.getenv("CTRF_SCHEMA")
    if configured:
        # set in CI: a missing file there is an error, not a reason to skip.
        # relative to the project root, pytester runs each test in a temporary directory
        path = PROJECT_ROOT / configured
        assert path.is_file(), f"CTRF_SCHEMA={configured} does not exist"
        return path
    local = PROJECT_ROOT / "schema_validator" / "ctrf.schema.json"
    if not local.is_file():
        pytest.skip("CTRF schema not found: set CTRF_SCHEMA or put it into schema_validator/ctrf.schema.json")
    return local


@pytest.mark.parametrize("args", [[], ["-n", "2"]], ids=["no_xdist", "xdist"])
def test_report_with_all_features_matches_schema(pytester: Pytester, args):
    jsonschema = pytest.importorskip("jsonschema")
    with open(_schema_path(), encoding="utf-8") as file:
        schema = json.load(file)
    pytester.makepyfile(test_params=PARAMETRIZED_TESTS, test_messages=MESSAGE_TESTS, test_reruns=RERUN_TESTS)
    pytester.runpytest("--ctrf", "report.json", *args)
    with open(pytester.path / "report.json") as file:
        report = json.load(file)
    validator_cls = jsonschema.validators.validator_for(schema, default=jsonschema.Draft7Validator)
    errors = ["/".join(map(str, e.absolute_path)) + ": " + e.message
              for e in validator_cls(schema).iter_errors(report)]
    assert not errors, "\n".join(errors)
    # make sure the rich fields were really produced, otherwise the check proves little
    tests = report["results"]["tests"]
    assert any("retryAttempts" in t for t in tests)
    assert any("parameters" in t for t in tests)
    assert any(t.get("rawStatus") == "xfailed" for t in tests)
    assert any(t.get("rawStatus") == "setup_failed" for t in tests)


def test_not_parametrized_test_has_no_parameters(ctrf_report_sync):
    for test in ctrf_report_sync["results"]["tests"]:
        if "[" not in test["name"]:
            assert "parameters" not in test
# CTRF for pytest

Pytest implementation of Common Test Report Format (CTRF) for test results.  
Test report will be generated in JSON format.  
Test report can be used to prettify the report in GitHub Actions with [github-actions-ctrf](https://github.com/ctrf-io/github-actions-ctrf).  
Do not worry if report in GitHub does not appear immediately. It takes some time to process the report. 

## Features
- Generates JSON report
- Tested to work correctly with and without [pytest-xdist](https://pypi.org/project/pytest-xdist/)
- Tested to get browser name from [pytest-playwright](https://pypi.org/project/pytest-playwright/)
- Reruns from [pytest-rerunfailures](https://pypi.org/project/pytest-rerunfailures/) are reported as `retries`, `retryAttempts` and `flaky`
- Each test gets a `suite` hierarchy: file, then classes
- Parametrized tests are supported: each case is reported as a separate test named by its full pytest node id (e.g. `test_file.py::test_param[1]`), with its values in `parameters`

## Installation

```bash
pip install pytest-json-ctrf
```

## Usage

generate report.json file in the root directory of the project. File path is mandatory

```bash
pytest --ctrf report.json
```
Environment Variables may be used to specify the required Environment Object
fields when using the CTRF [slack-test-reporter][ctrf-slack-test-reporter-url].
All of them are optional: a variable that is not set is left out of the report, see [.env.example](./.env.example).

```bash
CTRF_BUILD_NAME="Pytest JSON CTRF Report"
CTRF_BUILD_NUMBER=123
CTRF_BUILD_URL="https://ctrf.io"
CTRF_TEST_ENVIRONMENT="staging"
CTRF_TEST_TYPE="e2e"
```

`CTRF_BUILD_NUMBER` must be an integer. Otherwise a warning is issued and `buildNumber` is omitted from the report.  
`osPlatform`, `osRelease` and `osVersion` are detected automatically.  
`CTRF_TEST_TYPE` is written to every test's `type` field.

## JSON example

More info here: https://ctrf.io/docs/schema/examples

```json
{
  "reportFormat": "CTRF",
  "specVersion": "1.0.0",
  "generatedBy": "pytest",
  "results": {
    "tool": {
      "name": "pytest",
      "version": "9.0.3"
    },
    "summary": {
      "tests": 3,
      "passed": 1,
      "failed": 1,
      "pending": 0,
      "skipped": 1,
      "other": 0,
      "start": 1706644023,
      "stop": 1706644043
    },
    "environment": {
        "buildName": "Pytest JSON CTRF Report",
        "buildUrl": "https://ctrf.io",
        "osPlatform": "linux",
        "osRelease": "6.8.0-45-generic",
        "osVersion": "#45-Ubuntu SMP PREEMPT_DYNAMIC",
        "testEnvironment": "staging",
        "buildNumber": 123
    },
    "tests": [
      {
        "name": "User should be able to login",
        "status": "passed",
        "duration": 1200
      },
      {
        "name": "User profile information should be correct",
        "status": "failed",
        "duration": 800
      },
      {
        "name": "User should be able to logout",
        "status": "skipped",
        "duration": 0
      }
    ]
  }
}
```

## Report Example
![Example Image](./assets/report_example.png)

## Technical details
For future me and others who are interested in the technical details of the implementation.  
The main idea is to handle xdist plugin because without it collecting report is quite straightforward.  
By the example of putest-json-report plugin, I have learned that different plugins can be registered for the controller and workers node.  
The `pytest_runtest_logreport` hook in the controller node is used to collect the test results from all the nodes so other nodes can just add some details to the `TestReport` object.

## Credits

- https://ctrf.io/ -> nice data format
- https://github.com/numirias/pytest-json-report -> Source of inspiration and dealing with xdist sync
- https://github.com/testomatio/pytestomatio -> Source of inspiration for creating pytest plugins
- https://github.com/infopulse/Playwright-course-python -> The report will be used in the demo project as +1 report option

## Changelog
- 0.6.1 - proper license added to the package to fix build pipeline warnings
- 0.6.0 - fixed issue 12 - report now validates against the CTRF schema. Thanks to [@jamesarosen](https://github.com/jamesarosen) for the detailed report!
  - `filePath`, `rawStatus` and integer `buildNumber`; environment fields are added only when their variables are set (no defaults), plus `osPlatform`, `osRelease`, `osVersion` and `type` (`CTRF_TEST_TYPE`)
  - parametrized tests are named by the full node id and get `parameters`
  - `message` is the real failure message; skip and xfail reasons are reported in `message`
  - reruns (pytest-rerunfailures) are reported as `retries`, `retryAttempts` and `flaky`
  - new `suite` field and summary `other`, `flaky`, `suites`, `duration`
  - CI validates reports against the CTRF schema
- 0.5.3 - fixed issue 6 - @pytest.mark.parametrize will no longer be added to tags to prevent exhausting memory
- 0.5.1 - added mandatory root object fields: reportFormat, specVersion, generatedBy
- 0.5.0 - Changed logic of handling parametrized tests. Previously they were marked as retries, now they are reported as separate tests
- 0.4.1 - Introduced backward compatibility with python 3.8, fixed issues with the time formats

### Roadmap
- Add screenshots handling
- Add hooks for the report extension
- [ctrf-slack-test-reporter-url]: https://github.com/ctrf-io/slack-test-reporter
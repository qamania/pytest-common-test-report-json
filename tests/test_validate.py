import json
import subprocess
import sys
from pathlib import Path

import pytest

pytest.importorskip("jsonschema")

VALIDATOR = Path(__file__).parent.parent / "schema_validator" / "validate.py"
SCHEMA = {
    "type": "object",
    "required": ["name", "items"],
    "properties": {
        "name": {"type": "string"},
        "items": {"type": "array", "items": {"type": "integer"}},
    },
}


def run_validator(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(VALIDATOR), *args], capture_output=True, text=True)


@pytest.fixture
def schema(tmp_path) -> Path:
    path = tmp_path / "schema.json"
    path.write_text(json.dumps(SCHEMA), encoding="utf-8")
    return path


def write_report(tmp_path, content) -> Path:
    path = tmp_path / "report.json"
    path.write_text(content if isinstance(content, str) else json.dumps(content), encoding="utf-8")
    return path


def test_valid_report_exits_0(tmp_path, schema):
    report = write_report(tmp_path, {"name": "x", "items": [1, 2]})
    result = run_validator("--schema", str(schema), "--report", str(report))
    assert result.returncode == 0
    assert "is valid" in result.stdout


def test_invalid_report_exits_1_and_lists_errors_in_order(tmp_path, schema):
    items = [1] * 15
    items[4] = "four"
    items[14] = "fourteen"
    report = write_report(tmp_path, {"items": items})
    result = run_validator("-s", str(schema), "-r", str(report))
    assert result.returncode == 1
    lines = result.stdout.splitlines()
    assert lines == [
        "<root>: 'name' is a required property",
        "items/4: 'four' is not of type 'integer'",
        "items/14: 'fourteen' is not of type 'integer'",
        f"{report} is invalid: 3 error(s)",
    ]


def test_missing_report_exits_2(tmp_path, schema):
    result = run_validator("-s", str(schema), "-r", str(tmp_path / "missing.json"))
    assert result.returncode == 2
    assert result.stdout == ""
    assert "error:" in result.stderr


def test_report_with_broken_json_exits_2(tmp_path, schema):
    report = write_report(tmp_path, "{not json")
    result = run_validator("-s", str(schema), "-r", str(report))
    assert result.returncode == 2
    assert "error:" in result.stderr


def test_invalid_schema_exits_2(tmp_path):
    schema = tmp_path / "schema.json"
    schema.write_text(json.dumps({"type": "not-a-type"}), encoding="utf-8")
    report = write_report(tmp_path, {})
    result = run_validator("-s", str(schema), "-r", str(report))
    assert result.returncode == 2
    assert "invalid schema" in result.stderr


def test_missing_arguments_exit_2():
    result = run_validator()
    assert result.returncode == 2
    assert "--schema" in result.stderr

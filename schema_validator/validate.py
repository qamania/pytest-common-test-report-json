"""Validate a CTRF JSON report against a JSON schema.

Usage:
    python validate.py --schema ctrf.schema.json --report out.ctrf.json

Exit codes:
    0 - the report is valid
    1 - the report has validation errors
    2 - bad arguments, or a file could not be read or parsed
"""
import argparse
import json
import sys

from jsonschema import Draft7Validator
from jsonschema.exceptions import SchemaError
from jsonschema.validators import validator_for


def load_json(path):
    with open(path, encoding='utf-8') as f:
        return json.load(f)


def format_path(error):
    return '/'.join(str(x) for x in error.absolute_path) or '<root>'


def validate(schema, report):
    validator_cls = validator_for(schema, default=Draft7Validator)
    validator_cls.check_schema(schema)
    # sort array indexes numerically, so tests/4 comes before tests/15
    return sorted(validator_cls(schema).iter_errors(report),
                  key=lambda e: [(0, x, '') if isinstance(x, int) else (1, 0, x) for x in e.absolute_path])


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description='Validate a CTRF JSON report against a JSON schema.')
    parser.add_argument('-s', '--schema', required=True, help='path to the JSON schema file')
    parser.add_argument('-r', '--report', required=True, help='path to the JSON report file')
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    try:
        schema = load_json(args.schema)
        report = load_json(args.report)
        errors = validate(schema, report)
    except (OSError, json.JSONDecodeError) as e:
        print(f'error: {e}', file=sys.stderr)
        return 2
    except SchemaError as e:
        print(f'error: invalid schema {args.schema}: {e.message}', file=sys.stderr)
        return 2

    if not errors:
        print(f'{args.report} is valid')
        return 0

    for e in errors:
        print(f'{format_path(e)}: {e.message}')
    print(f'{args.report} is invalid: {len(errors)} error(s)')
    return 1


if __name__ == '__main__':
    sys.exit(main())

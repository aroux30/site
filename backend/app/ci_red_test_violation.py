"""Temporary RED-TEST file for CI gate verification (deleted after test).

Deliberately violates ruff rules: F401 (unused import), E501 (long line),
and ruff format check (non-canonical spacing)."""
import json  # noqa: F401 deliberately unused import for the red test

BAD_FORMAT_LINE    =    {"a": 1,   "b": 2}
VERY_LONG_STRING_FOR_E501 = "this line is intentionally much longer than the ninety-nine character limit enforced by the backend ruff configuration gate"
print(json.dumps(BAD_FORMAT_LINE), VERY_LONG_STRING_FOR_E501)

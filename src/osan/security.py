"""Secret detection for volunteer result payloads."""

from __future__ import annotations

import re
from collections.abc import Iterable
from typing import Any


SENSITIVE_KEY_RE = re.compile(
    r"(api[_-]?key|secret|token|cookie|session|authorization|oauth|bearer)",
    re.IGNORECASE,
)

SECRET_VALUE_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"sk-[A-Za-z0-9_-]{16,}"),
    re.compile(r"sk-ant-[A-Za-z0-9_-]{16,}"),
    re.compile(r"xox[baprs]-[A-Za-z0-9-]{16,}"),
    re.compile(r"Bearer\s+[A-Za-z0-9._~+/=-]{16,}", re.IGNORECASE),
    re.compile(r"sessionid=[A-Za-z0-9._~+/=-]{8,}", re.IGNORECASE),
)


def find_secret_paths(payload: Any) -> list[str]:
    """Return JSON-like paths that appear to contain credentials."""

    findings: list[str] = []

    def visit(value: Any, path: str) -> None:
        if isinstance(value, dict):
            for key, child in value.items():
                child_path = f"{path}.{key}" if path else str(key)
                if SENSITIVE_KEY_RE.search(str(key)):
                    findings.append(child_path)
                visit(child, child_path)
            return

        if isinstance(value, list):
            for index, child in enumerate(value):
                visit(child, f"{path}[{index}]")
            return

        if isinstance(value, str):
            for pattern in SECRET_VALUE_PATTERNS:
                if pattern.search(value):
                    findings.append(path or "$")
                    break

    visit(payload, "")
    return sorted(set(findings))


def assert_no_secrets(payload: Any) -> None:
    findings = find_secret_paths(payload)
    if findings:
        joined = ", ".join(findings)
        raise ValueError(f"payload appears to contain secrets at: {joined}")


def redact_lines(lines: Iterable[str]) -> list[str]:
    redacted: list[str] = []
    for line in lines:
        output = line
        for pattern in SECRET_VALUE_PATTERNS:
            output = pattern.sub("[REDACTED]", output)
        redacted.append(output)
    return redacted

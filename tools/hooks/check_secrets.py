#!/usr/bin/env python3
"""Block commits containing secret-shaped strings or sensitive files.

Tuned to this project's providers plus common credential formats
(AGENTS.md section 6). Placeholder values are ignored. pre-commit passes
staged paths as arguments.
"""

from __future__ import annotations

import sys
from pathlib import Path
from re import I, Pattern, compile

PLACEHOLDER = compile(r"changeme|example|placeholder|your[-_]|xxx+|dummy|redacted|<[^>]+>", I)

SECRETS: list[tuple[Pattern[str], str]] = [
    (compile(r"sk-or-v1-[A-Za-z0-9]{20,}"), "OpenRouter key"),
    (compile(r"sk-proj-[A-Za-z0-9_-]{20,}"), "OpenAI project key"),
    (compile(r"sk-ant-[A-Za-z0-9_-]{20,}"), "Anthropic key"),
    (compile(r"\bgsk_[A-Za-z0-9]{40,}"), "Groq key"),
    (compile(r"\btgp_v1_[A-Za-z0-9_-]{20,}"), "Together key"),
    (compile(r"\bsk-[A-Za-z0-9]{32,}"), "OpenAI-style key"),
    (compile(r"\b[MNO][\w-]{23,27}\.[\w-]{6}\.[\w-]{27,}"), "Discord bot token"),
    (compile(r"\bAKIA[0-9A-Z]{16}\b"), "AWS access key id"),
    (compile(r"-----BEGIN (?:RSA |EC |OPENSSH |DSA |PGP )?PRIVATE KEY-----"), "private key block"),
    (
        compile(r"(?i)(?:api[_-]?key|secret|token|passwd|password)\s*[:=]\s*['\"][^'\"]{16,}['\"]"),
        "hardcoded credential",
    ),
]

SENSITIVE_NAME = compile(
    r"(^|/)(\.env(\.[^/]*)?|[^/]*\.env|id_rsa|id_ed25519|.+\.pem|.+\.key|.+\.p12|.+\.pfx)$"
)
ALLOWED_NAME = compile(r"\.env\.example$")


def scan(path: str) -> list[tuple[int, str, str]]:
    hits: list[tuple[int, str, str]] = []
    name = Path(path).as_posix()
    if SENSITIVE_NAME.search(name) and not ALLOWED_NAME.search(name):
        hits.append((0, "sensitive filename", name))
    try:
        text = Path(path).read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        return hits
    for lineno, line in enumerate(text.splitlines(), start=1):
        if PLACEHOLDER.search(line):
            continue
        for pattern, label in SECRETS:
            if pattern.search(line):
                hits.append((lineno, label, line.strip()[:80]))
                break
    return hits


def main(argv: list[str]) -> int:
    failures: list[tuple[str, int, str, str]] = []
    for path in argv[1:]:
        for lineno, label, context in scan(path):
            failures.append((path, lineno, label, context))
    if failures:
        print("Potential secrets blocked (AGENTS.md s6):")
        for path, lineno, label, context in failures:
            where = f"{path}:{lineno}" if lineno else path
            print(f"  {where} [{label}] {context}")
        print(
            "Move secrets to .env (gitignored) or the settings store; use placeholders in source."
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))

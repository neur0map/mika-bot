#!/usr/bin/env python3
"""Reject commit messages carrying co-author or AI attribution.

Runs at the commit-msg stage; argv[1] is the path to the commit message file.
See AGENTS.md section 2, golden rule 1.
"""

from __future__ import annotations

import re
import sys

PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"^\s*co-authored-by:", re.I | re.M), "Co-authored-by trailer"),
    (re.compile(r"generated (with|by)", re.I), "generation attribution"),
    (re.compile(r"\bco-?authored\b", re.I), "co-author mention"),
    (re.compile(r"noreply@anthropic\.com", re.I), "AI author email"),
    (re.compile(r"\bclaude code\b", re.I), "tool attribution"),
    (
        re.compile(
            r"(written|authored|created) (with|by) (claude|chatgpt|copilot|gpt|an? ai)\b", re.I
        ),
        "AI authorship",
    ),
    (
        re.compile(r"with (the help of|assistance from) (an? ai|claude|chatgpt|copilot)", re.I),
        "AI assistance note",
    ),
    (re.compile("\U0001f916"), "robot emoji"),
]


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        return 0
    with open(argv[1], encoding="utf-8", errors="replace") as handle:
        raw = handle.read()
    body = "\n".join(line for line in raw.splitlines() if not line.startswith("#"))
    hits = [label for pattern, label in PATTERNS if pattern.search(body)]
    if hits:
        print("commit-msg rejected: attribution is not allowed (AGENTS.md s2).")
        for label in hits:
            print(f"  - {label}")
        print("Rewrite the message as a careful engineer would: no tool or AI mentions.")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))

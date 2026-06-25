#!/usr/bin/env python3
"""Block AI-slop comments in staged Python files.

pre-commit passes staged paths as arguments. Flags narration, placeholder, and
AI-tell comments (AGENTS.md section 4). Escape hatch: put `# allow-comment` on
the line for an intentional comment the heuristics would otherwise flag.
"""

from __future__ import annotations

import re
import sys
import tokenize
from collections.abc import Iterator

EMOJI = re.compile(
    "[\U0001f000-\U0001faff\U00002600-\U000027bf\U0001f1e6-\U0001f1ff\u2190-\u21ff\u2b00-\u2bff]"
)

PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\bas an ai\b", re.I), "AI self-reference"),
    (re.compile(r"\.\.\.\s*existing code", re.I), "placeholder elision"),
    (re.compile(r"\brest of (the )?code\b", re.I), "placeholder elision"),
    (re.compile(r"\byour code here\b", re.I), "placeholder"),
    (re.compile(r"\b(implementation|code) (goes )?here\b", re.I), "placeholder"),
    (re.compile(r"^todo:?\s*implement", re.I), "committed stub"),
    (re.compile(r"^step\s*\d+\b", re.I), "tutorial narration"),
    (re.compile(r"^(now|first|next|then|finally)[,:]?\s", re.I), "narration"),
    (
        re.compile(
            r"^this (function|method|class|code|will|is|does|returns|creates|loops|iterates)\b",
            re.I,
        ),
        "restates code",
    ),
    (
        re.compile(
            r"^(create|define|initialize|instantiate|import|loop through|iterate over|return the|return a)\b",
            re.I,
        ),
        "restates code",
    ),
    (
        re.compile(
            r"^we (then |now |)?(create|define|call|set|get|loop|iterate|initialize|instantiate|return|import)\b",
            re.I,
        ),
        "narration",
    ),
]


def comments(path: str) -> Iterator[tuple[int, str, str]]:
    try:
        with open(path, "rb") as handle:
            for tok in tokenize.tokenize(handle.readline):
                if tok.type == tokenize.COMMENT:
                    yield tok.start[0], tok.line, tok.string
    except (tokenize.TokenError, SyntaxError, IndentationError, ValueError):
        return


def main(argv: list[str]) -> int:
    failures: list[tuple[str, int, str, str]] = []
    for path in argv[1:]:
        if not path.endswith(".py"):
            continue
        for lineno, line, comment in comments(path):
            if "allow-comment" in line:
                continue
            body = comment.lstrip("#").strip()
            if not body:
                continue
            if EMOJI.search(comment):
                failures.append((path, lineno, "emoji in comment", body))
                continue
            for pattern, label in PATTERNS:
                if pattern.search(body):
                    failures.append((path, lineno, label, body))
                    break
    if failures:
        print("AI-slop comments rejected (AGENTS.md s4):")
        for path, lineno, label, body in failures:
            print(f"  {path}:{lineno} [{label}] # {body[:60]}")
        print("Delete the narration, or comment the *why*. Escape hatch: # allow-comment")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))

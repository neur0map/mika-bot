#!/usr/bin/env python3
"""Enforce size and comment-density limits on staged Python files.

No monolith files, no comment-dominated files, no walls of comments
(AGENTS.md section 2). pre-commit passes staged paths as arguments.
"""

from __future__ import annotations

import sys
import tokenize

MAX_FILE_LINES = 500
MAX_COMMENT_RATIO = 0.40
MIN_CODE_FOR_RATIO = 20
MAX_COMMENT_BLOCK = 12


def analyze(path: str) -> tuple[int, int, int, int] | None:
    comment_lines: set[int] = set()
    try:
        with open(path, "rb") as handle:
            for tok in tokenize.tokenize(handle.readline):
                if tok.type == tokenize.COMMENT:
                    comment_lines.add(tok.start[0])
    except (tokenize.TokenError, SyntaxError, IndentationError, ValueError):
        return None
    with open(path, encoding="utf-8", errors="replace") as handle:
        lines = handle.readlines()
    total = len(lines)
    blank = sum(1 for line in lines if not line.strip())
    n_comment = len(comment_lines)
    code = total - blank - n_comment
    longest = run = 0
    for i, line in enumerate(lines, start=1):
        if i in comment_lines and line.strip().startswith("#"):
            run += 1
            longest = max(longest, run)
        else:
            run = 0
    return total, max(code, 0), n_comment, longest


def main(argv: list[str]) -> int:
    failures: list[str] = []
    for path in argv[1:]:
        if not path.endswith(".py"):
            continue
        result = analyze(path)
        if result is None:
            continue
        total, code, n_comment, longest = result
        if total > MAX_FILE_LINES:
            failures.append(
                f"{path}: {total} lines (> {MAX_FILE_LINES}) - split into focused modules"
            )
        if code >= MIN_CODE_FOR_RATIO and n_comment / max(code, 1) > MAX_COMMENT_RATIO:
            pct = int(MAX_COMMENT_RATIO * 100)
            failures.append(
                f"{path}: {n_comment} comment vs {code} code lines (> {pct}%) - trim narration"
            )
        if longest >= MAX_COMMENT_BLOCK:
            failures.append(
                f"{path}: {longest} consecutive comment lines (>= {MAX_COMMENT_BLOCK}) - move prose to docs/ or a docstring"
            )
    if failures:
        print("File size/comment limits exceeded (AGENTS.md s2):")
        for item in failures:
            print(f"  {item}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))

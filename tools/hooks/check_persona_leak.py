#!/usr/bin/env python3
"""Block the internal codename from leaking into user-facing surfaces.

The codename "mika" is fine in operator/config/infra code, but must NEVER appear
in end-user-facing Discord surfaces (slash command names, descriptions, replies,
component labels). Those use the configured persona name (config.persona.name) so
deployers can rebrand. See AGENTS.md.

pre-commit scopes this to bot/userbot command/component/event files. It flags
non-docstring string literals containing the codename; identifiers and imports
(e.g. `from mika.core ...`) are not strings and are never flagged.
"""

from __future__ import annotations

import ast
import sys

CODENAME = "mika"


def _docstring_ids(tree: ast.AST) -> set[int]:
    skip: set[int] = set()
    scopes = (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
    for node in ast.walk(tree):
        body = getattr(node, "body", None)
        if isinstance(node, scopes) and body:
            first = body[0]
            if (
                isinstance(first, ast.Expr)
                and isinstance(first.value, ast.Constant)
                and isinstance(first.value.value, str)
            ):
                skip.add(id(first.value))
    return skip


def scan(path: str) -> list[tuple[int, str]]:
    try:
        with open(path, encoding="utf-8") as handle:
            tree = ast.parse(handle.read())
    except (OSError, SyntaxError, ValueError):
        return []
    skip = _docstring_ids(tree)
    hits: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Constant)
            and isinstance(node.value, str)
            and id(node) not in skip
            and CODENAME in node.value.lower()
        ):
            hits.append((node.lineno, node.value.strip()[:60]))
    return hits


def main(argv: list[str]) -> int:
    failures: list[tuple[str, int, str]] = []
    for path in argv[1:]:
        if path.endswith(".py"):
            for lineno, text in scan(path):
                failures.append((path, lineno, text))
    if failures:
        print("Codename leaked into a user-facing surface (AGENTS.md):")
        for path, lineno, text in failures:
            print(f'  {path}:{lineno}  "{text}"')
        print("User-facing text must use config.persona.name, not the literal codename.")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))

#!/usr/bin/env python3
"""Print privacy-safe aggregate Mika turn metrics from a shared archive."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

from mika.ai.learning.metrics import summarize_archive


def main() -> None:
    """Parse the archive path and emit aggregate turn metrics as JSON."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path, help="read-only path to mika-archive.sqlite")
    args = parser.parse_args()
    metrics = summarize_archive(args.archive)
    sys.stdout.write(json.dumps(asdict(metrics), sort_keys=True) + "\n")


if __name__ == "__main__":
    main()

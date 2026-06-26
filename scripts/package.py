"""Build the customer release zip: a clean, secret-free product bundle.

Uses an allowlist (only ship what is listed here) so that secrets, the reference
folder, developer tooling, tests, and the personal userbot can never leak into a
customer download. A secret scan over the staged tree is the final safety net.
"""

from __future__ import annotations

import re
import shutil
import tomllib
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

INCLUDE_FILES = (
    "install.sh",
    "Dockerfile",
    "docker-compose.yml",
    ".dockerignore",
    "pyproject.toml",
    "uv.lock",
    ".python-version",
    ".env.example",
    "LICENSE",
    "ARCHITECTURE.md",
)
INCLUDE_DIRS = ("src", "config", "docs")
RENAME = {
    "packaging/README.release.md": "README.md",
    "packaging/Makefile.user": "Makefile",
}

SECRET_PATTERNS = (
    re.compile(r"sk-or-v1-[A-Za-z0-9]{20,}"),
    re.compile(r"sk-proj-[A-Za-z0-9_-]{20,}"),
    re.compile(r"\bgsk_[A-Za-z0-9]{40,}"),
    re.compile(r"\btgp_v1_[A-Za-z0-9_-]{20,}"),
    re.compile(r"\b[MNO][\w-]{23,27}\.[\w-]{6}\.[\w-]{27,}"),
)
PLACEHOLDER = re.compile(r"changeme|example|your[-_]|<[^>]+>", re.IGNORECASE)


def _version() -> str:
    data = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    return str(data["project"]["version"])


def _stage(target: Path) -> None:
    if target.exists():
        shutil.rmtree(target)
    target.mkdir(parents=True)
    for name in INCLUDE_FILES:
        source = ROOT / name
        if source.exists():
            shutil.copy2(source, target / name)
    for name in INCLUDE_DIRS:
        source = ROOT / name
        if source.exists():
            shutil.copytree(
                source, target / name, ignore=shutil.ignore_patterns("__pycache__", "*.pyc")
            )
    for source_rel, dest_name in RENAME.items():
        source = ROOT / source_rel
        if source.exists():
            shutil.copy2(source, target / dest_name)


def _assert_clean(target: Path) -> None:
    for path in target.rglob("*"):
        if not path.is_file():
            continue
        if path.name == ".env" or path.name.endswith((".pem", ".key")) or path.name == "id_rsa":
            raise SystemExit(f"refusing to ship sensitive file: {path}")
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for line in text.splitlines():
            if PLACEHOLDER.search(line):
                continue
            if any(pattern.search(line) for pattern in SECRET_PATTERNS):
                raise SystemExit(f"refusing to ship: secret-shaped text in {path}")


def _zip(staging: Path, version: str) -> Path:
    archive = ROOT / "dist" / f"mika-{version}.zip"
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as bundle:
        for path in sorted(staging.rglob("*")):
            if path.is_file():
                bundle.write(path, path.relative_to(staging.parent))
    return archive


def main() -> None:
    version = _version()
    (ROOT / "dist").mkdir(exist_ok=True)
    staging = ROOT / "dist" / f"mika-{version}"
    print(f"staging release {version} ...")
    _stage(staging)
    print("scanning staged tree for secrets ...")
    _assert_clean(staging)
    archive = _zip(staging, version)
    print(f"built {archive.relative_to(ROOT)} ({archive.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()

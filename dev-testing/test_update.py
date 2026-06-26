"""The safe updater: replaces code, never touches user data or the active persona."""

from __future__ import annotations

from pathlib import Path

from mika.cli.commands.update import _apply, _find_release, _version


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_apply_keeps_user_data_and_replaces_code(tmp_path: Path) -> None:
    root = tmp_path / "install"
    _write(root / ".env", "DISCORD_TOKEN=mysecret")
    _write(root / "var" / "mika.sqlite3", "memory-db")
    _write(root / "config" / "persona.md", "ACTIVE PERSONA")
    _write(root / "config" / "personas" / "friendly.md", "old friendly")
    _write(root / "src" / "mika" / "removed.py", "stale module")
    _write(root / "pyproject.toml", '[project]\nversion = "0.1.0"\n')

    release = tmp_path / "mika-0.2.0"
    _write(release / "src" / "mika" / "added.py", "fresh module")
    _write(release / "config" / "persona.md", "DEFAULT PERSONA")  # must not overwrite
    _write(release / "config" / "personas" / "hero.md", "new preset")
    _write(release / "pyproject.toml", '[project]\nversion = "0.2.0"\n')
    _write(release / "README.md", "product readme")

    _apply(release, root)

    # user data untouched
    assert (root / ".env").read_text() == "DISCORD_TOKEN=mysecret"
    assert (root / "var" / "mika.sqlite3").read_text() == "memory-db"
    assert (root / "config" / "persona.md").read_text() == "ACTIVE PERSONA"
    # code cleanly replaced (stale module gone, new module present)
    assert not (root / "src" / "mika" / "removed.py").exists()
    assert (root / "src" / "mika" / "added.py").read_text() == "fresh module"
    # presets and top-level files updated
    assert (root / "config" / "personas" / "hero.md").read_text() == "new preset"
    assert (root / "README.md").read_text() == "product readme"


def test_find_release_locates_top_dir(tmp_path: Path) -> None:
    release = tmp_path / "mika-9.9.9"
    _write(release / "pyproject.toml", "x")
    _write(release / "src" / "mika" / "__init__.py", "")
    assert _find_release(tmp_path) == release


def test_version_reads_pyproject(tmp_path: Path) -> None:
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text('[project]\nversion = "1.2.3"\n', encoding="utf-8")
    assert _version(pyproject) == "1.2.3"

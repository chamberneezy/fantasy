"""Publish this week of the season pad to GitHub Pages (read-only copy).

Exports the week (scripts/export_season.py), force-pushes it as the only
commit on the ``season-data`` branch, then starts the Pages workflow on the
branch that holds the page. Skips the push when nothing changed since the
last publish. Run by the refresh timer after each pull.

    .venv/bin/python scripts/publish_season.py [--force]
"""

from __future__ import annotations

import hashlib
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))

from export_season import DEFAULT_OUT, export  # noqa: E402

DATA_BRANCH = "season-data"
# The branch whose docs/ and workflow GitHub Pages deploys.
PAGES_BRANCH = "cursor/3rd-league-draft-dollars"
STAMP = DEFAULT_OUT.parent / "season_export.published"
PUBLIC_NAME = re.compile(r"(\d{4}-\d{2}-\d{2}|index)\.json")


def _run(*args: str, cwd: Path | None = None) -> str:
    return subprocess.run(args, cwd=cwd, check=True, capture_output=True, text=True).stdout.strip()


def _digest(folder: Path) -> str:
    """The week's content, leaving out the publish time in the index."""
    digest = hashlib.sha256()
    for path in sorted(folder.glob("*.json")):
        if path.name != "index.json":
            digest.update(path.name.encode())
            digest.update(path.read_bytes())
    return digest.hexdigest()


def publish(force: bool = False) -> str:
    index = export(DEFAULT_OUT)
    digest = _digest(DEFAULT_OUT)
    if not force and STAMP.exists() and STAMP.read_text().strip() == digest:
        return "unchanged, not published"
    remote = _run("git", "remote", "get-url", "origin", cwd=ROOT)
    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp)
        # Only the week's day files and the index go public; nothing else in the folder, ever.
        for path in DEFAULT_OUT.glob("*.json"):
            if PUBLIC_NAME.fullmatch(path.name):
                shutil.copy2(path, work / path.name)
        _run("git", "init", "-q", "-b", DATA_BRANCH, cwd=work)
        _run("git", "add", "-A", cwd=work)
        _run(
            "git", "-c", "user.name=NBA Fantasy pad", "-c", "user.email=81742479+chamberneezy@users.noreply.github.com",
            "commit", "-q", "-m", f"Season week {index['week']}, published {index['published_at']}", cwd=work,
        )
        _run("git", "push", "-q", "--force", remote, f"HEAD:refs/heads/{DATA_BRANCH}", cwd=work)
    _run("gh", "workflow", "run", "pages.yml", "--ref", PAGES_BRANCH, cwd=ROOT)
    STAMP.write_text(digest)
    return f"published week {index['week']} ({len(index['days'])} days)"


if __name__ == "__main__":
    print(publish(force="--force" in sys.argv[1:]))

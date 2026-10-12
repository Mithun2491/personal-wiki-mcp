"""Optional private wiki snapshot fetcher for the Render deploy.

Read-only purpose: at service start, if WIKI_SNAPSHOT_URL is set,
download a private tar.gz snapshot of a wiki hub and unpack it into the
ephemeral deploy directory (default: deploy-wiki/). When the variable is
unset or empty — the default — this script does nothing and exits 0, so
the committed synthetic sample hub keeps serving.

Security properties:
- HTTPS only; the URL is a secret and is never printed or logged.
- Download is size-capped and time-bounded (no streaming from disk).
- Archive members with absolute paths, '..', links, or devices are
  rejected before extraction (tarfile 'data' filter plus an explicit
  pre-scan).
- The snapshot must contain a wikis.json hub registry at its root (or
  inside exactly one top-level folder) before it replaces the target.
- The target directory is replaced atomically-ish (validated in a temp
  dir first; the live directory is only touched after validation).

Stdlib only — no third-party or paid dependencies.
"""

from __future__ import annotations

import os
import shutil
import sys
import tarfile
import tempfile
import urllib.request
from pathlib import Path

MAX_SNAPSHOT_BYTES = 100 * 1024 * 1024  # 100 MiB
DOWNLOAD_TIMEOUT_SECONDS = 120
PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_TARGET = PROJECT_ROOT / "deploy-wiki"


def _log(message: str) -> None:
    # stderr only; never includes the URL or any env value.
    print(f"fetch_private_wiki: {message}", file=sys.stderr)


def _has_registry(directory: Path) -> bool:
    return (directory / "wikis.json").is_file()


def _find_snapshot_root(extracted: Path) -> Path | None:
    """Return the directory containing wikis.json, or None."""
    if _has_registry(extracted):
        return extracted
    entries = [entry for entry in extracted.iterdir() if entry.is_dir()]
    if len(entries) == 1 and _has_registry(entries[0]):
        return entries[0]
    return None


def _reject_unsafe_members(archive: tarfile.TarFile) -> None:
    """Reject traversal/absolute/link/device members before extraction."""
    for member in archive.getmembers():
        name = member.name
        if name.startswith("/") or name.startswith("\\"):
            raise ValueError(f"archive member has an absolute path: {name!r}")
        if ".." in Path(name).parts:
            raise ValueError(f"archive member escapes the root: {name!r}")
        if member.issym() or member.islnk():
            raise ValueError(f"archive member is a link: {name!r}")
        if member.isdev() or member.isfifo():
            raise ValueError(f"archive member is a device: {name!r}")


def _download(url: str) -> Path:
    """Stream the snapshot to a temp file with size and time bounds."""
    temp_file = tempfile.NamedTemporaryFile(suffix=".tar.gz", delete=False)
    temp_path = Path(temp_file.name)
    try:
        request = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(request, timeout=DOWNLOAD_TIMEOUT_SECONDS) as response:
            total = 0
            while True:
                chunk = response.read(64 * 1024)
                if not chunk:
                    break
                total += len(chunk)
                if total > MAX_SNAPSHOT_BYTES:
                    raise ValueError(
                        f"snapshot exceeds the {MAX_SNAPSHOT_BYTES} byte cap"
                    )
                temp_file.write(chunk)
    except BaseException:
        temp_file.close()
        temp_path.unlink(missing_ok=True)
        raise
    temp_file.close()
    return temp_path


def _verify_sha256(path: Path, expected: str) -> None:
    import hashlib

    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(64 * 1024), b""):
            digest.update(chunk)
    if digest.hexdigest() != expected.strip().lower():
        raise ValueError("snapshot sha256 mismatch; refusing to install")


def _install(snapshot_root: Path, target: Path) -> None:
    """Replace target with the validated snapshot."""
    staging = target.with_name(target.name + ".staging")
    if staging.exists():
        shutil.rmtree(staging)
    shutil.copytree(snapshot_root, staging)
    if target.exists():
        shutil.rmtree(target)
    staging.rename(target)


def main() -> int:
    url = os.environ.get("WIKI_SNAPSHOT_URL", "").strip()
    if not url:
        _log("WIKI_SNAPSHOT_URL not set; keeping the existing wiki directory")
        return 0
    if not url.startswith("https://"):
        _log("refusing to fetch: WIKI_SNAPSHOT_URL must be https://")
        return 1

    target = Path(os.environ.get("WIKI_SNAPSHOT_TARGET", str(DEFAULT_TARGET)))
    archive_path: Path | None = None
    work_dir = tempfile.mkdtemp(prefix="wiki-snapshot-")
    try:
        _log("downloading private wiki snapshot")
        archive_path = _download(url)
        expected_sha = os.environ.get("WIKI_SNAPSHOT_SHA256", "").strip()
        if expected_sha:
            _verify_sha256(archive_path, expected_sha)
            _log("snapshot sha256 verified")

        extracted = Path(work_dir) / "extracted"
        extracted.mkdir()
        with tarfile.open(archive_path, "r:gz") as archive:
            _reject_unsafe_members(archive)
            archive.extractall(extracted, filter="data")

        snapshot_root = _find_snapshot_root(extracted)
        if snapshot_root is None:
            _log("snapshot does not contain a wikis.json hub registry; refusing to install")
            return 1

        _install(snapshot_root, target)
        _log("snapshot installed")
        return 0
    except Exception as exc:  # noqa: BLE001 - operator-facing exit path
        # exc messages are ours or urllib's; the secret URL is never included.
        _log(f"failed: {exc}")
        return 1
    finally:
        if archive_path is not None:
            archive_path.unlink(missing_ok=True)
        shutil.rmtree(work_dir, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())

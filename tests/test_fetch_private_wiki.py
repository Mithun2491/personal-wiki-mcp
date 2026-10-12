"""Tests for the optional private-snapshot fetch script: no-op default,
https-only enforcement, archive traversal rejection, and registry
validation. No network access is performed."""

from __future__ import annotations

import io
import tarfile
from pathlib import Path

import pytest
from scripts import fetch_private_wiki as fetch


def _make_targz(members: dict[str, bytes]) -> bytes:
    """Build an in-memory tar.gz from {name: content}."""
    import gzip

    raw = io.BytesIO()
    with tarfile.open(fileobj=raw, mode="w") as archive:
        for name, content in members.items():
            info = tarfile.TarInfo(name=name)
            info.size = len(content)
            archive.addfile(info, io.BytesIO(content))
    return gzip.compress(raw.getvalue())


def _write_archive(tmp_path: Path, members: dict[str, bytes]) -> Path:
    path = tmp_path / "snap.tar.gz"
    path.write_bytes(_make_targz(members))
    return path


def test_noop_when_url_unset(tmp_path, monkeypatch, capsys):
    monkeypatch.delenv("WIKI_SNAPSHOT_URL", raising=False)
    monkeypatch.setenv("WIKI_SNAPSHOT_TARGET", str(tmp_path / "wiki"))
    assert fetch.main() == 0
    assert not (tmp_path / "wiki").exists()
    assert "not set" in capsys.readouterr().err


def test_rejects_non_https_url(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("WIKI_SNAPSHOT_URL", "http://example.invalid/snap.tar.gz")
    monkeypatch.setenv("WIKI_SNAPSHOT_TARGET", str(tmp_path / "wiki"))
    assert fetch.main() == 1
    assert "https://" in capsys.readouterr().err
    assert not (tmp_path / "wiki").exists()


def test_rejects_traversal_members(tmp_path, monkeypatch, capsys):
    """A tar member with '..' must be refused before extraction."""
    payload = _write_archive(
        tmp_path, {"../evil.md": b"escaped", "wikis.json": b"{}"}
    )
    monkeypatch.setenv("WIKI_SNAPSHOT_URL", "https://example.invalid/snap.tar.gz")
    monkeypatch.setenv("WIKI_SNAPSHOT_TARGET", str(tmp_path / "wiki"))
    monkeypatch.setattr(fetch, "_download", lambda url: payload)
    assert fetch.main() == 1
    assert not (tmp_path / "evil.md").exists()
    assert not (tmp_path / "wiki").exists()


def test_rejects_archive_without_registry(tmp_path, monkeypatch, capsys):
    payload = _write_archive(tmp_path, {"readme.md": b"no registry here"})
    monkeypatch.setenv("WIKI_SNAPSHOT_URL", "https://example.invalid/snap.tar.gz")
    monkeypatch.setenv("WIKI_SNAPSHOT_TARGET", str(tmp_path / "wiki"))
    monkeypatch.setattr(fetch, "_download", lambda url: payload)
    assert fetch.main() == 1
    assert "wikis.json" in capsys.readouterr().err
    assert not (tmp_path / "wiki").exists()


def test_installs_valid_snapshot(tmp_path, monkeypatch, capsys):
    payload = _write_archive(
        tmp_path,
        {
            "wikis.json": b'{"default": "<HUB>", "wikis": {"hub": {"path": "<HUB>"}}}',
            "_index.md": b"# Snapshot Hub\n",
        },
    )
    target = tmp_path / "wiki"
    monkeypatch.setenv("WIKI_SNAPSHOT_URL", "https://example.invalid/snap.tar.gz")
    monkeypatch.setenv("WIKI_SNAPSHOT_TARGET", str(target))
    monkeypatch.setattr(fetch, "_download", lambda url: payload)
    assert fetch.main() == 0
    assert (target / "wikis.json").is_file()
    assert (target / "_index.md").read_text(encoding="utf-8") == "# Snapshot Hub\n"


def test_installs_snapshot_wrapped_in_single_folder(tmp_path, monkeypatch):
    payload = _write_archive(
        tmp_path,
        {
            "hub/wikis.json": b'{"default": "<HUB>", "wikis": {}}',
            "hub/_index.md": b"# Wrapped\n",
        },
    )
    target = tmp_path / "wiki"
    monkeypatch.setenv("WIKI_SNAPSHOT_URL", "https://example.invalid/snap.tar.gz")
    monkeypatch.setenv("WIKI_SNAPSHOT_TARGET", str(target))
    monkeypatch.setattr(fetch, "_download", lambda url: payload)
    assert fetch.main() == 0
    assert (target / "wikis.json").is_file()


def test_sha256_mismatch_refuses_install(tmp_path, monkeypatch, capsys):
    payload = _write_archive(tmp_path, {"wikis.json": b"{}"})
    target = tmp_path / "wiki"
    monkeypatch.setenv("WIKI_SNAPSHOT_URL", "https://example.invalid/snap.tar.gz")
    monkeypatch.setenv("WIKI_SNAPSHOT_SHA256", "0" * 64)
    monkeypatch.setenv("WIKI_SNAPSHOT_TARGET", str(target))
    monkeypatch.setattr(fetch, "_download", lambda url: payload)
    assert fetch.main() == 1
    assert "sha256" in capsys.readouterr().err
    assert not target.exists()


def test_url_never_appears_in_output(tmp_path, monkeypatch, capsys):
    """The secret URL must not be echoed on any code path."""
    secret_url = "https://user:pass@example.invalid/private/snap.tar.gz?sig=SECRET"
    monkeypatch.setenv("WIKI_SNAPSHOT_URL", secret_url)
    monkeypatch.setenv("WIKI_SNAPSHOT_TARGET", str(tmp_path / "wiki"))
    monkeypatch.setattr(fetch, "_download", lambda url: (_ for _ in ()).throw(OSError("boom")))
    assert fetch.main() == 1
    output = capsys.readouterr()
    assert "SECRET" not in output.err
    assert "user:pass" not in output.err
    assert secret_url not in output.err


def test_fetch_module_imports_no_third_party():
    """Static audit: the fetch script is stdlib-only."""
    import ast

    source = (Path(fetch.__file__)).read_text(encoding="utf-8")
    tree = ast.parse(source)
    stdlib = set(__import__("sys").stdlib_module_names)
    allowed_prefixes = ("scripts",)
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                root = alias.name.split(".")[0]
                assert root in stdlib, f"non-stdlib import: {alias.name}"
        elif isinstance(node, ast.ImportFrom):
            if node.level > 0 or node.module is None:
                continue
            root = node.module.split(".")[0]
            assert root in stdlib or root.startswith(allowed_prefixes), (
                f"non-stdlib import: {node.module}"
            )
    assert "urllib.request" in source
    assert "https://" in source  # https-only enforcement present

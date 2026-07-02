"""Kaggle access seam (spec 006) — the ONLY module that talks to the Kaggle API / the network.

A thin, mockable wrapper over the official `kaggle` client. The rules in storage/adapt.py and the
ingest functions consume what this returns; tests inject a fake via `set_client(...)` so the suite
never touches the network (FR-013).

The official `kaggle` package authenticates eagerly (on import / construction) and raises without a
token, so it is imported **lazily** inside `_RealKaggleClient` — importing THIS module never needs a
token, and `parse_url` / `credentials_present` work with no network and no `kaggle` install.
"""
from __future__ import annotations

import os
import re
import tempfile
import zipfile
from dataclasses import dataclass
from typing import Optional

TABULAR_EXTS = (".csv", ".tsv", ".parquet")

_DATASET_URL = re.compile(
    r"^(?:https?://)?(?:www\.)?kaggle\.com/datasets/(?P<owner>[^/\s]+)/(?P<slug>[^/?\s#]+)",
    re.IGNORECASE,
)


class KaggleAccessError(Exception):
    """Listing or download failed (private / 404 / network / oversize)."""


@dataclass(frozen=True)
class Ref:
    owner: str
    slug: str

    @property
    def path(self) -> str:
        return f"{self.owner}/{self.slug}"

    @property
    def canonical_url(self) -> str:
        return f"https://www.kaggle.com/datasets/{self.owner}/{self.slug}"


@dataclass(frozen=True)
class FileInfo:
    name: str
    size_bytes: Optional[int] = None


def parse_url(url: str) -> Optional[Ref]:
    """A Kaggle dataset URL → Ref, else None (competition/kernel/other host → None → R1 rejects)."""
    if not url:
        return None
    m = _DATASET_URL.match(url.strip())
    return Ref(owner=m.group("owner"), slug=m.group("slug")) if m else None


def credentials_present() -> bool:
    """True if a Kaggle token is configured (env pair or the standard token file). No network."""
    if os.environ.get("KAGGLE_USERNAME") and os.environ.get("KAGGLE_KEY"):
        return True
    return os.path.exists(os.path.join(os.path.expanduser("~"), ".kaggle", "kaggle.json"))


def _read_one_from_zip(zip_path: str, name: str, max_bytes: int) -> bytes:
    with zipfile.ZipFile(zip_path) as zf:
        members = zf.namelist()
        target = name if name in members else next(
            (m for m in members if m.lower().endswith(TABULAR_EXTS)), None)
        if target is None:
            raise KaggleAccessError("no tabular file inside the downloaded archive")
        if zf.getinfo(target).file_size > max_bytes:        # zip-bomb / oversize guard
            raise KaggleAccessError(f"file exceeds {max_bytes} bytes (uncompressed)")
        return zf.read(target)


class _RealKaggleClient:
    """Adapts the official `kaggle` package to the seam. Built only after credentials are confirmed."""

    def __init__(self):
        # Lazy import: the package authenticates eagerly and raises without a token.
        from kaggle.api.kaggle_api_extended import KaggleApi
        self._api = KaggleApi()
        self._api.authenticate()

    def list_files(self, ref: Ref):
        try:
            res = self._api.dataset_list_files(ref.path)
            files = getattr(res, "files", res) or []
            out = []
            for f in files:
                name = getattr(f, "name", getattr(f, "ref", str(f)))
                size = getattr(f, "totalBytes", getattr(f, "size", None))
                out.append(FileInfo(name=str(name), size_bytes=int(size) if size else None))
            return out
        except Exception as exc:                            # noqa: BLE001 — surface as typed error
            raise KaggleAccessError(str(exc)) from exc

    def file_size(self, ref: Ref, name: str):
        return next((f.size_bytes for f in self.list_files(ref) if f.name == name), None)

    def download_file(self, ref: Ref, name: str, max_bytes: int) -> bytes:
        try:
            with tempfile.TemporaryDirectory() as d:
                self._api.dataset_download_file(ref.path, name, path=d, force=True, quiet=True)
                raw, zipped = os.path.join(d, name), os.path.join(d, name + ".zip")
                if os.path.exists(zipped):
                    return _read_one_from_zip(zipped, name, max_bytes)
                with open(raw, "rb") as fh:
                    data = fh.read()
        except KaggleAccessError:
            raise
        except Exception as exc:                            # noqa: BLE001
            raise KaggleAccessError(str(exc)) from exc
        if len(data) > max_bytes:
            raise KaggleAccessError(f"file exceeds {max_bytes} bytes")
        return data


_client = None      # cached real client
_override = None    # test-injected fake


def set_client(fake) -> None:
    """Inject a fake (any object with list_files / file_size / download_file). Pass None to reset."""
    global _override
    _override = fake


def get_client():
    """The active client — the injected fake if set, else a lazily-built authenticated real one.

    Call only after `credentials_present()` is True (the real client authenticates on construction).
    """
    global _client
    if _override is not None:
        return _override
    if _client is None:
        _client = _RealKaggleClient()
    return _client

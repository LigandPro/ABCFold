"""Content-addressed MSA cache.

Unpaired MSAs are keyed by sha256 of (source, options, sequence). Paired MSAs
depend on the partner chains, so they are keyed by the ordered tuple of all
protein sequences of the complex plus the chain's index in that tuple.
"""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
import time
from pathlib import Path
from typing import Dict, Optional, Sequence

DEFAULT_CACHE_DIR = "~/.cache/abcfold/msa"


def normalize_sequence(sequence: str) -> str:
    return "".join(sequence.split()).upper()


def msa_cache_key(sequence: str, source: str = "server", options: str = "") -> str:
    payload = f"{source}\x1f{options}\x1f{normalize_sequence(sequence)}"
    return hashlib.sha256(payload.encode()).hexdigest()


def paired_cache_key(
    sequences: Sequence[str], index: int, source: str = "server", options: str = ""
) -> str:
    joined = "\x1e".join(normalize_sequence(s) for s in sequences)
    payload = f"paired\x1f{source}\x1f{options}\x1f{index}\x1f{joined}"
    return hashlib.sha256(payload.encode()).hexdigest()


class MsaCache:
    def __init__(self, cache_dir: Optional[os.PathLike | str] = None):
        self.root = Path(cache_dir or DEFAULT_CACHE_DIR).expanduser()

    def _dir(self, key: str) -> Path:
        return self.root / key[:2] / key

    def get(self, key: str) -> Optional[str]:
        path = self._dir(key) / "msa.a3m"
        if path.exists():
            return path.read_text()
        return None

    def meta(self, key: str) -> Optional[Dict]:
        path = self._dir(key) / "meta.json"
        return json.loads(path.read_text()) if path.exists() else None

    def put(self, key: str, a3m: str, meta: Optional[Dict] = None) -> Path:
        """Atomically store an MSA (safe for concurrent writers)."""
        target = self._dir(key)
        target.mkdir(parents=True, exist_ok=True)
        for name, text in (
            ("msa.a3m", a3m),
            ("meta.json", json.dumps({"created": time.time(), **(meta or {})})),
        ):
            fd, tmp = tempfile.mkstemp(dir=target, prefix=f".{name}.")
            with os.fdopen(fd, "w") as handle:
                handle.write(text)
            os.replace(tmp, target / name)
        return target / "msa.a3m"

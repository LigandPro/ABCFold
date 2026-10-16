"""Resolve MSAs for an AF3-format input from one of several sources.

Sources:
  server  ColabFold MMseqs2 API (cached by sequence hash)
  custom  user-provided A3M files per chain
  af3     a precomputed AlphaFold 3 data-pipeline JSON (``*_data.json``)
  none    single-sequence mode (empty MSAs for every backend)
  auto    reuse MSAs already present in the input, otherwise leave it untouched

The result is written into the AF3 JSON fields (``unpairedMsa``, ``pairedMsa``,
``templates``) from which every backend converter derives its native format.
"""

from __future__ import annotations

import copy
import json
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

from abcfold.msa.cache import MsaCache, msa_cache_key, normalize_sequence, \
    paired_cache_key
from abcfold.msa.colabfold import DEFAULT_URL, ColabFoldClient
from abcfold.msa.formats import parse_a3m
from abcfold.msa.stats import msa_chain_stats

logger = logging.getLogger("logger")

SOURCES = ("auto", "server", "custom", "af3", "none")


@dataclass
class MsaOptions:
    source: str = "auto"
    cache_dir: Optional[str] = None
    server_url: str = DEFAULT_URL
    user_agent: str = "abcfold"
    paired: bool = True
    use_env: bool = True
    custom_a3m: Dict[str, str] = field(default_factory=dict)
    custom_paired_a3m: Dict[str, str] = field(default_factory=dict)
    af3_data_json: Optional[str] = None


@dataclass
class MsaResult:
    params: dict
    source: str
    seconds: float
    chains: Dict[str, dict]


def _ids(entity: dict) -> List[str]:
    ids = entity.get("id", [])
    return [ids] if isinstance(ids, str) else list(ids)


def protein_entities(params: dict) -> List[dict]:
    return [s["protein"] for s in params.get("sequences", []) if "protein" in s]


def _ensure_af3_fields(protein: dict) -> None:
    protein.setdefault("unpairedMsa", "")
    protein.setdefault("pairedMsa", "")
    if protein.get("templates") is None:
        protein["templates"] = []


def parse_chain_paths(items: Optional[Sequence[str]]) -> Dict[str, str]:
    """Parse ``CHAIN=path`` items (``path`` alone applies to every chain: '*')."""
    out: Dict[str, str] = {}
    for item in items or []:
        if "=" in item:
            chain, path = item.split("=", 1)
            for c in chain.split(","):
                out[c.strip()] = path
        else:
            out["*"] = item
    return out


def load_af3_data_json(path: str | Path) -> dict:
    path = Path(path)
    if path.is_dir():
        found = sorted(path.rglob("*_data.json"))
        if not found:
            raise FileNotFoundError(f"No *_data.json under {path}")
        path = found[0]
    return json.loads(path.read_text())


def _stats_for(params: dict, source: str, seconds: Dict[str, float],
               cached: Dict[str, bool]) -> Dict[str, dict]:
    stats: Dict[str, dict] = {}
    for protein in protein_entities(params):
        seq = normalize_sequence(protein["sequence"])
        for chain in _ids(protein):
            stats[chain] = msa_chain_stats(
                protein.get("unpairedMsa"),
                protein.get("pairedMsa"),
                query_length=len(seq),
                source=source,
                seconds=seconds.get(seq, 0.0),
                cached=cached.get(seq, False),
            )
    return stats


def resolve_msas(
    input_params: dict,
    options: MsaOptions,
    client: Optional[ColabFoldClient] = None,
) -> MsaResult:
    params = copy.deepcopy(input_params)
    proteins = protein_entities(params)
    source = options.source
    start = time.monotonic()
    seconds: Dict[str, float] = {}
    cached: Dict[str, bool] = {}

    if source not in SOURCES:
        raise ValueError(f"Unknown MSA source '{source}', expected one of {SOURCES}")

    if source == "auto":
        if proteins and all(p.get("unpairedMsa") is not None for p in proteins):
            for p in proteins:
                _ensure_af3_fields(p)
            return MsaResult(params, "input", 0.0, _stats_for(params, "input", {}, {}))
        return MsaResult(params, "backend", 0.0, {})

    if source == "none":
        for p in proteins:
            p["unpairedMsa"] = ""
            p["pairedMsa"] = ""
            p["templates"] = p.get("templates") or []
        return MsaResult(params, "none", 0.0, _stats_for(params, "none", {}, {}))

    if source == "custom":
        for p in proteins:
            path = next(
                (options.custom_a3m[c] for c in _ids(p) if c in options.custom_a3m),
                options.custom_a3m.get("*"),
            )
            if path is None and p.get("unpairedMsa") is None:
                raise ValueError(
                    f"No custom A3M given for protein chain(s) {_ids(p)}"
                )
            if path is not None:
                text = Path(path).expanduser().read_text()
                records = parse_a3m(text)
                if not records:
                    raise ValueError(f"Custom A3M {path} has no sequences")
                query = normalize_sequence(records[0][1].replace("-", ""))
                if query != normalize_sequence(p["sequence"]):
                    raise ValueError(
                        f"First sequence of {path} does not match chain(s) {_ids(p)}"
                    )
                p["unpairedMsa"] = text
            paired_path = next(
                (options.custom_paired_a3m[c] for c in _ids(p)
                 if c in options.custom_paired_a3m),
                None,
            )
            if paired_path is not None:
                p["pairedMsa"] = Path(paired_path).expanduser().read_text()
            _ensure_af3_fields(p)
        elapsed = time.monotonic() - start
        return MsaResult(params, "custom", elapsed,
                         _stats_for(params, "custom", {}, {}))

    if source == "af3":
        if not options.af3_data_json:
            raise ValueError("MSA source 'af3' needs --af3_data_json")
        data = load_af3_data_json(options.af3_data_json)
        by_seq = {
            normalize_sequence(p["sequence"]): p for p in protein_entities(data)
        }
        for p in proteins:
            match = by_seq.get(normalize_sequence(p["sequence"]))
            if match is None:
                raise ValueError(
                    f"AF3 data JSON has no MSA for chain(s) {_ids(p)}"
                )
            for key in ("unpairedMsa", "pairedMsa", "templates"):
                if match.get(key) is not None:
                    p[key] = match[key]
            _ensure_af3_fields(p)
        # RNA MSAs from the AF3 pipeline are reused as well
        rna_by_seq = {
            normalize_sequence(s["rna"]["sequence"]): s["rna"]
            for s in data.get("sequences", []) if "rna" in s
        }
        for s in params.get("sequences", []):
            if "rna" in s:
                match = rna_by_seq.get(normalize_sequence(s["rna"]["sequence"]))
                if match and match.get("unpairedMsa") is not None:
                    s["rna"]["unpairedMsa"] = match["unpairedMsa"]
        elapsed = time.monotonic() - start
        return MsaResult(params, "af3", elapsed, _stats_for(params, "af3", {}, {}))

    # source == "server"
    cache = MsaCache(options.cache_dir)
    client = client or ColabFoldClient(options.server_url, options.user_agent)
    opts = f"{options.server_url.rstrip('/')}|env={int(options.use_env)}"
    unique = list(dict.fromkeys(normalize_sequence(p["sequence"]) for p in proteins))

    unpaired: Dict[str, str] = {}
    missing: List[str] = []
    for seq in unique:
        hit = cache.get(msa_cache_key(seq, "server", opts))
        if hit is not None:
            unpaired[seq] = hit
            cached[seq] = True
        else:
            missing.append(seq)
    if missing:
        logger.info("Fetching unpaired MSAs for %d sequence(s) from %s",
                    len(missing), options.server_url)
        t0 = time.monotonic()
        fetched = client.unpaired(missing, use_env=options.use_env)
        per_seq = (time.monotonic() - t0) / len(missing)
        for seq, a3m in zip(missing, fetched):
            unpaired[seq] = a3m
            seconds[seq] = per_seq
            cached[seq] = False
            cache.put(msa_cache_key(seq, "server", opts), a3m,
                      {"kind": "unpaired", "source": "server", "options": opts,
                       "sequence": seq})

    paired: Dict[str, str] = {}
    if options.paired and len(unique) > 1:
        keys = [paired_cache_key(unique, i, "server", opts) for i in range(len(unique))]
        hits = [cache.get(k) for k in keys]
        if all(h is not None for h in hits):
            paired = dict(zip(unique, hits))  # type: ignore[arg-type]
        else:
            logger.info("Fetching paired MSAs for %d chains", len(unique))
            t0 = time.monotonic()
            fetched = client.paired(unique)
            share = (time.monotonic() - t0) / len(unique)
            for i, (seq, a3m) in enumerate(zip(unique, fetched)):
                paired[seq] = a3m
                seconds[seq] = seconds.get(seq, 0.0) + share
                cache.put(keys[i], a3m, {"kind": "paired", "source": "server",
                                         "options": opts, "complex": unique})

    for p in proteins:
        seq = normalize_sequence(p["sequence"])
        p["unpairedMsa"] = unpaired[seq]
        p["pairedMsa"] = paired.get(seq, "")
        if p.get("templates") is None:
            p["templates"] = []
    elapsed = time.monotonic() - start
    return MsaResult(params, "server", elapsed,
                     _stats_for(params, "server", seconds, cached))


def prefetch_unique_sequences(
    sequences: Sequence[str], options: MsaOptions,
    client: Optional[ColabFoldClient] = None,
) -> Tuple[int, int]:
    """Fill the cache for many sequences with a single server request.

    Returns (number fetched, number already cached).
    """
    cache = MsaCache(options.cache_dir)
    opts = f"{options.server_url.rstrip('/')}|env={int(options.use_env)}"
    unique = list(dict.fromkeys(normalize_sequence(s) for s in sequences))
    missing = [s for s in unique if cache.get(msa_cache_key(s, "server", opts)) is None]
    if missing:
        client = client or ColabFoldClient(options.server_url, options.user_agent)
        for seq, a3m in zip(missing, client.unpaired(missing, options.use_env)):
            cache.put(msa_cache_key(seq, "server", opts), a3m,
                      {"kind": "unpaired", "source": "server", "options": opts,
                       "sequence": seq})
    return len(missing), len(unique) - len(missing)

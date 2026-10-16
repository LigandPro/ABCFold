"""MSA statistics written to ``msa_stats.json``."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Optional

from abcfold.msa.formats import aligned_columns, parse_a3m

MAX_BINS = 200
SCHEMA = "abcfold-msa-stats-v1"


def bin_values(values: List[int], max_bins: int = MAX_BINS) -> List[float]:
    """Average ``values`` into at most ``max_bins`` contiguous bins."""
    n = len(values)
    if n <= max_bins:
        return [float(v) for v in values]
    out = []
    for b in range(max_bins):
        start = b * n // max_bins
        end = (b + 1) * n // max_bins
        chunk = values[start:end]
        out.append(round(sum(chunk) / len(chunk), 3))
    return out


def msa_chain_stats(
    unpaired: Optional[str],
    paired: Optional[str] = None,
    query_length: Optional[int] = None,
    source: str = "none",
    seconds: float = 0.0,
    cached: bool = False,
) -> Dict:
    """Depth and per-position coverage for one chain.

    depth: number of sequences (query included) in the unpaired MSA plus the
    non-gap paired rows. coverage: number of non-gap residues per query column,
    averaged into at most 200 bins.
    """
    rows = [aligned_columns(s) for _, s in parse_a3m(unpaired)]
    paired_rows = [
        aligned_columns(s) for _, s in parse_a3m(paired)
        if set(aligned_columns(s)) - {"-"}
    ]
    length = query_length or (len(rows[0]) if rows else (
        len(paired_rows[0]) if paired_rows else 0))
    coverage = [0] * length
    for row in rows + paired_rows:
        for i, c in enumerate(row[:length]):
            if c != "-":
                coverage[i] += 1
    return {
        "source": source,
        "depth": len(rows),
        "paired_depth": len(paired_rows),
        "query_length": length,
        "coverage": bin_values(coverage),
        "coverage_bins": min(length, MAX_BINS),
        "seconds": round(float(seconds), 3),
        "cached": cached,
    }


def write_msa_stats(path: Path, chains: Dict[str, Dict], source: str,
                    seconds: float) -> Dict:
    data = {
        "schema": SCHEMA,
        "source": source,
        "seconds": round(float(seconds), 3),
        "chains": chains,
    }
    Path(path).write_text(json.dumps(data, indent=2))
    return data

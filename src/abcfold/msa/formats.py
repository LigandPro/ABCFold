"""A3M helpers and conversions into backend-native MSA formats."""

from __future__ import annotations

from typing import List, Optional, Tuple

# Boltz limits (boltz.data.const)
BOLTZ_MAX_PAIRED_SEQS = 8192
BOLTZ_MAX_MSA_SEQS = 16384


def parse_a3m(text: Optional[str]) -> List[Tuple[str, str]]:
    """Return ``[(header, sequence), ...]`` from an A3M string (no '>' in headers).

    Sequence lines of one record are concatenated. ``#`` comment lines and
    null bytes (ColabFold separators) are skipped.
    """
    records: List[Tuple[str, str]] = []
    if not text:
        return records
    header: Optional[str] = None
    seq_parts: List[str] = []
    for raw in text.replace("\x00", "").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith(">"):
            if header is not None:
                records.append((header, "".join(seq_parts)))
            header = line[1:]
            seq_parts = []
        else:
            seq_parts.append(line)
    if header is not None:
        records.append((header, "".join(seq_parts)))
    return records


def format_a3m(records: List[Tuple[str, str]]) -> str:
    return "".join(f">{h}\n{s}\n" for h, s in records)


def aligned_columns(sequence: str) -> str:
    """Drop A3M insertions (lowercase letters and '.') -> query-aligned row."""
    return "".join(c for c in sequence if not (c.islower() or c == "."))


def is_gap_row(sequence: str) -> bool:
    return set(aligned_columns(sequence)) <= {"-"}


def a3m_to_boltz_csv(unpaired: Optional[str], paired: Optional[str] = None) -> str:
    """Convert A3M MSAs into Boltz's ``key,sequence`` CSV.

    Paired rows get their row index as key (same key across chains = paired);
    unpaired rows get key -1. Mirrors ``boltz.main.compute_msa``.
    """
    keys: List[int] = []
    seqs: List[str] = []
    paired_rows = [s for _, s in parse_a3m(paired)][:BOLTZ_MAX_PAIRED_SEQS]
    for idx, seq in enumerate(paired_rows):
        if not is_gap_row(seq):
            keys.append(idx)
            seqs.append(seq)
    unpaired_rows = [s for _, s in parse_a3m(unpaired)]
    if seqs:
        unpaired_rows = unpaired_rows[1:]  # the query is already the first paired row
    unpaired_rows = unpaired_rows[: max(0, BOLTZ_MAX_MSA_SEQS - len(seqs))]
    keys += [-1] * len(unpaired_rows)
    seqs += unpaired_rows
    lines = ["key,sequence"] + [f"{k},{s}" for k, s in zip(keys, seqs)]
    return "\n".join(lines) + "\n"


def chai_msa_frame(unpaired: Optional[str], paired: Optional[str] = None):
    """Build Chai-1's aligned-parquet table from A3M strings.

    Follows ``chai_lab.data.dataset.msas.colabfold``: paired rows carry their
    row index as ``pairing_key``; unpaired rows not already present get "".
    """
    import pandas as pd

    paired_records = [
        (h, s) for h, s in parse_a3m(paired) if not is_gap_row(s)
    ]
    paired_keys = [str(i) for i, (_, s) in enumerate(parse_a3m(paired))
                   if not is_gap_row(s)]
    paired_seqs = {s for _, s in paired_records}
    unpaired_records = [
        (h, s)
        for i, (h, s) in enumerate(parse_a3m(unpaired))
        if (i > 0 or not paired_records) and not is_gap_row(s) and s not in paired_seqs
    ]
    records = paired_records + unpaired_records
    keys = paired_keys + [""] * len(unpaired_records)
    if not records:
        return pd.DataFrame(
            columns=["sequence", "source_database", "pairing_key", "comment"]
        )
    sources = ["query"] + [
        "uniref90" if h.startswith("UniRef") else "bfd_uniclust"
        for h, _ in records[1:]
    ]
    return pd.DataFrame(
        {
            "sequence": [s for _, s in records],
            "source_database": sources,
            "pairing_key": keys,
            "comment": "",
        }
    )

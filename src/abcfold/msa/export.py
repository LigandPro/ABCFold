"""Write resolved MSAs in each backend's native layout (``abcfold msa --format``)."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Dict, Iterable, List

from abcfold.msa.formats import a3m_to_boltz_csv, chai_msa_frame
from abcfold.msa.resolve import protein_entities

FORMATS = ("boltz", "chai1", "protenix", "openfold3")


def _chains(params: dict):
    for protein in protein_entities(params):
        ids = protein.get("id", [])
        for chain in [ids] if isinstance(ids, str) else ids:
            yield chain, protein


def export_boltz(params: dict, out_dir: Path) -> List[Path]:
    """One file per chain: ``<chain>.csv`` when paired rows exist, else ``.a3m``."""
    out_dir.mkdir(parents=True, exist_ok=True)
    written = []
    for chain, protein in _chains(params):
        unpaired, paired = protein.get("unpairedMsa"), protein.get("pairedMsa")
        if paired:
            path = out_dir / f"{chain}.csv"
            path.write_text(a3m_to_boltz_csv(unpaired, paired))
        else:
            path = out_dir / f"{chain}.a3m"
            path.write_text(unpaired or "")
        written.append(path)
    return written


def export_chai(params: dict, out_dir: Path) -> List[Path]:
    """Chai-1 ``<sha256(seq)>.aligned.pqt`` files (the name Chai looks up)."""
    out_dir.mkdir(parents=True, exist_ok=True)
    written = []
    seen = set()
    for _, protein in _chains(params):
        seq = protein["sequence"].upper()
        if seq in seen:
            continue
        seen.add(seq)
        frame = chai_msa_frame(protein.get("unpairedMsa"), protein.get("pairedMsa"))
        if frame.empty:
            continue
        path = out_dir / f"{hashlib.sha256(seq.encode()).hexdigest()}.aligned.pqt"
        frame.to_parquet(path)
        written.append(path)
    return written


def _write_pair(out_dir: Path, main_name: str, paired_name: str, protein: dict
                ) -> List[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    written = []
    main = out_dir / main_name
    main.write_text(protein.get("unpairedMsa") or "")
    written.append(main)
    if protein.get("pairedMsa"):
        paired = out_dir / paired_name
        paired.write_text(protein["pairedMsa"])
        written.append(paired)
    return written


def export_protenix(params: dict, out_dir: Path) -> List[Path]:
    written: List[Path] = []
    for chain, protein in _chains(params):
        written += _write_pair(out_dir / chain, "non_pairing.a3m", "pairing.a3m",
                               protein)
    return written


def export_openfold3(params: dict, out_dir: Path) -> List[Path]:
    written: List[Path] = []
    for chain, protein in _chains(params):
        written += _write_pair(out_dir / chain, "colabfold_main.a3m",
                               "colabfold_paired.a3m", protein)
    return written


EXPORTERS = {
    "boltz": export_boltz,
    "chai1": export_chai,
    "protenix": export_protenix,
    "openfold3": export_openfold3,
}


def export_msas(params: dict, out_dir: Path, formats: Iterable[str]
                ) -> Dict[str, List[Path]]:
    result = {}
    for fmt in formats:
        if fmt not in EXPORTERS:
            raise ValueError(f"Unknown MSA format {fmt!r}, expected {FORMATS}")
        result[fmt] = EXPORTERS[fmt](params, Path(out_dir) / fmt)
    return result

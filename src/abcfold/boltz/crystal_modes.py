"""Helpers for Boltz crystal-conditioned ABCFold modes."""

from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

import numpy as np
from Bio.PDB.MMCIFParser import MMCIFParser
from Bio.PDB.PDBParser import PDBParser

MODE_DEFAULT = "default"
MODE_TEMPLATE = "template"
MODE_CONSTRAINED = "constrained"

MODE_ALIASES = {
    "default": MODE_DEFAULT,
    "none": MODE_DEFAULT,
    "predict": MODE_DEFAULT,
    "1": MODE_DEFAULT,
    "2": MODE_TEMPLATE,
    "template": MODE_TEMPLATE,
    "template_dock": MODE_TEMPLATE,
    "crystal_template": MODE_TEMPLATE,
    "3": MODE_CONSTRAINED,
    "constrained": MODE_CONSTRAINED,
    "constrained_dock": MODE_CONSTRAINED,
    "crystal_constrained": MODE_CONSTRAINED,
}


def normalize_boltz_mode(mode: str | None) -> str:
    """Normalize user-facing Boltz mode aliases."""
    if mode is None:
        return MODE_DEFAULT
    normalized = MODE_ALIASES.get(mode.lower())
    if normalized is None:
        valid = ", ".join(sorted(MODE_ALIASES))
        raise ValueError(f"Unsupported Boltz mode '{mode}'. Valid modes: {valid}")
    return normalized


def apply_crystal_mode(
    input_params: dict[str, Any],
    mode: str,
    crystal_structure: Path | None,
    ligand_chain: str | None = None,
    template_chain_id: list[str] | None = None,
    template_id: list[str] | None = None,
    template_force: bool = False,
    template_threshold: float = 2.0,
    pocket_radius: float = 6.0,
    pocket_max_distance: float = 6.0,
    pocket_force: bool = False,
) -> dict[str, Any]:
    """Return input parameters augmented with Boltz crystal conditioning."""
    mode = normalize_boltz_mode(mode)
    if mode == MODE_DEFAULT:
        return input_params
    if crystal_structure is None:
        raise ValueError(f"Boltz mode '{mode}' requires --boltz_crystal_structure.")

    crystal_structure = crystal_structure.expanduser().resolve()
    if not crystal_structure.exists():
        raise FileNotFoundError(f"Crystal structure not found: {crystal_structure}")

    augmented = copy.deepcopy(input_params)
    augmented.setdefault("templates", []).append(
        _template_entry(
            crystal_structure,
            template_chain_id,
            template_id,
            force=template_force or mode == MODE_CONSTRAINED,
            threshold=template_threshold,
        )
    )

    if ligand_chain:
        contacts = pocket_contacts_from_structure(
            crystal_structure,
            ligand_chain=ligand_chain,
            radius=pocket_radius,
        )
        augmented.setdefault("constraints", []).append(
            {
                "pocket": {
                    "binder": ligand_chain,
                    "contacts": contacts,
                    "max_distance": pocket_max_distance,
                    "force": pocket_force or mode == MODE_CONSTRAINED,
                }
            }
        )
    elif mode == MODE_CONSTRAINED:
        raise ValueError(
            "Boltz constrained mode requires --boltz_ligand_chain so ABCFold can "
            "derive pocket constraints from the crystal structure."
        )

    return augmented


def pocket_contacts_from_structure(
    structure_path: Path,
    ligand_chain: str,
    radius: float = 6.0,
) -> list[list[str | int]]:
    """Find protein residues within ``radius`` Angstrom of a ligand chain."""
    if radius <= 0:
        raise ValueError("Pocket radius must be greater than 0.")

    structure = _read_structure(structure_path)
    model = structure[0]
    if ligand_chain not in model:
        raise ValueError(
            f"Ligand chain '{ligand_chain}' not found in {structure_path}."
        )

    ligand_atoms = [
        atom
        for residue in model[ligand_chain]
        if residue.id[0] != " "
        for atom in residue
    ]
    if not ligand_atoms:
        raise ValueError(
            f"Chain '{ligand_chain}' in {structure_path} does not contain ligand atoms."
        )

    ligand_coords = np.array([atom.coord for atom in ligand_atoms], dtype=float)
    contacts: list[list[str | int]] = []
    radius_sq = radius * radius
    for chain in model:
        protein_residues = [residue for residue in chain if residue.id[0] == " "]
        for residue_index, residue in enumerate(protein_residues, start=1):
            residue_coords = np.array([atom.coord for atom in residue], dtype=float)
            if residue_coords.size == 0:
                continue
            diffs = residue_coords[:, None, :] - ligand_coords[None, :, :]
            if np.any(np.sum(diffs * diffs, axis=-1) <= radius_sq):
                contacts.append([chain.id, residue_index])

    if not contacts:
        raise ValueError(
            f"No protein residues within {radius:g} A of ligand chain "
            f"'{ligand_chain}' in {structure_path}."
        )
    return contacts


def _template_entry(
    structure_path: Path,
    chain_id: list[str] | None,
    template_id: list[str] | None,
    force: bool,
    threshold: float,
) -> dict[str, Any]:
    suffix = structure_path.suffix.lower()
    if suffix == ".pdb":
        path_key = "pdb"
    elif suffix in {".cif", ".mmcif"}:
        path_key = "cif"
    else:
        raise ValueError(
            "Boltz crystal templates must be .pdb, .cif, or .mmcif files: "
            f"{structure_path}"
        )

    entry: dict[str, Any] = {path_key: str(structure_path)}
    if chain_id:
        entry["chain_id"] = _scalar_or_list(chain_id)
    if template_id:
        entry["template_id"] = _scalar_or_list(template_id)
    if force:
        entry["force"] = True
        entry["threshold"] = threshold
    return entry


def _scalar_or_list(values: list[str]) -> str | list[str]:
    return values[0] if len(values) == 1 else values


def _read_structure(path: Path):
    suffix = path.suffix.lower()
    if suffix == ".pdb":
        return PDBParser(QUIET=True).get_structure(path.stem, str(path))
    if suffix in {".cif", ".mmcif"}:
        return MMCIFParser(QUIET=True).get_structure(path.stem, str(path))
    raise ValueError(f"Unsupported crystal structure suffix: {path.suffix}")

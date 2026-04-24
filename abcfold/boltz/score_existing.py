"""Score existing complexes with Boltz2 confidence and optional affinity heads.

This module intentionally bypasses Boltz diffusion sampling. It parses one or
more ready PDB/mmCIF complexes, featurizes them with Boltz2, runs the trunk plus
confidence module with ``skip_run_structure=True``, and writes score files.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import Any


SUMMARY_KEYS = [
    "confidence_score",
    "ptm",
    "iptm",
    "ligand_iptm",
    "protein_iptm",
    "complex_plddt",
    "complex_iplddt",
    "complex_pde",
    "complex_ipde",
]

AFFINITY_KEYS = [
    "affinity_pred_value",
    "affinity_probability_binary",
    "affinity_pred_value1",
    "affinity_probability_binary1",
    "affinity_pred_value2",
    "affinity_probability_binary2",
]


@dataclass(frozen=True)
class LigandPose:
    path: Path
    pose_index: int
    mol: Any


def _safe_id(path: Path) -> str:
    """Return a Boltz-safe record id derived from a structure path."""
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", path.stem).strip("_") or "complex"


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="python -m abcfold.boltz.score_existing",
        description="Score existing PDB/mmCIF complexes with Boltz2 confidence.",
    )
    parser.add_argument(
        "structures",
        nargs="+",
        type=Path,
        help=(
            "Existing complex structure files (.cif/.mmcif/.pdb), or ligand "
            "SDF files when --receptor is set."
        ),
    )
    parser.add_argument(
        "--receptor",
        type=Path,
        help=(
            "Protein receptor PDB. When set, positional inputs are ligand SDF "
            "poses scored as receptor-ligand complexes."
        ),
    )
    parser.add_argument(
        "--ligand_chain_id",
        default="L",
        help="Chain id assigned to SDF ligands in --receptor mode.",
    )
    parser.add_argument(
        "--out_dir",
        type=Path,
        default=Path("boltz_existing_scores"),
        help="Directory for confidence JSON/NPZ outputs.",
    )
    parser.add_argument(
        "--cache",
        type=Path,
        default=Path.home() / ".boltz",
        help="Boltz cache containing mols/, boltz2_conf.ckpt, and boltz2_aff.ckpt.",
    )
    parser.add_argument(
        "--affinity",
        action="store_true",
        help=(
            "Also run the Boltz2 affinity head on the provided coordinates. "
            "This uses boltz2_aff.ckpt by default and still skips diffusion."
        ),
    )
    parser.add_argument(
        "--affinity_checkpoint",
        type=Path,
        help="Optional path to a Boltz2 affinity checkpoint.",
    )
    parser.add_argument(
        "--no_affinity_mw_correction",
        action="store_true",
        help="Disable Boltz2 molecular-weight correction for affinity predictions.",
    )
    parser.add_argument(
        "--device",
        choices=["auto", "cpu", "cuda", "mps"],
        default="auto",
        help="Torch device. auto prefers CUDA, then MPS, then CPU.",
    )
    parser.add_argument(
        "--recycling_steps",
        type=int,
        default=0,
        help="Pairformer recycling steps before confidence scoring.",
    )
    parser.add_argument(
        "--reuse_trunk",
        action="store_true",
        help=(
            "Cache trunk embeddings from the first structure and reuse them for "
            "the remaining structures. Only valid for the same target topology."
        ),
    )
    parser.add_argument(
        "--write_full_pae",
        action="store_true",
        help="Write full PAE matrices. Disabled by default to keep screening fast.",
    )
    parser.add_argument(
        "--write_full_pde",
        action="store_true",
        help="Write full PDE matrices. Disabled by default to keep screening fast.",
    )
    parser.add_argument(
        "--use_kernels",
        action="store_true",
        help="Enable optional CUDA kernels if they are installed.",
    )
    parser.add_argument(
        "--no_download",
        action="store_true",
        help="Do not download missing Boltz2 weights or molecule cache.",
    )
    return parser.parse_args(argv)


def _import_boltz() -> dict[str, Any]:
    """Import Boltz only when the scoring command actually runs."""
    import numpy as np
    import torch
    from boltz.data import const
    from boltz.data.feature.featurizerv2 import Boltz2Featurizer
    from boltz.data.mol import load_canonicals, load_molecules
    from boltz.data.module.inferencev2 import collate
    from boltz.data.parse.schema import parse_boltz_schema
    from boltz.data.tokenize.boltz2 import Boltz2Tokenizer
    from boltz.data.types import Coords, Input
    from boltz.main import (
        Boltz2DiffusionParams,
        BoltzSteeringParams,
        MSAModuleArgs,
        PairformerArgsV2,
        download_boltz2,
    )
    from boltz.model.models.boltz2 import Boltz2

    return {
        "np": np,
        "torch": torch,
        "const": const,
        "Boltz2Featurizer": Boltz2Featurizer,
        "load_canonicals": load_canonicals,
        "load_molecules": load_molecules,
        "collate": collate,
        "parse_boltz_schema": parse_boltz_schema,
        "Boltz2Tokenizer": Boltz2Tokenizer,
        "Coords": Coords,
        "Input": Input,
        "Boltz2DiffusionParams": Boltz2DiffusionParams,
        "BoltzSteeringParams": BoltzSteeringParams,
        "MSAModuleArgs": MSAModuleArgs,
        "PairformerArgsV2": PairformerArgsV2,
        "download_boltz2": download_boltz2,
        "Boltz2": Boltz2,
    }


def _select_device(torch: Any, device: str) -> Any:
    if device == "auto":
        if torch.cuda.is_available():
            return torch.device("cuda")
        if getattr(torch.backends, "mps", None) and torch.backends.mps.is_available():
            return torch.device("mps")
        return torch.device("cpu")
    selected = torch.device(device)
    if selected.type == "cuda" and not torch.cuda.is_available():
        raise RuntimeError("CUDA was requested but is not available.")
    if (
        selected.type == "mps"
        and (
            not getattr(torch.backends, "mps", None)
            or not torch.backends.mps.is_available()
        )
    ):
        raise RuntimeError("MPS was requested but is not available.")
    return selected


def _read_bio_structure(path: Path, record_id: str):
    from Bio.PDB.MMCIFParser import MMCIFParser
    from Bio.PDB.PDBParser import PDBParser

    suffix = path.suffix.lower()
    if suffix == ".pdb":
        return PDBParser(QUIET=True).get_structure(record_id, str(path))
    if suffix in {".cif", ".mmcif"}:
        return MMCIFParser(QUIET=True).get_structure(record_id, str(path))
    raise ValueError(f"Unsupported structure suffix for {path}: {path.suffix}")


def _protein_residues(chain: Any, boltz: dict[str, Any]) -> list[Any]:
    protein_tokens = set(boltz["const"].prot_token_to_letter)
    return [
        residue
        for residue in chain
        if residue.id[0] == " " and residue.resname in protein_tokens
    ]


def _ligand_residues(chain: Any) -> list[Any]:
    return [
        residue
        for residue in chain
        if residue.id[0] != " "
    ]


def _schema_from_bio_structure(record_id: str, structure: Any, boltz: dict[str, Any]):
    sequences = []
    model = structure[0]

    for chain in model:
        protein_residues = _protein_residues(chain, boltz)
        if protein_residues:
            sequence = "".join(
                boltz["const"].prot_token_to_letter.get(residue.resname, "X")
                for residue in protein_residues
            )
            sequences.append({
                "protein": {
                    "id": chain.id,
                    "sequence": sequence,
                    "msa": "empty",
                }
            })
            continue

        for residue in _ligand_residues(chain):
            sequences.append({
                "ligand": {
                    "id": chain.id,
                    "ccd": residue.resname,
                }
            })

    if not sequences:
        raise ValueError(f"No supported protein or CCD ligand chains in {record_id}.")

    return {
        "version": 1,
        "sequences": sequences,
    }


def _with_affinity_property(
    schema: dict[str, Any],
    ligand_chain_id: str | None = None,
) -> dict[str, Any]:
    if ligand_chain_id is None:
        ligand_ids = []
        for item in schema["sequences"]:
            ligand = item.get("ligand")
            if ligand is None:
                continue
            ligand_id = ligand["id"]
            if isinstance(ligand_id, str):
                ligand_ids.append(ligand_id)
            else:
                ligand_ids.extend(ligand_id)

        if len(ligand_ids) != 1:
            raise ValueError(
                "Affinity scoring requires exactly one ligand chain unless "
                "--ligand_chain_id identifies the binder."
            )
        ligand_chain_id = ligand_ids[0]

    return {
        **schema,
        "properties": [
            *schema.get("properties", []),
            {"affinity": {"binder": ligand_chain_id}},
        ],
    }


def _protein_schema_items_from_bio_structure(
    record_id: str,
    structure: Any,
    boltz: dict[str, Any],
) -> list[dict[str, Any]]:
    sequences = []
    model = structure[0]

    for chain in model:
        protein_residues = _protein_residues(chain, boltz)
        if not protein_residues:
            continue

        sequence = "".join(
            boltz["const"].prot_token_to_letter.get(residue.resname, "X")
            for residue in protein_residues
        )
        sequences.append({
            "protein": {
                "id": chain.id,
                "sequence": sequence,
                "msa": "empty",
            }
        })

    if not sequences:
        raise ValueError(f"No supported protein chains in receptor {record_id}.")

    return sequences


def _coords_by_chain_residue(residues: list[Any]) -> list[dict[str, Any]]:
    residue_coords = []
    for residue in residues:
        atom_coords = {
            atom.name.strip(): tuple(float(x) for x in atom.coord)
            for atom in residue
        }
        residue_coords.append(atom_coords)
    return residue_coords


def _transfer_coordinates(
    target_structure: Any,
    bio_structure: Any,
    boltz: dict[str, Any],
):
    model = bio_structure[0]
    atoms = target_structure.atoms.copy()
    coords_data = []

    for chain in target_structure.chains:
        chain_name = str(chain["name"])
        if chain_name not in model:
            raise ValueError(f"Structure is missing chain {chain_name}.")

        bio_chain = model[chain_name]
        if int(chain["mol_type"]) == boltz["const"].chain_type_ids["NONPOLYMER"]:
            source_residues = _ligand_residues(bio_chain)
        else:
            source_residues = _protein_residues(bio_chain, boltz)

        res_start = int(chain["res_idx"])
        res_end = res_start + int(chain["res_num"])
        target_residues = target_structure.residues[res_start:res_end]
        if len(source_residues) != len(target_residues):
            raise ValueError(
                f"Chain {chain_name} residue count mismatch: "
                f"{len(source_residues)} in structure, "
                f"{len(target_residues)} in target."
            )

        source_coords = _coords_by_chain_residue(source_residues)
        for residue, atom_lookup in zip(target_residues, source_coords):
            atom_start = int(residue["atom_idx"])
            atom_end = atom_start + int(residue["atom_num"])
            for atom_idx in range(atom_start, atom_end):
                atom_name = str(atoms[atom_idx]["name"]).strip()
                coords = atom_lookup.get(atom_name)
                if coords is None:
                    atoms[atom_idx]["coords"] = (0.0, 0.0, 0.0)
                    atoms[atom_idx]["is_present"] = False
                else:
                    atoms[atom_idx]["coords"] = coords
                    atoms[atom_idx]["is_present"] = True

    coords_data = [(coord,) for coord in atoms["coords"]]
    coords = boltz["np"].array(coords_data, dtype=boltz["Coords"])
    return replace(target_structure, atoms=atoms, coords=coords)


def _transfer_receptor_ligand_coordinates(
    target_structure: Any,
    receptor_structure: Any,
    ligand_coords_by_chain: dict[str, dict[str, tuple[float, float, float]]],
    boltz: dict[str, Any],
):
    model = receptor_structure[0]
    atoms = target_structure.atoms.copy()
    nonpolymer_type = boltz["const"].chain_type_ids["NONPOLYMER"]

    for chain in target_structure.chains:
        chain_name = str(chain["name"])
        res_start = int(chain["res_idx"])
        res_end = res_start + int(chain["res_num"])
        target_residues = target_structure.residues[res_start:res_end]

        if int(chain["mol_type"]) == nonpolymer_type:
            atom_lookup = ligand_coords_by_chain.get(chain_name)
            if atom_lookup is None:
                raise ValueError(f"Missing ligand coordinates for chain {chain_name}.")
            if len(target_residues) != 1:
                raise ValueError(
                    f"Only single-residue SDF ligands are supported; "
                    f"chain {chain_name} has {len(target_residues)} residues."
                )
            residue_coord_blocks = [atom_lookup]
        else:
            if chain_name not in model:
                raise ValueError(f"Receptor is missing chain {chain_name}.")
            source_residues = _protein_residues(model[chain_name], boltz)
            if len(source_residues) != len(target_residues):
                raise ValueError(
                    f"Chain {chain_name} residue count mismatch: "
                    f"{len(source_residues)} in receptor, "
                    f"{len(target_residues)} in target."
                )
            residue_coord_blocks = _coords_by_chain_residue(source_residues)

        for residue, atom_lookup in zip(target_residues, residue_coord_blocks):
            atom_start = int(residue["atom_idx"])
            atom_end = atom_start + int(residue["atom_num"])
            for atom_idx in range(atom_start, atom_end):
                atom_name = str(atoms[atom_idx]["name"]).strip()
                coords = atom_lookup.get(atom_name)
                if coords is None:
                    atoms[atom_idx]["coords"] = (0.0, 0.0, 0.0)
                    atoms[atom_idx]["is_present"] = False
                else:
                    atoms[atom_idx]["coords"] = coords
                    atoms[atom_idx]["is_present"] = True

    coords_data = [(coord,) for coord in atoms["coords"]]
    coords = boltz["np"].array(coords_data, dtype=boltz["Coords"])
    return replace(target_structure, atoms=atoms, coords=coords)


def _read_sdf_poses(path: Path) -> list[LigandPose]:
    from rdkit import Chem

    if path.suffix.lower() != ".sdf":
        raise ValueError(f"--receptor mode expects SDF ligand poses, got {path}.")

    supplier = Chem.SDMolSupplier(str(path), sanitize=True, removeHs=False)
    poses = [
        LigandPose(path=path, pose_index=idx, mol=mol)
        for idx, mol in enumerate(supplier, start=1)
        if mol is not None
    ]
    if not poses:
        raise ValueError(f"No readable ligand poses in {path}.")

    for pose in poses:
        if pose.mol.GetNumConformers() == 0:
            raise ValueError(f"Ligand pose {path}#{pose.pose_index} has no conformer.")
    return poses


def _smiles_from_ligand_mol(mol: Any) -> str:
    from rdkit import Chem

    mol_no_h = Chem.RemoveHs(Chem.Mol(mol), sanitize=False)
    return Chem.MolToSmiles(mol_no_h, isomericSmiles=True)


def _ligand_coords_by_atom_name(
    source_mol: Any,
    target_mol: Any,
) -> dict[str, tuple[float, float, float]]:
    from rdkit import Chem

    source_no_h = Chem.RemoveHs(Chem.Mol(source_mol), sanitize=False)
    match = source_no_h.GetSubstructMatch(target_mol, useChirality=False)
    if not match:
        source_no_h = Chem.RemoveHs(Chem.Mol(source_mol), sanitize=True)
        match = source_no_h.GetSubstructMatch(target_mol, useChirality=False)
    if not match:
        raise ValueError("Could not map SDF ligand atoms onto the Boltz ligand.")
    if len(match) != target_mol.GetNumAtoms():
        raise ValueError("Incomplete SDF ligand atom mapping.")

    conformer = source_no_h.GetConformer()
    atom_coords = {}
    for target_idx, source_idx in enumerate(match):
        target_atom = target_mol.GetAtomWithIdx(target_idx)
        atom_name = target_atom.GetProp("name")
        pos = conformer.GetAtomPosition(source_idx)
        atom_coords[atom_name] = (float(pos.x), float(pos.y), float(pos.z))
    return atom_coords


def _ligand_target_mol(target: Any, ligand_chain_id: str) -> Any:
    for chain in target.structure.chains:
        if str(chain["name"]) != ligand_chain_id:
            continue
        res_idx = int(chain["res_idx"])
        res_name = str(target.structure.residues[res_idx]["name"])
        return target.extra_mols[res_name]
    raise ValueError(f"Target is missing ligand chain {ligand_chain_id}.")


def _target_from_structure(
    path: Path,
    mols: dict[str, Any],
    mol_dir: Path,
    boltz: dict[str, Any],
    compute_affinity: bool,
) -> Any:
    record_id = _safe_id(path)
    bio_structure = _read_bio_structure(path, record_id)
    schema = _schema_from_bio_structure(record_id, bio_structure, boltz)
    if compute_affinity:
        schema = _with_affinity_property(schema)
    target = boltz["parse_boltz_schema"](
        record_id,
        schema,
        mols,
        str(mol_dir),
        True,
    )
    structure = _transfer_coordinates(target.structure, bio_structure, boltz)
    return replace(target, structure=structure)


def _target_from_receptor_ligand(
    record_id: str,
    receptor_structure: Any,
    ligand_pose: LigandPose,
    ligand_chain_id: str,
    mols: dict[str, Any],
    mol_dir: Path,
    boltz: dict[str, Any],
    compute_affinity: bool,
) -> Any:
    schema = {
        "version": 1,
        "sequences": [
            *_protein_schema_items_from_bio_structure(
                record_id,
                receptor_structure,
                boltz,
            ),
            {
                "ligand": {
                    "id": ligand_chain_id,
                    "smiles": _smiles_from_ligand_mol(ligand_pose.mol),
                }
            },
        ],
    }
    if compute_affinity:
        schema = _with_affinity_property(schema, ligand_chain_id)
    target = boltz["parse_boltz_schema"](
        record_id,
        schema,
        mols,
        str(mol_dir),
        True,
    )
    ligand_coords = _ligand_coords_by_atom_name(
        ligand_pose.mol,
        _ligand_target_mol(target, ligand_chain_id),
    )
    structure = _transfer_receptor_ligand_coordinates(
        target.structure,
        receptor_structure,
        {ligand_chain_id: ligand_coords},
        boltz,
    )
    return replace(target, structure=structure)


def _features_from_structure(
    structure_path: Path,
    tokenizer: Any,
    featurizer: Any,
    canonical_mols: dict[str, Any],
    mol_dir: Path,
    boltz: dict[str, Any],
    compute_affinity: bool,
) -> tuple[dict[str, Any], str]:
    record_id = _safe_id(structure_path)
    target = _target_from_structure(
        structure_path,
        canonical_mols.copy(),
        mol_dir,
        boltz,
        compute_affinity,
    )

    input_data = boltz["Input"](
        target.structure,
        {},
        record=target.record,
        residue_constraints=target.residue_constraints,
        templates=target.templates,
        extra_mols=target.extra_mols,
    )
    tokenized = tokenizer.tokenize(input_data)

    molecules = {}
    molecules.update(canonical_mols)
    mol_names = set(tokenized.tokens["res_name"].tolist()) - set(molecules)
    if mol_names:
        molecules.update(boltz["load_molecules"](str(mol_dir), sorted(mol_names)))

    features = featurizer.process(
        tokenized,
        molecules=molecules,
        random=boltz["np"].random.default_rng(42),
        training=False,
        max_atoms=None,
        max_tokens=None,
        max_seqs=boltz["const"].max_msa_seqs,
        pad_to_max_seqs=False,
        single_sequence_prop=0.0,
        compute_frames=True,
        inference_pocket_constraints=None,
        inference_contact_constraints=None,
        compute_constraint_features=True,
        compute_affinity=compute_affinity,
    )
    features["record"] = target.record
    return features, record_id


def _features_from_ligand_pose(
    ligand_pose: LigandPose,
    receptor_structure: Any,
    ligand_chain_id: str,
    tokenizer: Any,
    featurizer: Any,
    canonical_mols: dict[str, Any],
    mol_dir: Path,
    boltz: dict[str, Any],
    compute_affinity: bool,
) -> tuple[dict[str, Any], str]:
    record_id = _safe_id(ligand_pose.path)
    if ligand_pose.pose_index > 1:
        record_id = f"{record_id}_pose{ligand_pose.pose_index}"
    target = _target_from_receptor_ligand(
        record_id,
        receptor_structure,
        ligand_pose,
        ligand_chain_id,
        canonical_mols.copy(),
        mol_dir,
        boltz,
        compute_affinity,
    )

    input_data = boltz["Input"](
        target.structure,
        {},
        record=target.record,
        residue_constraints=target.residue_constraints,
        templates=target.templates,
        extra_mols=target.extra_mols,
    )
    tokenized = tokenizer.tokenize(input_data)

    molecules = {}
    molecules.update(canonical_mols)
    molecules.update(target.extra_mols)
    mol_names = set(tokenized.tokens["res_name"].tolist()) - set(molecules)
    if mol_names:
        molecules.update(boltz["load_molecules"](str(mol_dir), sorted(mol_names)))

    features = featurizer.process(
        tokenized,
        molecules=molecules,
        random=boltz["np"].random.default_rng(42),
        training=False,
        max_atoms=None,
        max_tokens=None,
        max_seqs=boltz["const"].max_msa_seqs,
        pad_to_max_seqs=False,
        single_sequence_prop=0.0,
        compute_frames=True,
        inference_pocket_constraints=None,
        inference_contact_constraints=None,
        compute_constraint_features=True,
        compute_affinity=compute_affinity,
    )
    features["record"] = target.record
    return features, record_id


def _load_model(args: argparse.Namespace, device: Any, boltz: dict[str, Any]) -> Any:
    checkpoint = (
        args.affinity_checkpoint
        if args.affinity_checkpoint is not None
        else args.cache / ("boltz2_aff.ckpt" if args.affinity else "boltz2_conf.ckpt")
    )
    checkpoint = checkpoint.expanduser().resolve()
    if not checkpoint.exists():
        raise FileNotFoundError(
            f"Boltz2 checkpoint not found: {checkpoint}. "
            "Run without --no_download or provide --cache."
        )

    torch = boltz["torch"]
    diffusion_params = boltz["Boltz2DiffusionParams"]()
    pairformer_args = boltz["PairformerArgsV2"]()
    msa_args = boltz["MSAModuleArgs"](
        subsample_msa=False,
        num_subsampled_msa=boltz["const"].max_msa_seqs,
        use_paired_feature=True,
    )
    steering_args = boltz["BoltzSteeringParams"]()
    use_kernels = args.use_kernels and (
        device.type == "cuda"
        and torch.cuda.get_device_properties(device).major >= 8
    )
    model = boltz["Boltz2"].load_from_checkpoint(
        checkpoint,
        strict=True,
        predict_args={},
        map_location="cpu",
        diffusion_process_args=asdict(diffusion_params),
        ema=False,
        use_kernels=use_kernels,
        pairformer_args=asdict(pairformer_args),
        msa_args=asdict(msa_args),
        steering_args=asdict(steering_args),
        affinity_mw_correction=not args.no_affinity_mw_correction,
        skip_run_structure=True,
    )
    if args.affinity:
        if not hasattr(model, "affinity_module") and not hasattr(
            model,
            "affinity_module1",
        ):
            raise RuntimeError(
                f"Checkpoint does not expose a Boltz2 affinity head: {checkpoint}"
            )
        # Boltz2.forward expects diffusion-produced sample_atom_coords for its
        # built-in affinity path. This CLI scores externally supplied coords, so
        # affinity is called explicitly after the no-diffusion forward pass.
        model.affinity_prediction = False
    model.eval()
    model.to(device)
    return model


def _batch_to_device(batch: dict[str, Any], device: Any, torch: Any) -> dict[str, Any]:
    moved = {}
    for key, value in batch.items():
        moved[key] = value.to(device) if isinstance(value, torch.Tensor) else value
    return moved


def _batch_signature(batch: dict[str, Any]) -> str:
    """Create a topology signature used to guard trunk reuse."""
    hasher = hashlib.sha256()
    for key in ["res_type", "asym_id", "mol_type", "token_pad_mask", "atom_pad_mask"]:
        value = batch[key].detach().cpu().contiguous()
        hasher.update(key.encode())
        hasher.update(str(tuple(value.shape)).encode())
        hasher.update(value.numpy().tobytes())

    atom_to_token = batch["atom_to_token"].detach().cpu().argmax(dim=-1).contiguous()
    hasher.update(b"atom_to_token_argmax")
    hasher.update(str(tuple(atom_to_token.shape)).encode())
    hasher.update(atom_to_token.numpy().tobytes())
    return hasher.hexdigest()


def _confidence_from_cached_trunk(
    model: Any,
    batch: dict[str, Any],
    cached: dict[str, Any],
) -> dict[str, Any]:
    s_inputs = model.input_embedder(batch)
    out = model.confidence_module(
        s_inputs=s_inputs.detach(),
        s=cached["s"].detach(),
        z=cached["z"].detach(),
        x_pred=batch["coords"].repeat_interleave(1, 0),
        feats=batch,
        pred_distogram_logits=cached["pdistogram"][:, :, :, 0].detach(),
        multiplicity=1,
        run_sequentially=True,
        use_kernels=model.use_kernels,
    )
    out.update({
        "s": cached["s"],
        "z": cached["z"],
        "pdistogram": cached["pdistogram"],
    })
    return out


def _affinity_from_existing_coords(
    model: Any,
    batch: dict[str, Any],
    out: dict[str, Any],
    torch: Any,
) -> dict[str, Any]:
    if "affinity_token_mask" not in batch:
        raise ValueError(
            "Affinity features are missing. Build features with compute_affinity=True."
        )

    pad_token_mask = batch["token_pad_mask"][0]
    rec_mask = (batch["mol_type"][0] == 0) * pad_token_mask
    lig_mask = batch["affinity_token_mask"][0].to(torch.bool) * pad_token_mask
    cross_pair_mask = (
        lig_mask[:, None] * rec_mask[None, :]
        + rec_mask[:, None] * lig_mask[None, :]
        + lig_mask[:, None] * lig_mask[None, :]
    )
    z_affinity = out["z"] * cross_pair_mask[None, :, :, None]
    coords_affinity = batch["coords"].detach()
    if coords_affinity.ndim == 3:
        coords_affinity = coords_affinity[:, None]
    if coords_affinity.ndim != 4:
        raise ValueError(
            f"Expected coordinate tensor with 3 or 4 dimensions, got "
            f"{tuple(coords_affinity.shape)}."
        )

    s_inputs = model.input_embedder(batch, affinity=True)
    if getattr(model, "affinity_ensemble", False):
        dict_out_affinity1 = model.affinity_module1(
            s_inputs=s_inputs.detach(),
            z=z_affinity.detach(),
            x_pred=coords_affinity,
            feats=batch,
            multiplicity=1,
            use_kernels=model.use_kernels,
        )
        dict_out_affinity2 = model.affinity_module2(
            s_inputs=s_inputs.detach(),
            z=z_affinity.detach(),
            x_pred=coords_affinity,
            feats=batch,
            multiplicity=1,
            use_kernels=model.use_kernels,
        )
        dict_out_affinity1["affinity_probability_binary"] = torch.sigmoid(
            dict_out_affinity1["affinity_logits_binary"]
        )
        dict_out_affinity2["affinity_probability_binary"] = torch.sigmoid(
            dict_out_affinity2["affinity_logits_binary"]
        )
        affinity_out = {
            "affinity_pred_value": (
                dict_out_affinity1["affinity_pred_value"]
                + dict_out_affinity2["affinity_pred_value"]
            )
            / 2,
            "affinity_probability_binary": (
                dict_out_affinity1["affinity_probability_binary"]
                + dict_out_affinity2["affinity_probability_binary"]
            )
            / 2,
            "affinity_pred_value1": dict_out_affinity1["affinity_pred_value"],
            "affinity_probability_binary1": dict_out_affinity1[
                "affinity_probability_binary"
            ],
            "affinity_pred_value2": dict_out_affinity2["affinity_pred_value"],
            "affinity_probability_binary2": dict_out_affinity2[
                "affinity_probability_binary"
            ],
        }
        if getattr(model, "affinity_mw_correction", False):
            model_coef = 1.03525938
            mw_coef = -0.59992683
            bias = 2.83288489
            mw = batch["affinity_mw"][0] ** 0.3
            affinity_out["affinity_pred_value"] = (
                model_coef * affinity_out["affinity_pred_value"] + mw_coef * mw + bias
            )
        return affinity_out

    dict_out_affinity = model.affinity_module(
        s_inputs=s_inputs.detach(),
        z=z_affinity.detach(),
        x_pred=coords_affinity,
        feats=batch,
        multiplicity=1,
        use_kernels=model.use_kernels,
    )
    return {
        "affinity_pred_value": dict_out_affinity["affinity_pred_value"],
        "affinity_probability_binary": torch.sigmoid(
            dict_out_affinity["affinity_logits_binary"]
        ),
    }


def _scalar(out: dict[str, Any], key: str) -> float:
    value = out[key]
    if hasattr(value, "detach"):
        value = value.detach().float().cpu().reshape(-1)
        return float(value[0].item())
    return float(value)


def _confidence_summary(out: dict[str, Any], torch: Any) -> dict[str, float]:
    iptm = out["iptm"]
    ptm = out["ptm"]
    ranking_term = iptm if not torch.allclose(iptm, torch.zeros_like(iptm)) else ptm
    confidence_score = (4 * out["complex_plddt"] + ranking_term) / 5
    scored = {
        key: _scalar(out, key)
        for key in SUMMARY_KEYS
        if key != "confidence_score"
    }
    scored["confidence_score"] = float(
        confidence_score.detach().float().cpu().reshape(-1)[0].item()
    )
    return {key: scored[key] for key in SUMMARY_KEYS}


def _affinity_summary(out: dict[str, Any]) -> dict[str, float]:
    return {
        key: _scalar(out, key)
        for key in AFFINITY_KEYS
        if key in out
    }


def _serialise_pair_chains_iptm(value: Any) -> Any:
    if hasattr(value, "detach"):
        return value.detach().float().cpu().tolist()
    if isinstance(value, dict):
        return {
            str(k): _serialise_pair_chains_iptm(v)
            for k, v in value.items()
        }
    return value


def _write_outputs(
    out_dir: Path,
    record_id: str,
    source_path: Path,
    summary: dict[str, float],
    out: dict[str, Any],
    write_full_pae: bool,
    write_full_pde: bool,
) -> dict[str, Any]:
    import numpy as np

    record_dir = out_dir / record_id
    record_dir.mkdir(parents=True, exist_ok=True)

    json_payload = {
        "source_structure": str(source_path),
        **summary,
        "pair_chains_iptm": _serialise_pair_chains_iptm(
            out.get("pair_chains_iptm", {})
        ),
    }
    confidence_path = record_dir / f"confidence_{record_id}.json"
    confidence_path.write_text(json.dumps(json_payload, indent=4))

    plddt = out["plddt"].detach().float().cpu().numpy()
    np.savez_compressed(record_dir / f"plddt_{record_id}.npz", plddt=plddt)

    if write_full_pae and "pae" in out:
        pae = out["pae"].detach().float().cpu().numpy()
        np.savez_compressed(record_dir / f"pae_{record_id}.npz", pae=pae)
    if write_full_pde and "pde" in out:
        pde = out["pde"].detach().float().cpu().numpy()
        np.savez_compressed(record_dir / f"pde_{record_id}.npz", pde=pde)

    if "affinity_pred_value" in summary:
        affinity_payload = {
            key: summary[key]
            for key in AFFINITY_KEYS
            if key in summary
        }
        affinity_path = record_dir / f"affinity_{record_id}.json"
        affinity_path.write_text(json.dumps(affinity_payload, indent=4))
    else:
        affinity_path = None

    return {
        "structure": str(source_path),
        "record_id": record_id,
        **summary,
        "confidence_json": str(confidence_path),
        **({"affinity_json": str(affinity_path)} if affinity_path else {}),
    }


def score_existing_complexes(args: argparse.Namespace) -> list[dict[str, Any]]:
    boltz = _import_boltz()
    torch = boltz["torch"]
    device = _select_device(torch, args.device)
    args.cache = args.cache.expanduser().resolve()
    args.cache.mkdir(parents=True, exist_ok=True)
    mol_dir = args.cache / "mols"
    if not args.no_download:
        boltz["download_boltz2"](args.cache)
    if not mol_dir.exists():
        raise FileNotFoundError(
            f"Boltz2 molecule cache not found: {mol_dir}. "
            "Run without --no_download or provide --cache."
        )

    args.out_dir.mkdir(parents=True, exist_ok=True)
    canonical_mols = boltz["load_canonicals"](str(mol_dir))
    tokenizer = boltz["Boltz2Tokenizer"]()
    featurizer = boltz["Boltz2Featurizer"]()
    model = _load_model(args, device, boltz)
    receptor_structure = None
    if args.receptor is not None:
        args.receptor = args.receptor.expanduser().resolve()
        receptor_structure = _read_bio_structure(args.receptor, "receptor")

    rows = []
    trunk_cache = None
    trunk_signature = None
    seen_record_ids: dict[str, int] = {}
    with torch.inference_mode():
        for input_path in args.structures:
            input_path = input_path.expanduser().resolve()
            if receptor_structure is None:
                feature_inputs: list[Path | LigandPose] = [input_path]
            else:
                feature_inputs = _read_sdf_poses(input_path)

            for feature_input in feature_inputs:
                source_path = (
                    feature_input.path
                    if isinstance(feature_input, LigandPose)
                    else feature_input
                )
                torch.manual_seed(0)
                if torch.cuda.is_available():
                    torch.cuda.manual_seed_all(0)
                if isinstance(feature_input, LigandPose):
                    assert receptor_structure is not None
                    features, record_id = _features_from_ligand_pose(
                        feature_input,
                        receptor_structure,
                        args.ligand_chain_id,
                        tokenizer,
                        featurizer,
                        canonical_mols,
                        mol_dir,
                        boltz,
                        args.affinity,
                    )
                else:
                    features, record_id = _features_from_structure(
                        feature_input,
                        tokenizer,
                        featurizer,
                        canonical_mols,
                        mol_dir,
                        boltz,
                        args.affinity,
                    )
                batch = boltz["collate"]([features])
                batch = _batch_to_device(batch, device, torch)
                signature = _batch_signature(batch)
                if args.reuse_trunk and trunk_cache is not None:
                    if signature != trunk_signature:
                        raise ValueError(
                            "--reuse_trunk requires all structures to have the same "
                            "token and atom topology as the first structure."
                        )
                    out = _confidence_from_cached_trunk(model, batch, trunk_cache)
                else:
                    out = model(
                        batch,
                        recycling_steps=args.recycling_steps,
                        num_sampling_steps=None,
                        diffusion_samples=1,
                        max_parallel_samples=None,
                        run_confidence_sequentially=True,
                    )
                    if args.reuse_trunk and trunk_cache is None:
                        trunk_cache = {
                            "s": out["s"],
                            "z": out["z"],
                            "pdistogram": out["pdistogram"],
                        }
                        trunk_signature = signature
                summary = _confidence_summary(out, torch)
                if args.affinity:
                    affinity_out = _affinity_from_existing_coords(
                        model,
                        batch,
                        out,
                        torch,
                    )
                    out.update(affinity_out)
                    summary.update(_affinity_summary(out))

                seen_count = seen_record_ids.get(record_id, 0)
                seen_record_ids[record_id] = seen_count + 1
                output_id = (
                    record_id if seen_count == 0 else f"{record_id}_{seen_count}"
                )
                rows.append(
                    _write_outputs(
                        args.out_dir,
                        output_id,
                        source_path,
                        summary,
                        out,
                        args.write_full_pae,
                        args.write_full_pde,
                    )
                )

    summary_path = args.out_dir / "scores.csv"
    with summary_path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    return rows


def main(argv: list[str] | None = None) -> None:
    args = _parse_args(argv)
    rows = score_existing_complexes(args)
    print(f"Wrote scores for {len(rows)} structures to {args.out_dir / 'scores.csv'}")


if __name__ == "__main__":
    main()

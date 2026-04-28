# Boltz Existing-Structure Scoring

`abcfold.boltz.score_existing` scores already-built complexes with Boltz2
without running Boltz diffusion sampling. Use it when protein or complex
coordinates already exist and you want Boltz2 confidence and, optionally,
Boltz2 affinity estimates for those coordinates.

This is a scoring utility, not a structure-generation or local-minimization
tool. It does not move the protein or ligand.

## What It Computes

By default, the command writes Boltz2 confidence metrics:

- `confidence_score`
- `ptm`
- `iptm`
- `ligand_iptm`
- `protein_iptm`
- `complex_plddt`
- `complex_iplddt`
- `complex_pde`
- `complex_ipde`

With `--affinity`, it also writes Boltz2 affinity outputs from
`boltz2_aff.ckpt`:

- `affinity_pred_value`
- `affinity_probability_binary`
- `affinity_pred_value1`
- `affinity_probability_binary1`
- `affinity_pred_value2`
- `affinity_probability_binary2`

The affinity mode uses the supplied coordinates directly. It does not run
diffusion to generate `sample_atom_coords`.

## Score Ready PDB or mmCIF Complexes

Use this mode when each input file already contains the protein and ligand
chains in one `.pdb`, `.cif`, or `.mmcif` file.

```bash
abcfold-score-existing \
  complex_1.cif complex_2.cif \
  --out_dir boltz_existing_scores \
  --cache ~/.boltz \
  --device cuda \
  --no_download
```

For affinity estimates on the same coordinates:

```bash
abcfold-score-existing \
  complex_1.cif complex_2.cif \
  --out_dir boltz_existing_scores_affinity \
  --cache ~/.boltz \
  --device cuda \
  --no_download \
  --affinity
```

Affinity scoring for ready complex files currently requires exactly one ligand
chain unless a future wrapper identifies the binder explicitly.

## Score Receptor PDB Plus Ligand SDF Poses

Use this mode for docking-style outputs where the receptor is fixed and ligand
poses are stored as SDF files. This is the format used by DEKOIS2/Matcha-style
and HEDGEHOG-style pose scoring.

```bash
abcfold-score-existing \
  poses.sdf \
  --receptor receptor.pdb \
  --out_dir boltz_pose_scores \
  --cache ~/.boltz \
  --device cuda \
  --no_download
```

For confidence plus affinity:

```bash
abcfold-score-existing \
  poses.sdf \
  --receptor receptor.pdb \
  --out_dir boltz_pose_scores_affinity \
  --cache ~/.boltz \
  --device cuda \
  --no_download \
  --affinity
```

If several SDF files are provided, each readable conformer is scored. The
ligand is represented from the SDF molecule, while the receptor coordinates are
read from the receptor PDB.

## Reusing the Trunk

`--reuse_trunk` caches the first trunk output and reuses it for later inputs.
This is only valid when all scored structures have the same token and atom
topology, for example multiple poses of the same ligand against the same
protein.

```bash
abcfold-score-existing \
  same_ligand_poses.sdf \
  --receptor receptor.pdb \
  --out_dir boltz_pose_scores_reuse \
  --cache ~/.boltz \
  --device cuda \
  --no_download \
  --affinity \
  --reuse_trunk
```

Do not use `--reuse_trunk` for different ligands. The command checks the input
topology and fails if later structures do not match the first one.

## Outputs

The output directory contains:

- `scores.csv`: one summary row per scored structure or pose.
- `<record_id>/confidence_<record_id>.json`: confidence metrics and
  pair-chain `ipTM`.
- `<record_id>/plddt_<record_id>.npz`: compressed pLDDT array.
- `<record_id>/affinity_<record_id>.json`: affinity outputs when `--affinity`
  is enabled.
- Optional `pae_*.npz` and `pde_*.npz` files when `--write_full_pae` or
  `--write_full_pde` is enabled.

## Runtime Notes

The command avoids the expensive Boltz diffusion sampling path, so it is faster
than full Boltz structure prediction. It still loads the Boltz2 checkpoint and
runs the trunk, so the first score is not instantaneous. On GPU, scoring
additional poses in the same process is much cheaper than the cold start.

The utility currently sets protein MSAs to `empty`, so proteins are scored in
single-sequence mode. That is useful for fast pose screening, but confidence and
affinity values should be calibrated against the intended benchmark before
using them as final decision metrics.

## Required Cache Files

The default cache is `~/.boltz`. For confidence scoring, it must contain:

- `mols/`
- `boltz2_conf.ckpt`

For `--affinity`, it must also contain:

- `boltz2_aff.ckpt`

Omit `--no_download` if the cache should be populated automatically by Boltz.

For development checkouts, the equivalent module command is:

```bash
python -m abcfold.boltz.score_existing --help
```

# Boltz Crystal-Pocket Docking

`abcfold.boltz.dock_crystal` runs Boltz structure generation with a fixed
crystal receptor as a template, a ligand SMILES, and pocket constraints. Use it
when you know the receptor structure and pocket, but want Boltz to generate the
ligand pose instead of only scoring an existing pose.

This is a Boltz-native docking/co-folding mode. It is not a classical force
field minimizer: Boltz still runs diffusion sampling, but the protein is guided
toward the crystal template and the ligand is guided into the pocket.

## Explicit Pocket Residues

```bash
abcfold-dock-crystal \
  crystal_receptor.pdb \
  "CCOc1ccc(...)" \
  --protein_chain A \
  --pocket_residue A:145 \
  --pocket_residue A:146 \
  --pocket_residue A:189 \
  --out_dir boltz_crystal_dock \
  --affinity
```

`--pocket_residue` uses PDB residue numbering by default. The wrapper converts
those residues to the sequence indices required by Boltz constraints. Use
`--pocket_numbering sequence` if the input numbers are already Boltz sequence
indices.

## Infer Pocket From a Crystal Ligand

If the receptor PDB still contains a reference ligand chain, the wrapper can
infer pocket residues by distance:

```bash
abcfold-dock-crystal \
  crystal_complex.pdb \
  "CCOc1ccc(...)" \
  --protein_chain A \
  --reference_ligand_chain L \
  --pocket_cutoff 6.0 \
  --out_dir boltz_crystal_dock \
  --affinity
```

Only protein chains are written to the Boltz sequence section. The reference
ligand is used to choose pocket residues; the docked ligand still comes from
the SMILES argument.

## Template and Pocket Strength

By default, the generated YAML includes:

- `templates.force: true`
- `templates.threshold: 1.0`
- `constraints.pocket.force: true`
- `constraints.pocket.max_distance: 6.0`

These settings keep the protein close to the crystal receptor and steer the
ligand into the pocket. They can be relaxed:

```bash
abcfold-dock-crystal \
  crystal_receptor.pdb \
  "CCOc1ccc(...)" \
  --pocket_residue A:145 \
  --template_threshold 2.0 \
  --max_distance 8.0
```

Use `--no_force_template` or `--no_force_pocket` only when you want Boltz to be
less constrained.

## Accuracy and Runtime

This mode runs Boltz diffusion, so it is much slower than
`abcfold.boltz.score_existing`, which only scores supplied coordinates. The
default docking settings use:

- `--diffusion_samples 25`
- `--recycling_steps 10`
- `--sampling_steps 200`
- `--use_potentials`

For a quick dry run that only writes the Boltz YAML and command:

```bash
abcfold-dock-crystal \
  crystal_receptor.pdb \
  "CCOc1ccc(...)" \
  --pocket_residue A:145 \
  --dry_run
```

The output directory contains:

- `boltz_crystal_dock.yaml`
- `boltz_crystal_dock_command.json`
- Boltz prediction outputs when `--dry_run` is not used

Use `--use_msa_server` to let Boltz fetch MSAs. Without it, the wrapper writes
`msa: empty` for speed and offline execution.

For development checkouts, the equivalent module command is:

```bash
python -m abcfold.boltz.dock_crystal --help
```

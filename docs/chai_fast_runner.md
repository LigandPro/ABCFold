# Chai Fast Runner

ABCFold runs Chai-1 through the fast runner by default when `--chai1` is set.
There is no separate `--chai_fast` flag.

The fast runner prepares the same Chai FASTA, MSA directory, and constraints as
the standard runner, then executes seed jobs through persistent worker
processes. This avoids repeated process setup overhead and lets ABCFold assign
jobs across the requested `--gpus` device slots.

## Usage

```bash
uv run abcfold input.json output_dir --chai1 --gpus 0,1
```

Use `--gpus all` to let Chai choose CUDA, `--gpus cpu` for CPU execution, or a
comma-separated list such as `--gpus 0,1` to split seed jobs across devices.

## Output Layout

For a normal ABCFold run, the fast runner preserves the existing Chai output
layout:

- `chai_output_seed-<seed>/`
- `pred.model_idx_<n>.cif`
- `scores.model_idx_<n>.npz`
- ABCFold post-processing and visualization outputs

Batch helper calls can also write native nested output directories under
`outputs/<case_id>/chai_output_seed-<seed>/` for downstream export workflows.

## Quality Settings

The fast runner does not lower Chai quality settings. It forwards:

- `--number_of_models` to Chai diffusion sample count.
- `--num_recycles` to Chai trunk recycle count.
- 200 diffusion timesteps, matching the existing ABCFold Chai runner.

The speedup comes from orchestration and worker reuse, not from reducing model
quality.

from __future__ import annotations

import importlib.util
from pathlib import Path

import numpy as np


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "export_rnp_calc.py"
SPEC = importlib.util.spec_from_file_location("export_rnp_calc", SCRIPT)
export_rnp_calc = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(export_rnp_calc)


def write_chai_prediction(root: Path, case_id: str, seed: int, model: int) -> None:
    seed_dir = root / "outputs" / case_id / f"chai1_{case_id}" / f"chai_output_seed-{seed}"
    seed_dir.mkdir(parents=True, exist_ok=True)
    (seed_dir / f"pred.model_idx_{model}.cif").write_text("data_test\n")
    np.savez(seed_dir / f"scores.model_idx_{model}.npz", aggregate_score=0.7, ptm=0.6, iptm=0.5)


def test_export_chai_skips_cases_below_min_predictions(tmp_path: Path) -> None:
    write_chai_prediction(tmp_path, "case_a", seed=1, model=0)
    write_chai_prediction(tmp_path, "case_b", seed=1, model=0)
    write_chai_prediction(tmp_path, "case_b", seed=1, model=1)

    cases, predictions = export_rnp_calc.export_chai(tmp_path, min_predictions_per_case=2)

    assert cases == 1
    assert predictions == 2
    assert (tmp_path / "rnp_calc" / "outputs" / "case_b").is_dir()
    assert not (tmp_path / "rnp_calc" / "outputs" / "case_a").exists()
    assert sum(1 for _ in (tmp_path / "rnp_calc" / "all_scores.csv").open()) == 3


def test_export_chai_removes_empty_compat_case(tmp_path: Path) -> None:
    (tmp_path / "outputs" / "case_a" / "chai1_case_a").mkdir(parents=True)

    cases, predictions = export_rnp_calc.export_chai(tmp_path)

    assert cases == 0
    assert predictions == 0
    assert not (tmp_path / "rnp_calc" / "outputs" / "case_a").exists()

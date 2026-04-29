from __future__ import annotations

import csv
import importlib.util
import json
from pathlib import Path

import numpy as np

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "export_rnp_calc.py"
SPEC = importlib.util.spec_from_file_location("export_rnp_calc", SCRIPT)
assert SPEC is not None
export_rnp_calc = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(export_rnp_calc)


def write_boltz_batch_prediction(
    root: Path, case_id: str, seed: int, model: int, confidence_score: float
) -> tuple[Path, Path]:
    pred_dir = (
        root
        / "boltz_batch"
        / f"seed-{seed}"
        / f"boltz_results_seed-{seed}"
        / "predictions"
        / f"{case_id}_seed-{seed}"
    )
    pred_dir.mkdir(parents=True, exist_ok=True)
    cif_path = pred_dir / f"{case_id}_seed-{seed}_model_{model}.cif"
    score_path = pred_dir / f"confidence_{case_id}_seed-{seed}_model_{model}.json"
    cif_path.write_text("data_test\n")
    score_path.write_text(json.dumps({"confidence_score": confidence_score}))
    return cif_path, score_path


def write_chai_prediction(root: Path, case_id: str, seed: int, model: int) -> None:
    seed_dir = (
        root / "outputs" / case_id / f"chai1_{case_id}" / f"chai_output_seed-{seed}"
    )
    seed_dir.mkdir(parents=True, exist_ok=True)
    (seed_dir / f"pred.model_idx_{model}.cif").write_text("data_test\n")
    np.savez(
        seed_dir / f"scores.model_idx_{model}.npz",
        aggregate_score=0.7,
        ptm=0.6,
        iptm=0.5,
    )


def test_export_chai_skips_cases_below_min_predictions(tmp_path: Path) -> None:
    write_chai_prediction(tmp_path, "case_a", seed=1, model=0)
    write_chai_prediction(tmp_path, "case_b", seed=1, model=0)
    write_chai_prediction(tmp_path, "case_b", seed=1, model=1)

    cases, predictions = export_rnp_calc.export_chai(
        tmp_path, min_predictions_per_case=2
    )

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


def test_export_boltz_batch_layout(tmp_path: Path) -> None:
    write_boltz_batch_prediction(
        tmp_path, "case_one", seed=1, model=0, confidence_score=0.71
    )
    case_one_best = write_boltz_batch_prediction(
        tmp_path, "case_one", seed=1, model=1, confidence_score=0.95
    )
    write_boltz_batch_prediction(
        tmp_path, "case_two", seed=1, model=0, confidence_score=0.82
    )

    cases, predictions = export_rnp_calc.export_boltz(tmp_path)

    assert cases == 2
    assert predictions == 3
    assert (tmp_path / "rnp_calc" / "outputs" / "case_one").is_dir()
    assert (tmp_path / "rnp_calc" / "outputs" / "case_two").is_dir()

    case_one_backend = (
        tmp_path / "rnp_calc" / "outputs" / "case_one" / "boltz-1_CASE_ONE"
    )
    case_two_backend = (
        tmp_path / "rnp_calc" / "outputs" / "case_two" / "boltz-1_CASE_TWO"
    )

    assert case_one_backend.is_dir()
    assert (case_one_backend / "seed_1").is_dir()
    assert (case_one_backend / "seed_1" / "boltz_results_case_one_data").is_symlink()
    assert (case_one_backend / "best_model.cif").is_symlink()
    assert (case_one_backend / "all_scores.csv").is_file()
    assert (case_one_backend / "timing.log").is_file()
    assert (case_two_backend / "best_model.cif").is_symlink()
    assert (case_two_backend / "all_scores.csv").is_file()

    best_model_target = case_one_backend / "best_model.cif"
    assert best_model_target.resolve() == (
        tmp_path
        / "boltz_batch"
        / "seed-1"
        / "boltz_results_seed-1"
        / "predictions"
        / "case_one_seed-1"
        / "case_one_seed-1_model_1.cif"
    )
    expected_best_selection = "seed=1\nmodel=1\nconfidence_score=0.95\n"
    assert (
        (case_one_backend / "best_selection.txt")
        .read_text()
        .startswith(expected_best_selection)
    )

    all_scores = list(csv.DictReader((tmp_path / "rnp_calc" / "all_scores.csv").open()))
    assert len(all_scores) == 3
    case_one_rows = [row for row in all_scores if row["id"] == "case_one"]
    case_two_rows = [row for row in all_scores if row["id"] == "case_two"]
    assert len(case_one_rows) == 2
    assert len(case_two_rows) == 1
    assert float(case_one_rows[0]["confidence_score"]) < float(
        case_one_rows[1]["confidence_score"]
    )

    best_case_one = case_one_rows[1]
    assert best_case_one["model_idx"] == "1"
    assert best_case_one["source_cif_path"] == str(
        case_one_best[0].relative_to(tmp_path)
    )
    assert best_case_one["source_score_path"] == str(
        case_one_best[1].relative_to(tmp_path)
    )

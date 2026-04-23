#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import os
import re
import shutil
from pathlib import Path

BOLTZ_RE = re.compile(r"^(?:abc_)?(?P<id>.+)_seed-(?P<seed>\d+)_model_(?P<model>\d+)\.cif$")
CHAI_RE = re.compile(r"^pred\.model_idx_(?P<model>\d+)\.cif$")
SEED_DIR_RE = re.compile(r"^chai_output_seed-(?P<seed>\d+)$")
AF_SAMPLE_DIR_RE = re.compile(r"^seed-(?P<seed>\d+)_sample-(?P<sample>\d+)$")
PROTENIX_SEED_RE = re.compile(r"^protenix_results_seed-(?P<seed>\d+)$")
PROTENIX_SAMPLE_RE = re.compile(r"^(?P<id>.+)_sample_(?P<sample>\d+)\.cif$")


def json_str(value) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def scalar(value):
    import numpy as np

    if isinstance(value, np.ndarray):
        if value.shape == ():
            return value.item()
        if value.size == 1:
            return value.reshape(-1)[0].item()
        return value.tolist()
    if isinstance(value, np.generic):
        return value.item()
    return value


def safe_unlink(path: Path) -> None:
    if path.exists() or path.is_symlink():
        if path.is_dir() and not path.is_symlink():
            shutil.rmtree(path)
        else:
            path.unlink()


def safe_symlink(target: Path, link_path: Path) -> None:
    safe_unlink(link_path)
    link_path.symlink_to(os.path.relpath(target, link_path.parent))


def prepare_dir(root: Path) -> Path:
    tmp = root / "rnp_calc.__tmp__"
    safe_unlink(tmp)
    tmp.mkdir(parents=True)
    return tmp


def finalize_dir(root: Path, tmp: Path) -> Path:
    final = root / "rnp_calc"
    previous = root / "rnp_calc.__previous__"
    safe_unlink(previous)
    if final.exists() or final.is_symlink():
        final.rename(previous)
    tmp.rename(final)
    safe_unlink(previous)
    all_scores_link = root / "all_scores.csv"
    safe_unlink(all_scores_link)
    all_scores_link.symlink_to("rnp_calc/all_scores.csv")
    return final


def write_rows(csv_path: Path, rows: list[dict]) -> None:
    fieldnames: list[str] = []
    for row in rows:
        for key in row.keys():
            if key not in fieldnames:
                fieldnames.append(key)
    with csv_path.open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_simple_scores(csv_path: Path, rows: list[dict]) -> None:
    with csv_path.open("w", newline="") as fh:
        writer = csv.DictWriter(
            fh,
            fieldnames=["seed", "model", "confidence_score"],
            extrasaction="ignore",
        )
        writer.writeheader()
        writer.writerows(rows)


def write_best_selection(selection_path: Path, best_row: dict) -> None:
    selection_path.write_text(
        "seed={seed}\nmodel={model}\nconfidence_score={confidence_score}\ncif_path={cif_path}\n".format(**best_row)
    )


def touch_summary_log(path: Path, text: str) -> None:
    path.write_text(text)


def score_sort_key(row: dict) -> float:
    value = row.get("confidence_score")
    if value is None:
        return float("-inf")
    return float(value)


def export_boltz(root: Path) -> tuple[int, int]:
    outputs = root / "outputs"
    tmp = prepare_dir(root)
    compat_outputs = tmp / "outputs"
    compat_outputs.mkdir()
    summary_rows: list[dict] = []
    pred_count = 0
    case_count = 0

    for case_dir in sorted(p for p in outputs.iterdir() if p.is_dir()):
        case_id = case_dir.name
        nested_backend_dir = case_dir / f"boltz_{case_id}"
        if nested_backend_dir.exists():
            seed_dirs = sorted(p for p in nested_backend_dir.iterdir() if p.is_dir() and p.name.startswith("boltz_results_"))
        else:
            seed_dirs = sorted(p for p in case_dir.iterdir() if p.is_dir() and p.name.startswith("boltz_results_"))
        if not seed_dirs:
            continue

        case_compat = compat_outputs / case_id
        case_compat.mkdir(parents=True, exist_ok=True)
        src_json = case_dir / f"abc_{case_id}.json"
        if src_json.exists():
            safe_symlink(src_json, case_compat / f"abc_{case_id}_data.json")

        compat_backend = case_compat / f"boltz-1_{case_id.upper()}"
        compat_backend.mkdir()

        case_rows: list[dict] = []
        case_seen = False
        for seed_dir in seed_dirs:
            seed_str = seed_dir.name.split("seed-")[-1]
            try:
                seed = int(seed_str)
            except ValueError:
                continue
            compat_seed_dir = compat_backend / f"seed_{seed}"
            compat_seed_dir.mkdir()
            safe_symlink(seed_dir, compat_seed_dir / f"boltz_results_{case_id}_data")
            pred_dir = seed_dir / "predictions" / f"abc_{case_id}_seed-{seed}"
            if not pred_dir.exists():
                continue
            for cif_path in sorted(pred_dir.glob("*.cif")):
                m = BOLTZ_RE.match(cif_path.name)
                if not m:
                    continue
                model_idx = int(m.group("model"))
                score_path = pred_dir / f"confidence_abc_{case_id}_seed-{seed}_model_{model_idx}.json"
                if not score_path.exists():
                    continue
                score = json.loads(score_path.read_text())
                confidence = score.get("confidence_score")
                compat_cif_path = os.path.relpath(cif_path, compat_backend)
                row = {
                    "backend": "boltz",
                    "id": case_id,
                    "seed": seed,
                    "model_idx": model_idx,
                    "score": confidence,
                    "confidence_score": confidence,
                    "ptm": score.get("ptm"),
                    "iptm": score.get("iptm"),
                    "ligand_iptm": score.get("ligand_iptm"),
                    "protein_iptm": score.get("protein_iptm"),
                    "complex_plddt": score.get("complex_plddt"),
                    "complex_iplddt": score.get("complex_iplddt"),
                    "complex_pde": score.get("complex_pde"),
                    "complex_ipde": score.get("complex_ipde"),
                    "chains_ptm_json": json_str(score.get("chains_ptm", {})),
                    "pair_chains_iptm_json": json_str(score.get("pair_chains_iptm", {})),
                    "cif_name": cif_path.name,
                    "cif_path": compat_cif_path,
                    "source_cif_path": os.path.relpath(cif_path, root),
                    "source_score_path": os.path.relpath(score_path, root),
                }
                summary_rows.append(row)
                case_rows.append({
                    "seed": seed,
                    "model": model_idx,
                    "confidence_score": confidence,
                    "cif_path": compat_cif_path,
                })
                pred_count += 1
                case_seen = True
        if case_seen:
            case_count += 1
            case_rows.sort(key=score_sort_key, reverse=True)
            write_simple_scores(compat_backend / "all_scores.csv", case_rows)
            best = case_rows[0]
            safe_symlink(compat_backend / best["cif_path"], compat_backend / "best_model.cif")
            write_best_selection(compat_backend / "best_selection.txt", best)
            log_src = root / "logs" / f"{case_id}.boltz.log"
            if log_src.exists():
                safe_symlink(log_src, compat_backend / "timing.log")
            else:
                touch_summary_log(compat_backend / "timing.log", "No per-case timing log found.\n")
        else:
            safe_unlink(case_compat)

    summary_rows.sort(key=lambda r: (r["id"], int(r["seed"]), int(r["model_idx"])))
    write_rows(tmp / "all_scores.csv", summary_rows)
    finalize_dir(root, tmp)
    return case_count, pred_count


def export_chai(root: Path, min_predictions_per_case: int = 0) -> tuple[int, int]:
    import numpy as np

    outputs = root / "outputs"
    tmp = prepare_dir(root)
    compat_outputs = tmp / "outputs"
    compat_outputs.mkdir()
    summary_rows: list[dict] = []
    pred_count = 0
    case_count = 0

    for case_dir in sorted(p for p in outputs.iterdir() if p.is_dir()):
        case_id = case_dir.name
        backend_dir = case_dir / f"chai1_{case_id}"
        if not backend_dir.exists():
            continue
        case_compat = compat_outputs / case_id
        case_compat.mkdir(parents=True, exist_ok=True)
        src_json = case_dir / f"abc_{case_id}.json"
        if src_json.exists():
            safe_symlink(src_json, case_compat / f"abc_{case_id}_data.json")

        compat_backend = case_compat / f"chai1_{case_id.upper()}"
        compat_backend.mkdir()

        case_rows: list[dict] = []
        case_summary_rows: list[dict] = []
        case_seen = False
        for seed_dir in sorted(p for p in backend_dir.iterdir() if p.is_dir() and p.name.startswith("chai_output_seed-")):
            seed_match = SEED_DIR_RE.match(seed_dir.name)
            if not seed_match:
                continue
            seed = int(seed_match.group("seed"))
            safe_symlink(seed_dir, compat_backend / f"seed_{seed}")
            for cif_path in sorted(seed_dir.glob("pred.model_idx_*.cif")):
                m = CHAI_RE.match(cif_path.name)
                if not m:
                    continue
                model_idx = int(m.group("model"))
                score_path = seed_dir / f"scores.model_idx_{model_idx}.npz"
                if not score_path.exists():
                    continue
                npz = np.load(score_path)
                score_data = {k: scalar(npz[k]) for k in npz.files}
                confidence = score_data.get("aggregate_score")
                row = {
                    "backend": "chai",
                    "id": case_id,
                    "seed": seed,
                    "model_idx": model_idx,
                    "score": confidence,
                    "aggregate_score": confidence,
                    "ptm": score_data.get("ptm"),
                    "iptm": score_data.get("iptm"),
                    "has_inter_chain_clashes": score_data.get("has_inter_chain_clashes"),
                    "per_chain_ptm_json": json_str(score_data.get("per_chain_ptm", [])),
                    "per_chain_pair_iptm_json": json_str(score_data.get("per_chain_pair_iptm", [])),
                    "chain_chain_clashes_json": json_str(score_data.get("chain_chain_clashes", [])),
                    "cif_name": cif_path.name,
                    "cif_path": os.path.relpath(cif_path, compat_backend),
                    "source_cif_path": os.path.relpath(cif_path, root),
                    "source_score_path": os.path.relpath(score_path, root),
                }
                case_summary_rows.append(row)
                case_rows.append({
                    "seed": seed,
                    "model": model_idx,
                    "confidence_score": confidence,
                    "cif_path": os.path.relpath(cif_path, compat_backend),
                })
                case_seen = True
        if case_seen and len(case_rows) >= min_predictions_per_case:
            case_count += 1
            pred_count += len(case_rows)
            summary_rows.extend(case_summary_rows)
            case_rows.sort(key=score_sort_key, reverse=True)
            write_simple_scores(compat_backend / "all_scores.csv", case_rows)
            best = case_rows[0]
            safe_symlink(compat_backend / best["cif_path"], compat_backend / "best_model.cif")
            write_best_selection(compat_backend / "best_selection.txt", best)
            log_src = root / "logs" / "cases" / f"{case_id}.log"
            if log_src.exists():
                safe_symlink(log_src, compat_backend / "timing.log")
            else:
                touch_summary_log(compat_backend / "timing.log", "No per-case timing log found.\n")
        else:
            safe_unlink(case_compat)

    summary_rows.sort(key=lambda r: (r["id"], int(r["seed"]), int(r["model_idx"])))
    write_rows(tmp / "all_scores.csv", summary_rows)
    finalize_dir(root, tmp)
    return case_count, pred_count


def export_alphafast(root: Path) -> tuple[int, int]:
    runs = root / "runs"
    tmp = prepare_dir(root)
    compat_outputs = tmp / "outputs"
    compat_outputs.mkdir()
    summary_rows: list[dict] = []
    pred_count = 0
    case_count = 0

    for case_dir in sorted(p for p in runs.iterdir() if p.is_dir() and not p.name.startswith("_")):
        case_id = case_dir.name
        ranking_csv = case_dir / f"{case_id}_ranking_scores.csv"
        if not ranking_csv.exists():
            continue
        case_compat = compat_outputs / case_id
        case_compat.mkdir(parents=True, exist_ok=True)
        data_json = case_dir / f"{case_id}_data.json"
        if data_json.exists():
            safe_symlink(data_json, case_compat / f"{case_id}_data.json")

        compat_backend = case_compat / f"alphafold3_{case_id.upper()}"
        compat_backend.mkdir()
        results_dir = compat_backend / "results"
        results_dir.mkdir()

        rank_map: dict[tuple[int, int], float] = {}
        with ranking_csv.open() as fh:
            for row in csv.DictReader(fh):
                rank_map[(int(row["seed"]), int(row["sample"]))] = float(row["ranking_score"])

        case_rows: list[dict] = []
        case_seen = False
        for sample_dir in sorted(p for p in case_dir.iterdir() if p.is_dir()):
            match = AF_SAMPLE_DIR_RE.match(sample_dir.name)
            if not match:
                continue
            seed = int(match.group("seed"))
            sample = int(match.group("sample"))
            model_src = sample_dir / f"{case_id}_seed-{seed}_sample-{sample}_model.cif"
            conf_src = sample_dir / f"{case_id}_seed-{seed}_sample-{sample}_confidences.json"
            summary_src = sample_dir / f"{case_id}_seed-{seed}_sample-{sample}_summary_confidences.json"
            if not model_src.exists():
                continue
            compat_sample_dir = results_dir / sample_dir.name
            compat_sample_dir.mkdir()
            safe_symlink(model_src, compat_sample_dir / "model.cif")
            if conf_src.exists():
                safe_symlink(conf_src, compat_sample_dir / "confidences.json")
            if summary_src.exists():
                safe_symlink(summary_src, compat_sample_dir / "summary_confidences.json")
                summary = json.loads(summary_src.read_text())
            else:
                summary = {}
            confidence = rank_map.get((seed, sample), summary.get("ranking_score"))
            row = {
                "backend": "alphafast",
                "id": case_id,
                "seed": seed,
                "model_idx": sample,
                "score": confidence,
                "confidence_score": confidence,
                "ranking_score": summary.get("ranking_score", confidence),
                "ptm": summary.get("ptm"),
                "iptm": summary.get("iptm"),
                "has_clash": summary.get("has_clash"),
                "fraction_disordered": summary.get("fraction_disordered"),
                "chain_ptm_json": json_str(summary.get("chain_ptm", [])),
                "chain_iptm_json": json_str(summary.get("chain_iptm", [])),
                "chain_pair_iptm_json": json_str(summary.get("chain_pair_iptm", [])),
                "chain_pair_pae_min_json": json_str(summary.get("chain_pair_pae_min", [])),
                "cif_name": model_src.name,
                "cif_path": os.path.relpath(compat_sample_dir / "model.cif", compat_backend),
                "source_cif_path": os.path.relpath(model_src, root),
                "source_score_path": os.path.relpath(summary_src, root) if summary_src.exists() else "",
            }
            summary_rows.append(row)
            case_rows.append({
                "seed": seed,
                "model": sample,
                "confidence_score": confidence,
                "cif_path": os.path.relpath(compat_sample_dir / "model.cif", compat_backend),
            })
            pred_count += 1
            case_seen = True

        if case_seen:
            case_count += 1
            case_rows.sort(key=score_sort_key, reverse=True)
            write_simple_scores(compat_backend / "all_scores.csv", case_rows)
            best = case_rows[0]
            safe_symlink(compat_backend / best["cif_path"], compat_backend / "best_model.cif")
            write_best_selection(compat_backend / "best_selection.txt", best)
            for name in [
                f"{case_id}_ranking_scores.csv",
                f"{case_id}_model.cif",
                f"{case_id}_confidences.json",
                f"{case_id}_summary_confidences.json",
                "TERMS_OF_USE.md",
            ]:
                src = case_dir / name
                if src.exists():
                    safe_symlink(src, results_dir / name)
            timing_src = case_dir / "inference_timing.jsonl"
            if timing_src.exists():
                safe_symlink(timing_src, compat_backend / "timing.log")
            else:
                touch_summary_log(compat_backend / "timing.log", "No per-case timing log found.\n")

    summary_rows.sort(key=lambda r: (r["id"], int(r["seed"]), int(r["model_idx"])))
    write_rows(tmp / "all_scores.csv", summary_rows)
    finalize_dir(root, tmp)
    return case_count, pred_count


def export_protenix(root: Path) -> tuple[int, int]:
    outputs = root / "outputs"
    tmp = prepare_dir(root)
    compat_outputs = tmp / "outputs"
    compat_outputs.mkdir()
    summary_rows: list[dict] = []
    pred_count = 0
    case_count = 0

    for case_dir in sorted(p for p in outputs.iterdir() if p.is_dir()):
        case_id = case_dir.name
        backend_dir = case_dir / f"protenix_{case_id}"
        if not backend_dir.exists():
            continue
        case_compat = compat_outputs / case_id
        case_compat.mkdir(parents=True, exist_ok=True)
        src_json = case_dir / f"abc_{case_id}.json"
        if src_json.exists():
            safe_symlink(src_json, case_compat / f"abc_{case_id}_data.json")

        compat_backend = case_compat / f"protenix_{case_id.upper()}"
        compat_backend.mkdir()

        case_rows: list[dict] = []
        case_seen = False
        for seed_bundle in sorted(p for p in backend_dir.iterdir() if p.is_dir()):
            seed_match = PROTENIX_SEED_RE.match(seed_bundle.name)
            if not seed_match:
                continue
            seed = int(seed_match.group("seed"))
            native_seed_dir = seed_bundle / case_id / f"seed_{seed}"
            pred_dir = native_seed_dir / "predictions"
            if not pred_dir.exists():
                continue
            compat_seed_dir = compat_backend / f"seed_{seed}"
            compat_seed_dir.mkdir()
            safe_symlink(native_seed_dir, compat_seed_dir / f"protenix_results_{case_id}_data")
            safe_symlink(pred_dir, compat_seed_dir / "predictions")
            for cif_path in sorted(pred_dir.glob(f"{case_id}_sample_*.cif")):
                match = PROTENIX_SAMPLE_RE.match(cif_path.name)
                if not match:
                    continue
                sample = int(match.group("sample"))
                summary_path = pred_dir / f"{case_id}_summary_confidence_sample_{sample}.json"
                if not summary_path.exists():
                    continue
                summary = json.loads(summary_path.read_text())
                confidence = summary.get("ranking_score")
                row = {
                    "backend": "protenix",
                    "id": case_id,
                    "seed": seed,
                    "model_idx": sample,
                    "score": confidence,
                    "confidence_score": confidence,
                    "ranking_score": confidence,
                    "plddt": summary.get("plddt"),
                    "gpde": summary.get("gpde"),
                    "ptm": summary.get("ptm"),
                    "iptm": summary.get("iptm"),
                    "has_clash": summary.get("has_clash"),
                    "disorder": summary.get("disorder"),
                    "num_recycles": summary.get("num_recycles"),
                    "chain_gpde_json": json_str(summary.get("chain_gpde", [])),
                    "chain_pair_gpde_json": json_str(summary.get("chain_pair_gpde", [])),
                    "chain_ptm_json": json_str(summary.get("chain_ptm", [])),
                    "chain_iptm_json": json_str(summary.get("chain_iptm", [])),
                    "chain_pair_iptm_json": json_str(summary.get("chain_pair_iptm", [])),
                    "chain_pair_iptm_global_json": json_str(summary.get("chain_pair_iptm_global", [])),
                    "chain_plddt_json": json_str(summary.get("chain_plddt", [])),
                    "chain_pair_plddt_json": json_str(summary.get("chain_pair_plddt", [])),
                    "cif_name": cif_path.name,
                    "cif_path": os.path.relpath(compat_seed_dir / "predictions" / cif_path.name, compat_backend),
                    "source_cif_path": os.path.relpath(cif_path, root),
                    "source_score_path": os.path.relpath(summary_path, root),
                }
                summary_rows.append(row)
                case_rows.append({
                    "seed": seed,
                    "model": sample,
                    "confidence_score": confidence,
                    "cif_path": os.path.relpath(compat_seed_dir / "predictions" / cif_path.name, compat_backend),
                })
                pred_count += 1
                case_seen = True
        if case_seen:
            case_count += 1
            case_rows.sort(key=score_sort_key, reverse=True)
            write_simple_scores(compat_backend / "all_scores.csv", case_rows)
            best = case_rows[0]
            safe_symlink(compat_backend / best["cif_path"], compat_backend / "best_model.cif")
            write_best_selection(compat_backend / "best_selection.txt", best)
            log_src = root / "logs" / "per_case" / f"{case_id}.log"
            if log_src.exists():
                safe_symlink(log_src, compat_backend / "timing.log")
            else:
                touch_summary_log(compat_backend / "timing.log", "No per-case timing log found.\n")

    summary_rows.sort(key=lambda r: (r["id"], int(r["seed"]), int(r["model_idx"])))
    write_rows(tmp / "all_scores.csv", summary_rows)
    finalize_dir(root, tmp)
    return case_count, pred_count


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--backend", choices=["alphafast", "boltz", "chai", "protenix"], required=True)
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument(
        "--min-predictions-per-case",
        type=int,
        default=0,
        help="Skip cases with fewer complete predictions. Mainly useful for live Chai exports.",
    )
    args = parser.parse_args()
    root = args.root.resolve()
    if args.backend == "boltz":
        case_count, pred_count = export_boltz(root)
    elif args.backend == "chai":
        case_count, pred_count = export_chai(root, args.min_predictions_per_case)
    elif args.backend == "alphafast":
        case_count, pred_count = export_alphafast(root)
    else:
        case_count, pred_count = export_protenix(root)
    print(f"backend={args.backend} root={root} cases={case_count} predictions={pred_count}")


if __name__ == "__main__":
    main()

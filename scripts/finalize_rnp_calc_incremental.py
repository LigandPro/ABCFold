#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path


CHAI_MODEL_PREFIX = "pred.model_idx_"


def timestamp() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def safe_rel_symlink(target: Path, link_path: Path) -> None:
    link_path.symlink_to(os.path.relpath(target, link_path.parent))


def chai_prediction_count(case_dir: Path) -> int:
    backend_dir = case_dir / f"chai1_{case_dir.name}"
    if not backend_dir.is_dir():
        return 0

    count = 0
    for seed_dir in sorted(backend_dir.glob("chai_output_seed-*")):
        if not seed_dir.is_dir():
            continue
        for cif_path in sorted(seed_dir.glob(f"{CHAI_MODEL_PREFIX}*.cif")):
            model_idx = cif_path.name.removeprefix(CHAI_MODEL_PREFIX).removesuffix(".cif")
            if (seed_dir / f"scores.model_idx_{model_idx}.npz").exists():
                count += 1
    return count


def is_complete_chai_case(case_dir: Path, min_predictions: int) -> bool:
    return chai_prediction_count(case_dir) >= min_predictions


def process_is_running(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def lock_pid(lock_path: Path) -> int | None:
    try:
        for line in lock_path.read_text().splitlines():
            if line.startswith("pid="):
                return int(line.split("=", 1)[1])
    except (FileNotFoundError, ValueError):
        return None
    return None


def acquire_lock(root: Path, wait: bool, poll_seconds: int) -> Path:
    lock_path = root / ".rnp_calc_finalize.lock"
    while True:
        try:
            fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            break
        except FileExistsError as exc:
            pid = lock_pid(lock_path)
            if pid is not None and not process_is_running(pid):
                lock_path.unlink(missing_ok=True)
                continue
            if not wait:
                raise SystemExit(f"Another rnp_calc finalizer appears to be running: {lock_path}") from exc
            time.sleep(poll_seconds)
    with os.fdopen(fd, "w") as fh:
        fh.write(f"pid={os.getpid()}\nts={timestamp()}\n")
    return lock_path


def merge_complete_shard_outputs(
    root: Path,
    shard_roots: list[Path],
    min_predictions: int,
    move_conflicts: bool,
) -> tuple[int, int, int, int]:
    outputs = root / "outputs"
    outputs.mkdir(parents=True, exist_ok=True)
    backup_root = root / f"incremental_finalize_backup_{datetime.now().strftime('%Y%m%dT%H%M%S%z')}"

    merged = 0
    already = 0
    skipped_incomplete = 0
    conflicts = 0

    for shard_root in shard_roots:
        shard_outputs = shard_root / "outputs"
        if not shard_outputs.is_dir():
            continue
        for src in sorted(p for p in shard_outputs.iterdir() if p.is_dir()):
            if not is_complete_chai_case(src, min_predictions):
                skipped_incomplete += 1
                continue

            dst = outputs / src.name
            if dst.exists() or dst.is_symlink():
                if dst.resolve() == src.resolve():
                    already += 1
                    continue
                if is_complete_chai_case(dst, min_predictions):
                    already += 1
                    continue
                if not move_conflicts:
                    conflicts += 1
                    continue

                backup_dir = backup_root / "outputs_conflicts"
                backup_dir.mkdir(parents=True, exist_ok=True)
                backup_dst = backup_dir / dst.name
                if backup_dst.exists() or backup_dst.is_symlink():
                    backup_dst = backup_dir / f"{dst.name}.{datetime.now().strftime('%H%M%S')}"
                shutil.move(str(dst), str(backup_dst))

            safe_rel_symlink(src, dst)
            merged += 1

    return merged, already, skipped_incomplete, conflicts


def write_line(log_path: Path, text: str) -> None:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    line = f"[{timestamp()}] {text}"
    with log_path.open("a") as fh:
        fh.write(line + "\n")
    print(line)


def run_export(root: Path, repo_dir: Path, min_predictions: int, log_path: Path) -> str:
    export_log = root / "logs" / "export_rnp_calc.incremental.log"
    cmd = [
        sys.executable,
        str(repo_dir / "scripts" / "export_rnp_calc.py"),
        "--backend",
        "chai",
        "--root",
        str(root),
        "--min-predictions-per-case",
        str(min_predictions),
    ]
    write_line(log_path, f"RUN {' '.join(cmd)}")
    with export_log.open("w") as fh:
        subprocess.run(cmd, check=True, stdout=fh, stderr=subprocess.STDOUT)
    return export_log.read_text().strip()


def count_outputs(root: Path) -> tuple[int, int]:
    outputs = root / "rnp_calc" / "outputs"
    cases = sum(1 for p in outputs.iterdir() if p.is_dir()) if outputs.is_dir() else 0
    all_scores = root / "rnp_calc" / "all_scores.csv"
    if not all_scores.exists():
        return cases, 0
    with all_scores.open() as fh:
        rows = max(sum(1 for _ in fh) - 1, 0)
    return cases, rows


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--repo-dir", default=Path(__file__).resolve().parents[1], type=Path)
    parser.add_argument("--shard-root", action="append", default=[], type=Path)
    parser.add_argument("--min-predictions-per-case", type=int, default=25)
    parser.add_argument("--move-conflicts", action="store_true")
    parser.add_argument("--wait-for-lock", action="store_true")
    parser.add_argument("--lock-poll-seconds", type=int, default=10)
    parser.add_argument("--log", type=Path)
    args = parser.parse_args()

    root = args.root.resolve()
    repo_dir = args.repo_dir.resolve()
    log_path = args.log or (root / "logs" / "finalize_rnp_calc_incremental.log")
    lock_path = acquire_lock(root, args.wait_for_lock, args.lock_poll_seconds)
    try:
        write_line(log_path, f"Incremental finalize started root={root}")
        merged, already, skipped, conflicts = merge_complete_shard_outputs(
            root,
            [p.resolve() for p in args.shard_root],
            args.min_predictions_per_case,
            args.move_conflicts,
        )
        write_line(
            log_path,
            "Shard merge: "
            f"merged={merged} already={already} skipped_incomplete={skipped} conflicts={conflicts}",
        )
        if conflicts:
            write_line(log_path, "Continuing without conflicted shard cases")
        export_summary = run_export(root, repo_dir, args.min_predictions_per_case, log_path)
        cases, rows = count_outputs(root)
        write_line(log_path, f"Export complete: {export_summary} rnp_calc_cases={cases} all_scores_rows={rows}")
    finally:
        try:
            lock_path.unlink()
        except FileNotFoundError:
            pass


if __name__ == "__main__":
    main()

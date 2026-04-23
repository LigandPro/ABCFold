#!/usr/bin/env bash
set -euo pipefail

INPUT_DIR=${1:?input_dir required}
OUT_ROOT=${2:?out_root required}
REPO_DIR=${3:-$HOME/work/Projects/ABCFold_ligandpro}
GPU_ID="${CUDA_VISIBLE_DEVICES:-0}"
GPU_ID="${GPU_ID%%,*}"
NUMBER_OF_MODELS=${NUMBER_OF_MODELS:-5}
NUM_RECYCLES=${NUM_RECYCLES:-10}
MIN_PREDICTIONS_PER_CASE=${MIN_PREDICTIONS_PER_CASE:-25}
STATUS_TSV="$OUT_ROOT/status.tsv"
CASE_LOG_DIR="$OUT_ROOT/logs/cases"
RUNNER_FINALIZE_LOG="$OUT_ROOT/logs/incremental_finalize.runner.log"
LAST_FINALIZER_PID=""

mkdir -p "$OUT_ROOT/logs" "$OUT_ROOT/outputs" "$CASE_LOG_DIR"
printf "id\tstatus\tts\tpredictions\n" > "$STATUS_TSV"

chai_prediction_count() {
  local out_dir=$1
  local id=$2
  python3 - "$out_dir" "$id" <<'PY'
import sys
from pathlib import Path

out_dir = Path(sys.argv[1])
case_id = sys.argv[2]
backend_dir = out_dir / f"chai1_{case_id}"
count = 0
if backend_dir.is_dir():
    for cif_path in backend_dir.glob("chai_output_seed-*/pred.model_idx_*.cif"):
        model_idx = cif_path.name.removeprefix("pred.model_idx_").removesuffix(".cif")
        if (cif_path.parent / f"scores.model_idx_{model_idx}.npz").exists():
            count += 1
print(count)
PY
}

run_incremental_export_async() {
  (
    "$REPO_DIR/.venv311/bin/python" "$REPO_DIR/scripts/finalize_rnp_calc_incremental.py" \
      --root "$OUT_ROOT" \
      --repo-dir "$REPO_DIR" \
      --min-predictions-per-case "$MIN_PREDICTIONS_PER_CASE" \
      >>"$RUNNER_FINALIZE_LOG" 2>&1
  ) &
  LAST_FINALIZER_PID=$!
  echo "[finalize] incremental export queued pid=$LAST_FINALIZER_PID"
}

wait_for_last_incremental_export() {
  if [ -n "$LAST_FINALIZER_PID" ] && kill -0 "$LAST_FINALIZER_PID" 2>/dev/null; then
    wait "$LAST_FINALIZER_PID" || echo "[WARN] background incremental export failed; see $RUNNER_FINALIZE_LOG" >&2
  fi
  LAST_FINALIZER_PID=""
}

run_incremental_export_final() {
  wait_for_last_incremental_export
  if "$REPO_DIR/.venv311/bin/python" "$REPO_DIR/scripts/finalize_rnp_calc_incremental.py" \
      --root "$OUT_ROOT" \
      --repo-dir "$REPO_DIR" \
      --min-predictions-per-case "$MIN_PREDICTIONS_PER_CASE" \
      --wait-for-lock \
      >>"$RUNNER_FINALIZE_LOG" 2>&1; then
    echo "[finalize] final incremental export updated"
  else
    echo "[WARN] final incremental export failed; see $RUNNER_FINALIZE_LOG" >&2
  fi
}

mapfile -t JSON_FILES < <(find "$INPUT_DIR" -maxdepth 1 -type f -name "*.json" | sort)
TOTAL=${#JSON_FILES[@]}
echo "START_TIME=$(date -Is)"
echo "INPUT_DIR=$INPUT_DIR"
echo "OUT_ROOT=$OUT_ROOT"
echo "TOTAL_INPUTS=$TOTAL"
echo "MIN_PREDICTIONS_PER_CASE=$MIN_PREDICTIONS_PER_CASE"

ok=0
fail=0
for jf in "${JSON_FILES[@]}"; do
  base=$(basename "$jf")
  id="${base%.json}"
  out_dir="$OUT_ROOT/outputs/$id"
  log_file="$CASE_LOG_DIR/$id.log"
  mkdir -p "$out_dir"
  echo "RUN  $id"
  if CUDA_VISIBLE_DEVICES="$GPU_ID" DOCKER_HOST=unix:///run/user/1003/docker.sock \
      "$REPO_DIR/.venv311/bin/abcfold" \
      "$jf" "$out_dir" -c --gpus 0 \
      --number_of_models "$NUMBER_OF_MODELS" --num_recycles "$NUM_RECYCLES" \
      --no_server --no_visuals --override \
      >"$log_file" 2>&1; then
    pred_count=$(chai_prediction_count "$out_dir" "$id")
    if [ "$pred_count" -ge "$MIN_PREDICTIONS_PER_CASE" ]; then
      printf "%s\tok\t%s\t%s\n" "$id" "$(date -Is)" "$pred_count" >> "$STATUS_TSV"
      echo "OK   $id predictions=$pred_count"
      ok=$((ok+1))
    else
      printf "%s\tfail_incomplete\t%s\t%s\n" "$id" "$(date -Is)" "$pred_count" >> "$STATUS_TSV"
      echo "FAIL $id incomplete predictions=$pred_count/$MIN_PREDICTIONS_PER_CASE (see $log_file)"
      fail=$((fail+1))
    fi
  else
    pred_count=$(chai_prediction_count "$out_dir" "$id")
    printf "%s\tfail\t%s\t%s\n" "$id" "$(date -Is)" "$pred_count" >> "$STATUS_TSV"
    echo "FAIL $id predictions=$pred_count (see $log_file)"
    fail=$((fail+1))
  fi
  run_incremental_export_async
done

echo "END_TIME=$(date -Is)"
echo "SUMMARY ok=$ok fail=$fail total=$TOTAL"
run_incremental_export_final

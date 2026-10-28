import json
import threading
import time

import pytest

from abcfold.batch import (BatchJob, ManifestError, job_command, parse_manifest,
                           parse_models, run_batch)

KRAS = "MTEYKLVVVGADGVGKSALTIQ"
PART = "GSHMLEDPV"


def write_csv(path, rows):
    path.write_text("\n".join(rows) + "\n")
    return path


def test_parse_models_aliases():
    assert parse_models("boltz;chai") == ["boltz", "chai1"]
    assert parse_models("af3, of3 protenix") == ["alphafold3", "openfold3",
                                                 "protenix"]
    assert parse_models(None) == ["boltz"]
    assert len(parse_models("all")) == 6
    with pytest.raises(ManifestError):
        parse_models("alphafold2")


def test_parse_csv_manifest(tmp_path):
    manifest = write_csv(tmp_path / "m.csv", [
        "id,protein,smiles,ccd,models,n_models",
        f"kras,{KRAS},CCO,MG;GDP,boltz;protenix,2",
        f"dimer,{KRAS}:{PART},,,chai1,",
    ])
    jobs = parse_manifest(manifest)
    assert [j.id for j in jobs] == ["kras", "dimer"]
    kras = jobs[0]
    assert kras.models == ["boltz", "protenix"]
    assert kras.n_models == 2
    seqs = kras.params["sequences"]
    assert seqs[0] == {"protein": {"id": "A", "sequence": KRAS}}
    assert seqs[1] == {"ligand": {"id": "B", "smiles": "CCO"}}
    assert seqs[2] == {"ligand": {"id": "C", "ccdCodes": ["MG"]}}
    assert seqs[3] == {"ligand": {"id": "D", "ccdCodes": ["GDP"]}}
    assert kras.params["name"] == "kras"
    assert jobs[1].protein_sequences == [KRAS, PART]


def test_parse_json_manifest_with_af3_json(tmp_path):
    af3 = tmp_path / "x.json"
    af3.write_text(json.dumps({"name": "orig", "modelSeeds": [7], "sequences": [
        {"protein": {"id": "A", "sequence": KRAS}}]}))
    manifest = tmp_path / "m.json"
    manifest.write_text(json.dumps({
        "defaults": {"models": ["boltz", "chai1"]},
        "jobs": [{"id": "a", "af3_json": "x.json"},
                 {"id": "b", "protein": [KRAS], "smiles": ["CCO", "CCN"],
                  "models": "protenix"}],
    }))
    a, b = parse_manifest(manifest)
    assert a.params["name"] == "a" and a.params["modelSeeds"] == [7]
    assert a.models == ["boltz", "chai1"]
    assert b.models == ["protenix"]
    assert len(b.params["sequences"]) == 3


@pytest.mark.parametrize("rows,msg", [
    (["id,protein", f",{KRAS}"], "missing 'id'"),
    (["id,protein", f"a,{KRAS}", f"a,{KRAS}"], "Duplicate"),
    (["id,protein", "a/b,X"], "invalid id"),
    (["id,smiles", "a,CCO"], "needs 'protein'"),
])
def test_manifest_errors(tmp_path, rows, msg):
    with pytest.raises(ManifestError, match=msg):
        parse_manifest(write_csv(tmp_path / "m.csv", rows))


def test_job_command(tmp_path):
    job = BatchJob("a", {}, ["boltz", "chai1"], n_models=2)
    cmd = job_command(job, tmp_path / "a.json", tmp_path / "out", "1", "server",
                      ["--diffusion_steps", "50"])
    assert cmd[1:4] == ["-m", "abcfold.cli", "run"]
    assert "--boltz" in cmd and "--chai1" in cmd
    assert cmd[cmd.index("--gpus") + 1] == "1"
    assert cmd[cmd.index("--msa") + 1] == "server"
    assert cmd[-2:] == ["--diffusion_steps", "50"]


class FakeRunner:
    def __init__(self, codes=None, delay=0.0):
        self.codes = codes or {}
        self.calls = []
        self.delay = delay
        self.active = 0
        self.max_active = 0
        self.lock = threading.Lock()

    def __call__(self, cmd, log_path, env):
        with self.lock:
            self.active += 1
            self.max_active = max(self.max_active, self.active)
        out = cmd[cmd.index("run") + 2]
        job_id = out.rstrip("/").split("/")[-1]
        self.calls.append((job_id, cmd[cmd.index("--gpus") + 1]
                           if "--gpus" in cmd else None))
        time.sleep(self.delay)
        code = self.codes.get(job_id, 0)
        import pathlib
        pathlib.Path(out).mkdir(parents=True, exist_ok=True)
        (pathlib.Path(out) / "report.json").write_text(json.dumps({
            "engines": [{"engine": "boltz", "status": "ok" if code == 0 else
                         "failed"}]}))
        log_path.write_text("log\n")
        with self.lock:
            self.active -= 1
        return code


def manifest_of(tmp_path, n):
    rows = ["id,protein,models"] + [f"j{i},{KRAS},boltz" for i in range(n)]
    return write_csv(tmp_path / "m.csv", rows)


def test_run_batch_status_and_resume(tmp_path):
    manifest = manifest_of(tmp_path, 3)
    runner = FakeRunner(codes={"j1": 1, "j2": 2})
    status = run_batch(manifest, tmp_path / "out", msa="none", runner=runner)
    jobs = status["jobs"]
    assert {k: v["status"] for k, v in jobs.items()} == {
        "j0": "ok", "j1": "failed", "j2": "partial"}
    assert jobs["j0"]["engines"] == {"boltz": "ok"}
    on_disk = json.loads((tmp_path / "out" / "batch_status.json").read_text())
    assert on_disk["counts"] == {"ok": 1, "failed": 1, "partial": 1}
    assert (tmp_path / "out" / "inputs" / "j0.json").exists()

    runner2 = FakeRunner()
    run_batch(manifest, tmp_path / "out", msa="none", runner=runner2)
    assert sorted(c[0] for c in runner2.calls) == ["j1", "j2"]  # j0 skipped

    runner3 = FakeRunner()
    run_batch(manifest, tmp_path / "out", msa="none", runner=runner3, force=True)
    assert len(runner3.calls) == 3


def test_run_batch_parallel_round_robin_gpus(tmp_path):
    manifest = manifest_of(tmp_path, 4)
    runner = FakeRunner(delay=0.05)
    run_batch(manifest, tmp_path / "out", max_parallel=2, gpus="1,2",
              msa="none", runner=runner)
    assert runner.max_active == 2
    assert {gpu for _, gpu in runner.calls} == {"1", "2"}


def test_run_batch_prefetches_unique_sequences_once(tmp_path, monkeypatch):
    calls = []

    def fake_prefetch(sequences, options, client=None):
        calls.append(list(sequences))
        return len(set(sequences)), 0

    monkeypatch.setattr("abcfold.msa.resolve.prefetch_unique_sequences",
                        fake_prefetch)
    run_batch(manifest_of(tmp_path, 3), tmp_path / "out", msa="server",
              runner=FakeRunner())
    assert len(calls) == 1
    assert calls[0] == [KRAS, KRAS, KRAS]

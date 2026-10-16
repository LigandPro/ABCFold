"""Regression tests: a requested MSA must reach the backend (Protenix N_msa 2 bug)."""

import json
import re
from pathlib import Path

import pytest

from abcfold.msa.guard import (ShallowMsaError, check_backend_n_msa,
                               check_input_msa_depth, check_protenix_input,
                               msa_rows, parse_n_msa)
from abcfold.protenix import run_protenix as rp

QUERY = "MTEYKLVVVGADGVGKSALTIQLIQNHFVDEYDPTIEDSYRKQ"


def a3m(n):
    rows = [f">query\n{QUERY}\n"]
    for i in range(n):
        rows.append(f">hit{i}\n{QUERY[:-2]}{'ACDEFGHIKLMNPQRSTVWY'[i % 20]}"
                    f"{'ACDEFGHIKLMNPQRSTVWY'[(i // 20) % 20]}\n")
    return "".join(rows)


def kras_input(msa):
    protein = {"id": "A", "sequence": QUERY}
    if msa is not None:
        protein.update(unpairedMsa=msa, pairedMsa="", templates=[])
    return {
        "name": "kras",
        "modelSeeds": [1],
        "sequences": [
            {"protein": protein},
            {"ligand": {"id": "B", "ccdCodes": ["GDP"]}},
            {"ligand": {"id": "C", "ccdCodes": ["MG"]}},
        ],
    }


def test_msa_rows_counts_distinct_non_gap_rows():
    assert msa_rows(a3m(30)) == 31
    gap = f">g\n{'-' * len(QUERY)}\n"
    assert msa_rows(a3m(3) + gap, f">query\n{QUERY}\n") == 4


def test_parse_n_msa():
    log = "kras [seed:1]: N_asym 4, N_token 242, N_atom 1430, N_msa 2\n"
    assert parse_n_msa(log) == [2]


def test_input_depth_guard():
    check_input_msa_depth(kras_input(a3m(50)), 10)
    check_input_msa_depth(kras_input(None), 10)       # no MSA requested
    check_input_msa_depth(kras_input(""), 10)         # single-sequence mode
    with pytest.raises(ShallowMsaError, match="A: 3 rows"):
        check_input_msa_depth(kras_input(a3m(2)), 10)
    check_input_msa_depth(kras_input(a3m(2)), 0)      # disabled


def test_protenix_input_guard_detects_missing_file(tmp_path):
    job = [{"sequences": [{"proteinChain": {
        "sequence": QUERY, "count": 1,
        "unpairedMsaPath": str(tmp_path / "gone" / "non_pairing.a3m")}}]}]
    with pytest.raises(ShallowMsaError, match="does not exist"):
        check_protenix_input(job, 10)


def test_backend_n_msa_guard():
    check_backend_n_msa("Protenix", "N_msa 512", 10)
    with pytest.raises(ShallowMsaError, match="N_msa=2"):
        check_backend_n_msa("Protenix", "N_msa 2", 10)


class FakeProtenixEnv:
    """Stands in for the Protenix env: checks what Protenix would read."""

    def __init__(self, report_n_msa=None):
        self.report_n_msa = report_n_msa
        self.seen_rows = []

    def has_executable(self, name):
        return False

    def run(self, cmd, extra_env=None, log_file=None, **kwargs):
        input_json = Path(cmd[cmd.index("--input_json_path") + 1])
        dump_dir = Path(cmd[cmd.index("--dump_dir") + 1])
        assert cmd[cmd.index("--use_msa") + 1] == "True"
        job = json.loads(input_json.read_text())[0]
        chain = job["sequences"][0]["proteinChain"]
        assert "msa" not in chain  # deprecated field must not be used
        # The MSA file must still exist while Protenix runs
        rows = msa_rows(Path(chain["unpairedMsaPath"]).read_text())
        self.seen_rows.append(rows)
        n_msa = self.report_n_msa if self.report_n_msa is not None else rows
        Path(log_file).write_text(
            f"kras [seed:1]: N_asym 3, N_token 60, N_atom 400, N_msa {n_msa}\n"
        )
        out = dump_dir / "kras" / "seed_1" / "predictions"
        out.mkdir(parents=True)
        (out / "kras_sample_0.cif").write_text("data_x\n")


def _run(tmp_path, monkeypatch, msa, env):
    monkeypatch.setattr(rp, "ensure_protenix_env", lambda config: env)
    input_json = tmp_path / "abc_input.json"
    input_json.write_text(json.dumps(kras_input(msa)))
    return rp.run_protenix(input_json, tmp_path / "out", config={},
                           number_of_models=1)


def test_protenix_receives_full_msa(tmp_path, monkeypatch):
    env = FakeProtenixEnv()
    assert _run(tmp_path, monkeypatch, a3m(200), env) is True
    assert env.seen_rows == [201]


def test_protenix_fails_loudly_when_msa_is_lost(tmp_path, monkeypatch):
    env = FakeProtenixEnv(report_n_msa=2)
    with pytest.raises(ShallowMsaError):
        _run(tmp_path, monkeypatch, a3m(200), env)
    err = (tmp_path / "out" / "protenix_error.log").read_text()
    assert re.search(r"N_msa=2", err)


def test_protenix_shallow_input_fails_before_running(tmp_path, monkeypatch):
    env = FakeProtenixEnv()
    with pytest.raises(ShallowMsaError):
        _run(tmp_path, monkeypatch, a3m(3), env)
    assert env.seen_rows == []

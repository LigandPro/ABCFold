import json
import sys
from pathlib import Path

import numpy as np
import pytest

from abcfold.output.utils import af3_pae_path
from abcfold.report import (SCHEMA, EngineRecord, SampleRecord, build_report,
                            extract_scores, ligand_pae, samples_from_output,
                            to_percent, validate_report, write_report)


@pytest.mark.parametrize("data,score", [
    ({"ranking_score": 0.8, "ptm": 0.7, "iptm": 0.6}, 0.8),        # AF3/Protenix
    ({"confidence_score": 0.9, "ptm": 0.5, "iptm": 0.4}, 0.9),     # Boltz
    ({"aggregate_score": np.array([0.3]), "ptm": np.array([0.2]),
      "iptm": np.array([0.1])}, 0.3),                              # Chai-1
    ({"sample_ranking_score": 0.42}, 0.42),                        # OpenFold3
    ({}, None),
])
def test_extract_scores(data, score):
    out = extract_scores(data)
    assert out["score"] == (pytest.approx(score) if score is not None else None)


def test_to_percent_scales_unit_plddt():
    assert to_percent([0.5, 0.7]) == pytest.approx(60.0)
    assert to_percent([50, 70]) == pytest.approx(60.0)
    assert to_percent([]) is None


def test_ligand_pae_both_directions():
    pae = [[0, 1, 2],
           [3, 0, 4],
           [5, 6, 0]]
    chains = ["A", "A", "L"]
    # A->L: 2, 4 ; L->A: 5, 6
    assert ligand_pae(pae, chains, ["L"]) == pytest.approx(17 / 4)
    assert ligand_pae(pae, chains, []) is None
    assert ligand_pae(pae, ["A", "A"], ["L"]) is None


def engine(name, status, scores=(), error=None):
    rec = EngineRecord(engine=name, version="1.0", status=status, seconds=10.0,
                       error=error)
    rec.samples = [
        SampleRecord(engine=name, version="1.0", seed=1, rank=None,
                     cif=f"{name}_{i}.cif", score=s, chain_ids=["A", "B"])
        for i, s in enumerate(scores)
    ]
    return rec


def test_build_report_ranks_and_status():
    report = build_report(
        "kras",
        [engine("boltz", "ok", [0.2, 0.9, None]),
         engine("chai1", "failed", error="boom"),
         engine("protenix", "skipped")],
        msa={"source": "server", "chains": {"A": {"depth": 10}}},
    )
    assert report["schema"] == SCHEMA
    assert report["status"] == "partial"
    boltz = [s for s in report["samples"] if s["engine"] == "boltz"]
    assert [s["score"] for s in boltz] == [0.9, 0.2, None]
    assert [s["rank"] for s in boltz] == [1, 2, 3]
    eng = {e["engine"]: e for e in report["engines"]}
    assert eng["boltz"]["top_score"] == 0.9
    assert eng["chai1"]["error"] == "boom"
    assert validate_report(report) == []


def test_report_status_all_failed_and_ok():
    assert build_report("x", [engine("boltz", "failed", error="e")])["status"] == \
        "failed"
    assert build_report("x", [engine("boltz", "ok", [0.1])])["status"] == "ok"


def test_validate_report_catches_problems():
    report = build_report("x", [engine("boltz", "failed")])
    errors = validate_report(report)
    assert any("failed engine without error" in e for e in errors)
    report["samples"] = [{"engine": "boltz", "score": "high"}]
    assert any("missing" in e for e in validate_report(report))


def test_write_report_is_json(tmp_path):
    report = build_report("x", [engine("boltz", "ok", [0.5])])
    path = write_report(report, tmp_path / "sub" / "report.json")
    assert json.loads(path.read_text())["schema"] == SCHEMA


def test_samples_from_output_with_real_outputs(output_objs, tmp_path):
    samples = samples_from_output("boltz", "2.2.1", output_objs.boltz_output.output,
                                  tmp_path, seconds_per_sample=3.0)
    assert samples
    s = samples[0]
    assert s.engine == "boltz" and s.version == "2.2.1"
    assert s.score is not None and 0 <= s.score <= 1
    assert s.plddt is not None and 0 < s.plddt <= 100
    assert s.chain_ids
    assert s.seconds == 3.0
    af3 = samples_from_output("alphafold3", "3.0.4", output_objs.af3_output.output,
                              tmp_path)
    assert all(x.score is not None for x in af3)
    report = build_report("6BJ9", [EngineRecord("boltz", "2.2.1", "ok", 1.0,
                                                samples=samples)])
    assert validate_report(report) == []


def test_pae_files_use_json_extension():
    """Defect 5: converted PAE files were written with npz/npy suffixes."""
    for name in ("pred.model_idx_0.cif", "model_0.cif", "x.npz.cif"):
        out = af3_pae_path(Path("/o") / name)
        assert out.suffix == ".json"
        assert out.name.endswith("_af3_pae.json")


def test_report_cli_exit_codes_are_distinct():
    from abcfold.abcfold import EXIT_FAILED, EXIT_OK, EXIT_PARTIAL

    assert len({EXIT_OK, EXIT_FAILED, EXIT_PARTIAL}) == 3
    assert "abcfold.report" in sys.modules

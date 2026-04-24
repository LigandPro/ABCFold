import os
import tempfile
from pathlib import Path

import pytest

try:
    import chai_lab  # noqa F401

    run_chai1 = True

except ImportError:
    run_chai1 = False


@pytest.mark.skipif(not run_chai1, reason="chai_lab not installed")
def test_generate_chai_command(test_data):
    from abcfold.chai1.run_chai1 import generate_chai_command

    input_fasta = "/road/to/nowhere.fasta"
    msa_dir = "/road/to/nowhere"
    with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as fp:
        constraints = fp.name
        output_dir = "/road/to/nowhere"

        cmd = generate_chai_command(
            input_fasta=input_fasta,
            msa_dir=msa_dir,
            input_constraints=constraints,
            output_dir=output_dir,
        )

    assert cmd[1].endswith("chai.py")
    assert "fold" in cmd
    assert input_fasta in cmd
    assert msa_dir in cmd
    assert constraints in cmd
    assert output_dir in cmd
    assert "--num-diffn-samples" in cmd
    assert "5" in cmd


@pytest.mark.skipif(
    os.getenv("CI") == "true" and not run_chai1,
    reason="Skipping test in CI environment",
)
def test_run_chai(test_data):
    pytest.importorskip("chai_lab")
    from abcfold.chai1.run_chai1 import run_chai

    with tempfile.TemporaryDirectory() as temp_dir:
        try:
            run_chai(
                test_data.test_inputA_json,
                temp_dir,
                save_input=True,
                test=True,
                config=test_data.config_dict,
            )
        except Exception as e:
            print(e)
            assert False


def test_normalize_chai_fast_devices():
    from abcfold.chai1.run_chai1_fast import normalize_devices

    assert normalize_devices(None) == [None]
    assert normalize_devices("cpu") == ["cpu"]
    assert normalize_devices("all") == ["cuda"]
    assert normalize_devices("0,1") == ["cuda:0", "cuda:1"]


def test_run_chai_batch_test_mode_creates_native_layout(monkeypatch, test_data):
    from abcfold.chai1 import run_chai1_fast

    def fail_if_called(*args, **kwargs):
        raise AssertionError("test mode must not create or use the Chai env")

    monkeypatch.setattr(run_chai1_fast, "ensure_chai_env", fail_if_called)

    with tempfile.TemporaryDirectory() as temp_dir:
        run_ok = run_chai1_fast.run_chai_batch(
            [test_data.test_inputA_json, test_data.test_inputDNA_json],
            temp_dir,
            config=test_data.config_dict,
            test=True,
            devices="0,1",
        )

        assert run_ok
        assert Path(temp_dir, "outputs", "2PV7", "chai_output_seed-1").is_dir()
        assert Path(temp_dir, "outputs", "DNA_example", "chai_output_seed-1").is_dir()


def test_chai_fast_manifests_preserve_quality_settings():
    from abcfold.chai1.run_chai1_fast import (_write_device_manifests,
                                              _write_worker_script)

    tasks = [
        {"seed": 1, "output_dir": "out-1"},
        {"seed": 2, "output_dir": "out-2"},
    ]
    with tempfile.TemporaryDirectory() as temp_dir:
        manifests = _write_device_manifests(
            tasks,
            devices=["cuda:0", "cuda:1"],
            work_root=Path(temp_dir),
            number_of_models=5,
            num_recycles=10,
        )

        assert len(manifests) == 2
        manifest_text = "\n".join(path.read_text() for path in manifests)
        assert '"device": "cuda:0"' in manifest_text
        assert '"device": "cuda:1"' in manifest_text
        assert '"number_of_models": 5' in manifest_text
        assert '"num_recycles": 10' in manifest_text
        assert (
            "num_diffn_timesteps=200"
            in _write_worker_script(Path(temp_dir)).read_text()
        )

import os
import tempfile
from pathlib import Path

import pytest

try:
    import chai_lab  # noqa F401

    chai_lab_installed = True

except ImportError:
    chai_lab_installed = False


@pytest.mark.skipif(
    os.getenv("CI") == "true" and not chai_lab_installed,
    reason="Skipping test in CI environment",
)
def test_run_chai(test_data):
    pytest.importorskip("chai_lab")
    from abcfold.chai1.run_chai1_fast import run_chai_fast

    with tempfile.TemporaryDirectory() as temp_dir:
        try:
            run_chai_fast(
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

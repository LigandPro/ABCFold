import os
import tempfile

import pytest

from abcfold.boltz.run_boltz import (generate_boltz_command, run_boltz,
                                     run_boltz_batch)


@pytest.mark.skipif(os.getenv("CI") == "true", reason="Skipping test in CI environment")
def test_run_boltz(test_data):

    with tempfile.TemporaryDirectory() as temp_dir:
        try:
            run_boltz(
                test_data.test_inputA_json,
                temp_dir,
                config=test_data.config_dict,
                save_input=True,
                test=True,
            )
        except Exception as e:
            print(e)
            assert False


def test_generate_boltz_command(test_data):
    input_yaml = "/road/to/nowhere.yaml"
    output_dir = "/road/to/nowhere"

    cmd = generate_boltz_command(
        input_yaml=input_yaml,
        output_dir=output_dir,
        config=test_data.config_dict,
    )

    assert "boltz" in cmd
    assert "predict" in cmd
    assert input_yaml in cmd
    assert output_dir in cmd
    assert "--override" in cmd
    assert "--sampling_steps" in cmd
    assert "200" in cmd


def test_generate_boltz_command_batch_options(test_data):
    cmd = generate_boltz_command(
        input_yaml="/road/to/seed-1",
        output_dir="/road/to/output",
        config=test_data.config_dict,
        preprocessing_threads=2,
        num_workers=2,
    )

    assert "--preprocessing-threads" in cmd
    assert "2" in cmd
    assert "--num_workers" in cmd


def test_run_boltz_batch_test_mode(test_data):
    with tempfile.TemporaryDirectory() as temp_dir:
        run_ok = run_boltz_batch(
            [test_data.test_inputA_json, test_data.test_inputDNA_json],
            temp_dir,
            config=test_data.config_dict,
            save_input=True,
            test=True,
        )

        assert run_ok
        seed_dir = os.path.join(temp_dir, "boltz_batch", "seed-1")
        assert os.path.isdir(seed_dir)
        assert os.path.exists(os.path.join(seed_dir, "inputA_seed-1.yaml"))
        assert os.path.exists(os.path.join(seed_dir, "inputDNA_seed-1.yaml"))
        assert os.path.exists(
            os.path.join(temp_dir, "outputs", "inputA", "abc_inputA.json")
        )

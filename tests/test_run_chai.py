import os
import tempfile

import pytest

from src.run_chai1 import generate_chai_command, run_chai


def test_generate_chai_command():
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

    assert "chai" in cmd
    assert "fold" in cmd
    assert input_fasta in cmd
    assert msa_dir in cmd
    assert constraints in cmd
    assert output_dir in cmd


@pytest.mark.skipif(os.getenv("CI") == "true", reason="Skipping test in CI environment")
def test_run_chai(test_data):
    pytest.importorskip("chai_lab")

    with tempfile.TemporaryDirectory() as temp_dir:
        try:
            run_chai(
                test_data.test_inputA_json,
                temp_dir,
                save_input=True,
                test=True,
            )
        except Exception as e:
            print(e)
            assert False

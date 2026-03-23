import shutil
import subprocess
from pathlib import Path

from abcfold.alphafold3.run_alphafold3 import (
    generate_af3_cmd,
    run_alphafold3,
    sanitize_job_name,
)


def test_sanitize_job_name():
    assert sanitize_job_name("Test Name (A/B)") == "Test_Name_AB"


def test_generate_af3_command(test_data):
    input_json = Path(test_data.test_inputA_json)
    output_dir = Path("/road/to/output")
    model_params = Path("/road/to/models")
    database_dir = Path("/road/to/database")

    cmd = generate_af3_cmd(
        input_json=input_json,
        output_dir=output_dir,
        config=test_data.config_dict,
        model_params=model_params,
        database_dir=database_dir,
        sif_path=None,
        interactive=True,
    )
    assert "docker run -i" in cmd
    assert "romerolabduke/alphafast:latest" in cmd
    assert f"{input_json.parent.resolve()}:/root/af_input:ro" in cmd
    assert f"{output_dir.resolve()}:/root/af_output" in cmd
    assert f"{model_params.resolve()}:/root/models:ro" in cmd
    assert f"{database_dir.resolve()}:/root/public_databases:ro" in cmd
    assert "--gpus all" in cmd
    assert "python /app/alphafold/run_alphafold.py" in cmd
    assert f"--json_path /root/af_input/{input_json.name}" in cmd
    assert "--output_dir /root/af_output" in cmd
    assert "--db_dir /root/public_databases" in cmd
    assert "--mmseqs_db_dir /root/public_databases/mmseqs" in cmd
    assert "--use_mmseqs_gpu" in cmd


def test_generate_af3_command_precomputed_msas(test_data):
    input_json = Path(test_data.test_inputA_json)
    output_dir = Path("/road/to/output")
    model_params = Path("/road/to/models")
    database_dir = Path("/road/to/database")

    cmd = generate_af3_cmd(
        input_json=input_json,
        output_dir=output_dir,
        config=test_data.config_dict,
        model_params=model_params,
        database_dir=database_dir,
        sif_path=None,
        interactive=False,
        use_precomputed_msas=True,
    )
    assert "--norun_data_pipeline" in cmd
    assert "--force_output_dir" in cmd
    assert "--use_mmseqs_gpu" not in cmd
    assert "--output_dir /root/af_output/2PV7" in cmd


def test_generate_af3_singularity_command(test_data):
    input_json = Path(test_data.test_inputA_json)
    output_dir = Path("/road/to/nowhere")
    model_params = Path("/road/to/nowhere")
    database_dir = Path("/road/to/nowhere")
    sif_path = Path("/road/to/nowhere.sif")

    cmd = generate_af3_cmd(
        input_json=input_json,
        output_dir=output_dir,
        config=test_data.config_dict,
        model_params=model_params,
        database_dir=database_dir,
        sif_path=sif_path,
        interactive=True,
    )

    assert "singularity exec" in cmd
    assert f"--bind {input_json.parent.resolve()}:/root/af_input" in cmd
    assert f"--bind {output_dir.resolve()}:/root/af_output" in cmd
    assert f"--bind {model_params.resolve()}:/root/models" in cmd
    assert f"--bind {database_dir.resolve()}:/root/public_databases" in cmd
    assert f"{sif_path}" in cmd
    assert "python /app/alphafold/run_alphafold.py" in cmd
    assert f"--json_path=/root/af_input/{input_json.name}" in cmd
    assert "--model_dir=/root/models" in cmd
    assert "--output_dir=/root/af_output" in cmd
    assert "--num_diffusion_samples" in cmd
    assert "--num_recycles" in cmd


def test_run_af3_returns_output_dir(monkeypatch, test_data, tmp_path):
    input_json = tmp_path / "inputA.json"
    shutil.copyfile(test_data.test_inputA_json, input_json)
    model_params = tmp_path / "models"
    database_dir = tmp_path / "db"
    output_dir = tmp_path / "output"
    model_params.mkdir()
    database_dir.mkdir()
    output_dir.mkdir()

    def fake_run(*args, **kwargs):
        command = kwargs["args"] if "args" in kwargs else args[0]
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr(
        "abcfold.alphafold3.run_alphafold3.check_af3_install",
        lambda *args, **kwargs: None,
    )
    monkeypatch.setattr(subprocess, "run", fake_run)

    result = run_alphafold3(
        input_json=input_json,
        output_dir=output_dir,
        model_params=model_params,
        database_dir=database_dir,
        sif_path=None,
        config=test_data.config_dict,
    )

    assert result == output_dir / "2PV7"


def test_run_af3_writes_error_log(monkeypatch, test_data, tmp_path):
    input_json = tmp_path / "inputA.json"
    shutil.copyfile(test_data.test_inputA_json, input_json)
    model_params = tmp_path / "models"
    database_dir = tmp_path / "db"
    output_dir = tmp_path / "output"
    model_params.mkdir()
    database_dir.mkdir()
    output_dir.mkdir()

    def fake_run(*args, **kwargs):
        command = kwargs["args"] if "args" in kwargs else args[0]
        raise subprocess.CalledProcessError(
            1, command, output="", stderr="backend exploded"
        )

    monkeypatch.setattr(
        "abcfold.alphafold3.run_alphafold3.check_af3_install",
        lambda *args, **kwargs: None,
    )
    monkeypatch.setattr(subprocess, "run", fake_run)

    result = run_alphafold3(
        input_json=input_json,
        output_dir=output_dir,
        model_params=model_params,
        database_dir=database_dir,
        sif_path=None,
        config=test_data.config_dict,
    )

    assert result is None
    assert output_dir.joinpath("af3_error.log").read_text() == "backend exploded"

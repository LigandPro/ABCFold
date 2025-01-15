import logging
import subprocess
import sys
from pathlib import Path
from typing import Union

logger = logging.getLogger("logger")


def check_af3_install(interactive):
    logger.debug("Checking if Alphafold3 is installed")
    cmd = generate_test_command(interactive)
    with subprocess.Popen(
        cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE
    ) as p:
        _, stderr = p.communicate()
        p.wait()
        if p.returncode != 1:
            logger.error(
                "Alphafold3 is not installed, please go to \
https://github.com/google-deepmind/alphafold3 and follow the instructions to install"
            )

            raise subprocess.CalledProcessError(p.returncode, cmd, stderr)
    logger.info("Alphafold3 is installed")


def run_alphafold3(
    input_json: Union[str, Path],
    output_dir: Union[str, Path],
    model_params: Union[str, Path],
    database_dir: Union[str, Path],
    interactive: bool = True,
    number_of_models: int = 5,
) -> None:

    check_af3_install(interactive)

    input_json = Path(input_json)
    output_dir = Path(output_dir)
    cmd = generate_af3_cmd(
        input_json=input_json,
        output_dir=output_dir,
        model_params=model_params,
        database_dir=database_dir,
        interactive=interactive,
        number_of_models=number_of_models,
    )

    logger.info("Running Alphafold3")
    with subprocess.Popen(
        cmd, shell=True, stdout=sys.stdout, stderr=subprocess.PIPE
    ) as p:
        _, stderr = p.communicate()
        if p.returncode != 0:
            logger.error(stderr.decode())
            raise subprocess.CalledProcessError(p.returncode, cmd, stderr)
    logger.info("Alphafold3 run complete")
    logger.info("Output files are in %s", output_dir)


def generate_af3_cmd(
    input_json: Union[str, Path],
    output_dir: Union[str, Path],
    model_params: Union[str, Path],
    database_dir: Union[str, Path],
    number_of_models: int = 5,
    interactive: bool = True,
) -> str:
    input_json = Path(input_json)
    output_dir = Path(output_dir)
    return f"""
    docker run {'-it' if interactive else ''} \
    --volume {input_json.parent.resolve()}:/root/af_input \
    --volume {output_dir.resolve()}:/root/af_output \
    --volume {model_params}:/root/models \
    --volume {database_dir}:/root/public_databases \
    --gpus all \
    alphafold3 \
    python run_alphafold.py \
    --json_path=/root/af_input/{input_json.name} \
    --model_dir=/root/models \
    --output_dir=/root/af_output \
    --num_diffusion_samples {number_of_models}
    """


def generate_test_command(interactive: bool = True) -> str:
    return f"""
    docker run {'-it' if interactive else ''} \
    alphafold3 \
    python run_alphafold.py \
    --help
"""

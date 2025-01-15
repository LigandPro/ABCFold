import logging
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Union

from abcfold.boltz1.af3_to_boltz1 import BoltzYaml
from abcfold.boltz1.check_install import check_boltz1

logger = logging.getLogger("logger")


def run_boltz(
    input_json: Union[str, Path],
    output_dir: Union[str, Path],
    save_input: bool = False,
    test: bool = False,
    number_of_models: int = 5,
):
    input_json = Path(input_json)
    output_dir = Path(output_dir)

    logger.debug("Checking if boltz1 is installed")
    check_boltz1()

    with tempfile.TemporaryDirectory() as temp_dir:
        working_dir = Path(temp_dir)
        if save_input:
            logger.info("Saving input yaml file and msa to the output directory")
            working_dir = output_dir

        boltz_yaml = BoltzYaml(working_dir)
        boltz_yaml.json_to_yaml(input_json)
        out_file = working_dir.joinpath(f"{input_json.stem}.yaml")

        boltz_yaml.write_yaml(out_file)
        logger.info("Running Boltz1")
        cmd = (
            generate_boltz_command(out_file, output_dir, number_of_models)
            if not test
            else generate_test_command()
        )

        with subprocess.Popen(
            cmd,
            stdout=sys.stdout,
            stderr=subprocess.PIPE,
        ) as proc:
            _, stderr = proc.communicate()
            if proc.returncode != 0:
                if proc.stderr:
                    logger.error(stderr.decode())
                raise subprocess.CalledProcessError(proc.returncode, proc.args)

        logger.info("Boltz1 run complete")
        logger.info("Output files are in %s", output_dir)


def generate_boltz_command(
    input_yaml: Union[str, Path],
    output_dir: Union[str, Path],
    number_of_models: int = 5,
):
    return [
        "boltz",
        "predict",
        str(input_yaml),
        "--out_dir",
        str(output_dir),
        "--override",
        "--write_full_pae",
        "--write_full_pde",
        "--diffusion_samples",
        str(number_of_models),
    ]


def generate_test_command():
    return [
        "boltz",
        "predict",
        "--help",
    ]

import logging
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Union

from af3_mmseqs2.boltz1.af3_to_boltz1 import BoltzYaml
from af3_mmseqs2.boltz1.check_install import check_boltz1

logger = logging.getLogger("logger")


def run_boltz(
    input_json: Union[str, Path],
    output_dir: Union[str, Path],
    save_input: bool = False,
    test: bool = False,
):
    input_json = Path(input_json)
    output_dir = Path(output_dir)
    logger.info("Running Boltz1")
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

        cmd = (
            generate_boltz_command(out_file, output_dir)
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
):
    return [
        "boltz",
        "predict",
        str(input_yaml),
        "--out_dir",
        str(output_dir),
        "--override",
        # Add more options here
    ]


def generate_test_command():
    return [
        "boltz",
        "predict",
        "--help",
    ]

import logging
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Union

from src.boltz1.check_install import check_chai1
from src.chai1.af3_to_chai import ChaiFasta

logger = logging.getLogger("logger")


def run_chai(
    input_json: Union[str, Path],
    output_dir: Union[str, Path],
    save_input: bool = False,
    test: bool = False,
):
    input_json = Path(input_json)
    output_dir = Path(output_dir)
    logger.info("Running CHAI-1")
    logger.debug("Checking if CHAI-1 is installed")
    check_chai1()

    with tempfile.TemporaryDirectory() as temp_dir:
        working_dir = Path(temp_dir)
        if save_input:
            logger.info("Saving input fasta file and msa to the output directory")
            working_dir = output_dir

        chai_fasta = ChaiFasta(working_dir)
        chai_fasta.json_to_fasta(input_json)

        out_fasta = chai_fasta.fasta
        msa_dir = chai_fasta.working_dir
        out_constraints = chai_fasta.constraints

        cmd = (
            generate_chai_command(out_fasta, msa_dir, out_constraints, output_dir)
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

        logger.info("CHAI-1 run complete")
        logger.info("Output files are in %s", output_dir)


def generate_chai_command(
    input_fasta: Union[str, Path],
    msa_dir: Union[str, Path],
    input_constraints: Union[str, Path],
    output_dir: Union[str, Path],
):
    cmd = ["chai", "fold", input_fasta]

    if Path(msa_dir).exists():
        cmd += ["--msa-directory", str(msa_dir)]
    if Path(input_constraints).exists():
        cmd += ["--constraint-path", str(input_constraints)]

    cmd += [str(output_dir)]

    return cmd


def generate_test_command():
    return [
        "chai",
        "fold",
        "--help",
    ]

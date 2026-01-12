import logging
import subprocess
import tempfile
from pathlib import Path
from typing import Union

from abcfold.openfold3.af3_to_openfold3 import OpenfoldJson
from abcfold.openfold3.check_install import ensure_openfold_env

logger = logging.getLogger("logger")


def run_openfold(
    input_json: Union[str, Path],
    output_dir: Union[str, Path],
    save_input: bool = False,
    test: bool = False,
    number_of_models: int = 5,
    num_recycles: int = 10,
) -> bool:
    """
    Run OpenFold 3 using the input JSON file

    Args:
        input_json (Union[str, Path]): Path to the input JSON file
        output_dir (Union[str, Path]): Path to the output directory
        save_input (bool): If True, save the input JSON file and MSA to the output
        directory
        test (bool): If True, run the test command
        number_of_models (int): Number of models to generate

    Returns:
        Bool: True if the OpenFold 3 run was successful, False otherwise

    Raises:
        subprocess.CalledProcessError: If the OpenFold 3 command returns an error


    """
    input_json = Path(input_json)
    output_dir = Path(output_dir)

    logger.debug("Checking if openfold is installed")
    env = ensure_openfold_env()

    with tempfile.TemporaryDirectory() as temp_dir:
        working_dir = Path(temp_dir)
        if save_input:
            logger.info("Saving input yaml file and msa to the output directory")
            working_dir = output_dir

        openfold_json = OpenfoldJson(working_dir)
        openfold_json.json_to_json(input_json)
        runner_yaml = working_dir / "opennfold3_runner.yml"
        openfold_json.write_yaml(runner_yaml)

        for seed in openfold_json.seeds:
            out_file = working_dir.joinpath(f"{input_json.stem}_seed-{seed}.json")

            openfold_json.write_json(out_file)
            logger.info("Running OpenFold 3 using seed: %s", seed)
            openfold_out_dir = output_dir / f"openfold_results_seed-{seed}"
            cmd = (
                generate_openfold_command(
                    out_file,
                    openfold_out_dir,
                    runner_yaml,
                    number_of_models
                )
                if not test
                else generate_openfold_test_command()
            )

            try:
                env.run(cmd)
            except subprocess.CalledProcessError as e:
                stderr = e.stderr or ""
                if stderr:
                    if working_dir.exists():
                        output_err_file = working_dir / "openfold_error.log"
                    else:
                        output_err_file = working_dir.parent / "openfold_error.log"
                    output_err_file.write_text(stderr)
                    logger.error(
                        "OpenFold 3 run failed. Error log is in %s", output_err_file
                    )
                else:
                    logger.error("OpenFold 3 run failed")
                return False

    logger.info("OpenFold 3 run complete")
    logger.info("Output files are in %s", output_dir)
    return True


def generate_openfold_command(
    input_json: Union[str, Path],
    output_dir: Union[str, Path],
    runner_yaml: Union[str, Path],
    number_of_models: int = 5
) -> list:
    """
    Generate the OpenFold 3 command

    Args:
        input_json (Union[str, Path]): Path to the input JSON file
        output_dir (Union[str, Path]): Path to the output directory
        runner_yaml (Union[str, Path]): Path to the runner YAML file
        number_of_models (int): Number of models to generate

    Returns:
        list: The OpenFold 3 command
    """
    return [
        "run_openfold",
        "predict",
        "--query_json", str(input_json),
        "--runner_yaml", str(runner_yaml),
        "--num_diffusion_samples", str(number_of_models),
        "--output_dir", str(output_dir),
        "--use_msa_server", "false"
    ]


def generate_openfold_test_command() -> list:
    """
    Generate the test command for OpenFold 3

    Args:
        None

    Returns:
        list: The OpenFold 3 test command
    """

    return [
        "run_openfold",
        "predict",
        "--help",
    ]

import logging
import subprocess

logger = logging.getLogger(__name__)


def check_af3_install(interactive: bool = True) -> None:
    """
    Check if Alphafold3 is installed by running the help command

    Args:
        interactive (bool): If True, run the docker container in interactive mode

    Raises:
        subprocess.CalledProcessError: If the Alphafold3 help command returns an error

    """
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
https://github.com/google-deepmind/alphafold3 and follow install instructions"
            )

            raise subprocess.CalledProcessError(p.returncode, cmd, stderr)
    logger.info("Alphafold3 is installed")


def generate_test_command(interactive: bool = True) -> str:
    """
    Generate the Alphafold3 help command

    Args:
        interactive (bool): If True, run the docker container in interactive mode

    Returns:
        str: The Alphafold3 help command
    """
    return f"""
    docker run {'-it' if interactive else ''} \
    alphafold3 \
    python run_alphafold.py \
    --help
"""

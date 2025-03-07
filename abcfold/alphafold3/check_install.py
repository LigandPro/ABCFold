import logging
import subprocess

from packaging.version import Version

logger = logging.getLogger(__name__)


AF3_VERSION = "3.0.0"


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

    cmd = generate_version_command()
    with subprocess.Popen(
        cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE
    ) as p:
        stdout, stderr = p.communicate()
        version = str(stdout.strip().decode("utf-8"))

        if Version(version) < Version(AF3_VERSION):
            raise ImportError(
                f"Expected AlphaFold3 version {AF3_VERSION} or later, found {version}"
            )


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


def generate_version_command() -> str:
    """
    Generate the Alphafold3 version command
    """

    return """docker run \
    alphafold3 \
    python -c \
    'from alphafold3.version import __version__ ; print(__version__)'
"""

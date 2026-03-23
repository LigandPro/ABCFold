import logging
import shlex
import subprocess
from pathlib import Path
from typing import Union

from packaging.version import Version

ALPHAFAST_IMAGE = "romerolabduke/alphafast:latest"
CONTAINER_APP_DIR = Path("/app/alphafold")

logger = logging.getLogger(__name__)


def check_af3_install(
    config: dict,
    interactive: bool = True,
    sif_path: Union[str, Path, None] = None,
) -> None:
    """
    Check if the AF3 backend is available.

    Docker mode uses AlphaFast by default. Singularity mode keeps the legacy
    AlphaFold3 image/version check.
    """
    logger.debug("Checking if Alphafold3 is installed")

    if sif_path is not None and sif_path != "None":
        af3_version = config["af3_version"]
        cmd = generate_test_command(config, interactive, sif_path)
        with subprocess.Popen(
            cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE
        ) as proc:
            _, stderr = proc.communicate()
            proc.wait()
            if proc.returncode != 1:
                logger.error(
                    "Alphafold3 is not installed, please go to "
                    "https://github.com/google-deepmind/alphafold3 and follow "
                    "install instructions"
                )
                raise subprocess.CalledProcessError(proc.returncode, cmd, stderr)

        version_cmd = generate_version_command(config, sif_path)
        with subprocess.Popen(
            version_cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE
        ) as proc:
            stdout, _ = proc.communicate()
            version = stdout.strip().decode("utf-8")
            if Version(version) < Version(af3_version):
                raise ImportError(
                    "Expected AlphaFold3 version "
                    f"{af3_version} or later, found {version}"
                )

        logger.info("Alphafold3 is installed")
        return

    logger.debug("Checking if AlphaFast backend is installed")
    cmd = generate_test_command(config, interactive, sif_path)
    result = subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    if result.returncode != 0:
        image = config.get("af3_docker_env", ALPHAFAST_IMAGE)
        logger.error(
            "AlphaFast backend is not available, please install or pull %s",
            image,
        )
        raise subprocess.CalledProcessError(
            result.returncode, cmd, result.stdout, result.stderr
        )
    logger.info("AlphaFast backend is available")


def generate_test_command(
    config: dict,
    interactive: bool = True,
    sif_path: Union[str, Path, None] = None,
):
    """
    Generate the backend help command.
    """
    if sif_path is not None and sif_path != "None":
        return f"""
    singularity exec \
    {sif_path} \
    python /app/alphafold/run_alphafold.py \
    --help
"""

    image = config.get("af3_docker_env", ALPHAFAST_IMAGE)
    cmd = ["docker", "run", "--rm"]
    if interactive:
        cmd.append("-i")
    cmd += [
        image,
        "python",
        str(CONTAINER_APP_DIR / "run_alphafold.py"),
        "--help",
    ]
    return cmd


def generate_version_command(
    config: dict,
    sif_path: Union[str, Path, None] = None,
) -> str:
    """
    Generate the legacy AlphaFold3 version command.
    """
    if sif_path is not None and sif_path != "None":
        return f"""
    singularity exec \
    {sif_path} \
    python -c \
    'from alphafold3.version import __version__ ; print(__version__)'
"""

    image = config.get("af3_docker_env", ALPHAFAST_IMAGE)
    return shlex.join(
        [
            "docker",
            "run",
            "--rm",
            image,
            "python",
            "-c",
            "from alphafold3.version import __version__ ; print(__version__)",
        ]
    )

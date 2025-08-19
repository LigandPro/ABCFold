import logging
import subprocess
import sys

logger = logging.getLogger("logger")

BOLTZ_VERSION = "2.2.0"


def check_boltz():
    try:
        import boltz as _  # noqa F401

        cmd = [sys.executable, "-m", "pip", "show", "boltz"]
        with subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        ) as proc:
            stdout, stderr = proc.communicate()
            if proc.returncode != 0:
                if "Package(s) not found:" in stderr.decode():

                    raise ModuleNotFoundError(
                        "Boltz package not found."
                    )
                raise subprocess.CalledProcessError(proc.returncode, cmd, stderr)

            version = None
            for line in stdout.decode().split("\n"):
                if line.startswith("Version:"):
                    version = line.split(":", 1)[1].strip()
                    break

            if version != BOLTZ_VERSION:
                raise ImportError(
                    f"Expected boltz version {BOLTZ_VERSION}, found {version}"
                )

    except (ImportError, ModuleNotFoundError):

        logger.info("Installing boltz package")
        cmd = [
            sys.executable,
            "-m",
            "pip",
            "install",
            f"boltz=={BOLTZ_VERSION}",
            "cuequivariance_torch",
            "cuequivariance_ops_torch-cu12",
            "--no-cache-dir",

        ]

        logger.info("Running %s", " ".join(cmd))
        with subprocess.Popen(
            cmd,
            stdout=sys.stdout,
            stderr=subprocess.PIPE,
        ) as proc:
            proc.wait()
            if proc.returncode != 0:
                if proc.stderr:
                    logger.error(proc.stderr.read().decode())
                raise subprocess.CalledProcessError(proc.returncode, proc.args)

    logger.info(f"Running Boltz version: {BOLTZ_VERSION}")

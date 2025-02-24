import logging
import subprocess
import sys

logger = logging.getLogger("logger")

BOLTZ_VERSION = "0.4.1"


def check_boltz1():
    try:
        import boltz as _  # noqa F401
    except (ImportError, ModuleNotFoundError):

        logger.info("Installing boltz package")
        cmd = [
            sys.executable,
            "-m",
            "pip",
            "install",
            f"boltz=={BOLTZ_VERSION}",
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

import subprocess
import sys

from af3_mmseqs2.af3_script_utils import setup_logger

LOGGER = setup_logger()

if __name__ == "__main__":
    try:
        import boltz as _  # noqa F401
    except ImportError or ModuleNotFoundError:
        try:
            import chai_lab as _  # noqa F401

            no_deps = True
        except ImportError or ModuleNotFoundError:
            no_deps = False
        LOGGER.info("Installing boltz package")
        LOGGER.info("No dependencies will be installed") if no_deps else None
        cmd = [sys.executable, "-m", "pip", "install", "boltz"]

        cmd.append("--no-deps") if no_deps else None
        LOGGER.info("Running %s", " ".join(cmd))
        with subprocess.Popen(
            cmd,
            stdout=sys.stdout,
            stderr=subprocess.PIPE,
        ) as proc:
            if proc.returncode != 0:
                if proc.stderr:
                    LOGGER.error(proc.stderr.read().decode())
                raise subprocess.CalledProcessError(proc.returncode, proc.args)

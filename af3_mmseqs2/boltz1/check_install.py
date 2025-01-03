import logging
import subprocess
import sys

logger = logging.getLogger("logger")


def check_boltz1():
    try:
        import boltz as _  # noqa F401
    except ImportError or ModuleNotFoundError:
        try:
            import chai_lab as _  # noqa F401

            no_deps = True
        except ImportError or ModuleNotFoundError:
            no_deps = False
        logger.info("Installing boltz package")
        logger.info("No dependencies will be installed") if no_deps else None
        cmd = [sys.executable, "-m", "pip", "install", "boltz"]

        cmd.append("--no-deps") if no_deps else None
        logger.info("Running %s", " ".join(cmd))
        with subprocess.Popen(
            cmd,
            stdout=sys.stdout,
            stderr=subprocess.PIPE,
        ) as proc:
            if proc.returncode != 0:
                if proc.stderr:
                    logger.error(proc.stderr.read().decode())
                raise subprocess.CalledProcessError(proc.returncode, proc.args)


def check_chai1():
    try:
        import chai_lab as _  # noqa F401
    except ImportError or ModuleNotFoundError:
        try:
            import boltz1 as _  # noqa F401

            no_deps = True
        except ImportError or ModuleNotFoundError:
            no_deps = False
        logger.info("Installing chai_lab package")
        logger.info("No dependencies will be installed") if no_deps else None
        cmd = [sys.executable, "-m", "pip", "install", "chai_lab"]
        cmd.append("--no-deps") if no_deps else None
        logger.info("Running %s", " ".join(cmd))
        with subprocess.Popen(
            cmd,
            stdout=sys.stdout,
            stderr=subprocess.PIPE,
        ) as proc:
            if proc.returncode != 0:
                if proc.stderr:
                    logger.error(proc.stderr.read().decode())
                raise subprocess.CalledProcessError(proc.returncode, proc.args)

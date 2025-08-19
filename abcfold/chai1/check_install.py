import logging
import subprocess
import sys

logger = logging.getLogger("logger")


CHAI_VERSION = "0.6.1"
CHAI_VERSION = "0.6.1"


def check_chai1():
    try:
        import chai_lab as _  # noqa F40

        cmd = [sys.executable, "-m", "pip", "show", "chai_lab"]
        with subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        ) as proc:
            stdout, stderr = proc.communicate()
            if proc.returncode != 0:
                if "Package(s) not found:" in stderr.decode():

                    raise ModuleNotFoundError(
                        "Chai_lab package not found."
                    )
                raise subprocess.CalledProcessError(proc.returncode, cmd, stderr)

            version = None
            for line in stdout.decode().split("\n"):
                if line.startswith("Version:"):
                    version = line.split(":", 1)[1].strip()
                    break

            if version != CHAI_VERSION:
                raise ImportError(
                    f"Expected Chai-1 version {CHAI_VERSION}, found {version}"
                )
    except (ImportError, ModuleNotFoundError):
        try:
            import boltz as _  # noqa F401

            no_deps = True
        except (ImportError, ModuleNotFoundError):
            no_deps = False
        logger.info("Installing chai_lab package")
        logger.info("No dependencies will be installed") if no_deps else None
        cmd = [
            sys.executable,
            "-m",
            "pip",
            "install",
            f"chai_lab=={CHAI_VERSION}",
            "--no-cache-dir",
        ]
        cmd.append("--no-deps") if no_deps else None
        logger.info("Running %s", " ".join(cmd))
        run_command_using_sys(cmd)
        if no_deps:
            cmd = [
                sys.executable,
                "-m",
                "pip",
                "install",
                "antipickle",
                "typer",
                "jaxtyping",
                "beartype",
                "pandera",
                "matplotlib",
            ]
            logger.info("Installing dependencies: %s", " ".join(cmd))
            run_command_using_sys(cmd)
    except Exception as e:
        logger.error("Error while checking or installing chai_lab: %s", e)
        raise ImportError(
            "chai_lab package is not installed. "
            "Please install it using `pip install chai_lab`."
        ) from e

    logger.info(f"Running Chai version: {CHAI_VERSION}")


def run_command_using_sys(command: list[str]) -> None:
    """Run a command using sys.executable."""
    logger.info("Running command: %s", " ".join(command))
    with subprocess.Popen(
        command,
        stdout=sys.stdout,
        stderr=subprocess.PIPE,
    ) as proc:
        proc.wait()
        if proc.returncode != 0:
            if proc.stderr:
                logger.error(proc.stderr.read().decode())
            raise subprocess.CalledProcessError(proc.returncode, proc.args)

import logging

from abcfold.backend_envs import MicromambaEnv

logger = logging.getLogger("logger")

OPENFOLD_VERSION = "0.3.1"
OPENFOLD_ENV = "abcfold-openfold3-py311"


def ensure_openfold_env():
    env = MicromambaEnv(OPENFOLD_ENV)

    # 1. Ensure env exists
    env.create(python_version="3.11")

    # 2. Check installed openfold version
    installed = env.get_installed_version("openfold3")

    # 3. Install Kalign2
    env.conda_install(["kalign2"], channels=["conda-forge", "bioconda"])

    if installed != OPENFOLD_ENV:
        if installed is None:
            logger.info("openfold3 not found. Installing version: %s", OPENFOLD_ENV)
        else:
            logger.info(
                "openfold3 version mismatch (found %s). Installing correct version: %s",
                installed,
                OPENFOLD_ENV,
            )
        env.pip_install([
            f"openfold3=={OPENFOLD_ENV}",
        ])
        # Setup databases
        env.run(["setup_openfold"])
    else:
        logger.info("openfold3 is already up-to-date (%s)", OPENFOLD_ENV)

    # 4. Ensure runtime deps you *actually* need
    env.ensure_package("numpy")
    env.ensure_package("typer")
    env.ensure_package("matplotlib")

    return env

import logging

from abcfold.backend_envs import MicromambaEnv

logger = logging.getLogger("logger")

PROTENIX_VERSION = "0.7.3"
PROTENIX_ENV = "abcfold-protenix-py311"


def ensure_protenix_env():
    env = MicromambaEnv(PROTENIX_ENV)

    # 1. Ensure env exists
    env.create(python_version="3.11")

    # 2. Check installed chai version
    installed = env.get_installed_version("protenix")

    if installed != PROTENIX_VERSION:
        if installed is None:
            logger.info("Protenix not found. Installing version: %s", PROTENIX_ENV)
        else:
            logger.info(
                "Protenix version mismatch (found %s). Installing correct version: %s",
                installed,
                PROTENIX_ENV,
            )
        env.pip_install([f"protenix=={PROTENIX_VERSION}"])
    else:
        logger.info("Protenix is already up-to-date (%s)", PROTENIX_ENV)

    # 3. Ensure runtime deps you *actually* need
    env.ensure_package("numpy")
    env.ensure_package("typer")
    env.ensure_package("matplotlib")

    return env

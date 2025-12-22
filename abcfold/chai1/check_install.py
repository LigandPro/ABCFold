import logging

from abcfold.backend_envs import MicromambaEnv

logger = logging.getLogger("logger")


CHAI_VERSION = "0.6.1"
CHAI_ENV = "abcfold-chai-py311"


def ensure_chai_env():
    env = MicromambaEnv(CHAI_ENV)

    # 1. Ensure env exists
    env.create(python_version="3.11")

    # 2. Check installed chai version
    installed = env.get_installed_version("chai_lab")

    if installed != CHAI_VERSION:
        if installed is None:
            logger.info("chai_lab not found. Installing version: %s", CHAI_VERSION)
        else:
            logger.info(
                "chai_lab version mismatch (found %s). Installing correct version: %s",
                installed,
                CHAI_VERSION,
            )
        env.pip_install([f"chai_lab=={CHAI_VERSION}"])
    else:
        logger.info("chai_lab is already up-to-date (%s)", CHAI_VERSION)

    # 3. Ensure runtime deps you *actually* need
    env.ensure_package("numpy")
    env.ensure_package("typer")
    env.ensure_package("matplotlib")

    return env

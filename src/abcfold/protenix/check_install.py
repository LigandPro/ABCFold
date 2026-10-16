import logging

from abcfold.backend_envs import MicromambaEnv, ensure_backend_env

logger = logging.getLogger("logger")


def ensure_protenix_env(config: dict) -> MicromambaEnv:
    """Verify (never modify) the pinned protenix environment."""
    return ensure_backend_env("protenix", config)

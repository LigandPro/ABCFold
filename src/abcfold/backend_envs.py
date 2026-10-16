"""Isolated backend environments.

Environments are created and populated only by ``abcfold envs build``. During a
prediction ABCFold only *verifies* that the environment exists and carries the
pinned backend version; it never upgrades or downgrades packages in place.
"""

from __future__ import annotations

import json
import logging
import os
import shutil
import subprocess
import sys
import tempfile
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Mapping, Optional

logger = logging.getLogger("logger")

CURRENT_ENV = "@current"
FORBIDDEN_PACKAGES = ("rdkit-pypi",)


class BackendEnvError(RuntimeError):
    """Raised when a backend environment is missing or does not match its pin."""


def supports_cuda_wheels() -> bool:
    return sys.platform.startswith("linux")


def _clean_env(extra: Optional[Mapping[str, str]] = None) -> Dict[str, str]:
    env = dict(os.environ)
    # Never leak an LD_PRELOAD shim (e.g. proxychains) into GPU workloads
    env.pop("LD_PRELOAD", None)
    if extra:
        env.update({k: str(v) for k, v in extra.items() if v is not None})
    return env


class MicromambaEnv:
    """A micromamba environment addressed by name, by prefix path, or the
    current interpreter (``@current``, e.g. inside a backend container)."""

    def __init__(self, env_name: str):
        self.env_name = env_name
        self.is_current = env_name == CURRENT_ENV
        self.is_prefix = not self.is_current and (
            os.sep in env_name or env_name.startswith("~")
        )
        self.micromamba = None if self.is_current else self._find_micromamba()

    @staticmethod
    def _find_micromamba() -> str:
        for candidate in [
            os.environ.get("MAMBA_EXE"),
            shutil.which("micromamba"),
            os.path.expanduser("~/micromamba/bin/micromamba"),
            os.path.expanduser("~/.local/bin/micromamba"),
        ]:
            if candidate and os.path.exists(candidate):
                return candidate
        raise BackendEnvError(
            "micromamba binary not found. Install micromamba or set the backend "
            "env to '@current' when running inside a backend image."
        )

    def _target(self) -> List[str]:
        if self.is_prefix:
            return ["-p", os.path.expanduser(self.env_name)]
        return ["-n", self.env_name]

    def prefix_command(self, command: List[str]) -> List[str]:
        if self.is_current:
            if command and command[0] == "python":
                return [sys.executable, *command[1:]]
            return list(command)
        assert self.micromamba is not None
        return [self.micromamba, "run", *self._target(), *command]

    def get_installed_version(self, package: str) -> Optional[str]:
        code = (
            "from importlib.metadata import version, PackageNotFoundError\n"
            "import sys\n"
            f"pkg={package!r}\n"
            "try:\n"
            "    print(version(pkg))\n"
            "except PackageNotFoundError:\n"
            "    sys.exit(3)"
        )
        try:
            out = subprocess.check_output(
                self.prefix_command(["python", "-c", code]),
                text=True,
                env=_clean_env(),
                stderr=subprocess.DEVNULL,
            )
            return out.strip() or None
        except (subprocess.CalledProcessError, FileNotFoundError):
            return None

    def python_prefix(self) -> Optional[str]:
        try:
            out = subprocess.check_output(
                self.prefix_command(
                    ["python", "-c", "import sys; print(sys.prefix)"]
                ),
                text=True,
                env=_clean_env(),
                stderr=subprocess.DEVNULL,
            )
            return out.strip()
        except (subprocess.CalledProcessError, FileNotFoundError):
            return None

    def env_exists(self) -> bool:
        if self.is_current:
            return True
        if self.is_prefix:
            return Path(os.path.expanduser(self.env_name), "bin", "python").exists()
        assert self.micromamba is not None
        try:
            out = subprocess.check_output(
                [self.micromamba, "env", "list", "--json"], text=True,
                env=_clean_env(),
            )
            prefixes = json.loads(out).get("envs", [])
            return any(Path(p).name == self.env_name for p in prefixes)
        except (subprocess.CalledProcessError, ValueError):
            return False

    def has_executable(self, name: str) -> bool:
        code = f"import shutil,sys; sys.exit(0 if shutil.which({name!r}) else 1)"
        try:
            subprocess.check_call(
                self.prefix_command(["python", "-c", code]),
                env=_clean_env(),
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            return True
        except (subprocess.CalledProcessError, FileNotFoundError):
            return False

    def run(
        self,
        command: List[str],
        capture_output: bool = False,
        quiet: bool = False,
        extra_env: Optional[Mapping[str, str]] = None,
        log_file: Optional[Path] = None,
    ) -> Optional[str]:
        """Run a command inside the env.

        stdout is streamed (and returned when ``capture_output``); stderr is
        captured so that a failure carries the backend's error message.
        """
        cmd = self.prefix_command(command)
        env = _clean_env(extra_env)
        stdout_lines: List[str] = []
        stderr_lines: List[str] = []

        def pump(stream, sink, buffer):
            for line in stream:
                buffer.append(line)
                if not quiet:
                    sink.write(line)
                    sink.flush()

        with subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            errors="replace",
            env=env,
        ) as proc:
            assert proc.stdout is not None and proc.stderr is not None
            err_thread = threading.Thread(
                target=pump, args=(proc.stderr, sys.stderr, stderr_lines),
                daemon=True,
            )
            err_thread.start()
            pump(proc.stdout, sys.stdout, stdout_lines)
            proc.wait()
            err_thread.join()
        stdout, stderr = "".join(stdout_lines), "".join(stderr_lines)
        if log_file is not None:
            Path(log_file).write_text(stdout + "\n" + stderr)
        if proc.returncode != 0:
            raise subprocess.CalledProcessError(
                proc.returncode, cmd, output=stdout, stderr=stderr
            )
        return stdout if capture_output else None


@dataclass
class BackendEnvSpec:
    name: str
    package: str
    version: str
    env: str
    python: str = "3.11"
    pip: List[str] = field(default_factory=list)
    conda: List[str] = field(default_factory=list)
    overrides: List[str] = field(default_factory=list)
    torch_backend: Optional[str] = None

    @classmethod
    def from_settings(cls, name: str, pins: Mapping) -> "BackendEnvSpec":
        return cls(
            name=name,
            package=pins["package"],
            version=str(pins["version"]),
            env=pins.get("env", f"abcfold2-{name}"),
            python=str(pins.get("python", "3.11")),
            pip=list(pins.get("pip", [])),
            conda=list(pins.get("conda", [])),
            overrides=list(pins.get("overrides", [])),
            torch_backend=pins.get("torch_backend"),
        )


def build_commands(
    spec: BackendEnvSpec,
    micromamba: str = "micromamba",
    uv: Optional[str] = "uv",
    python_path: Optional[str] = None,
    overrides_file: Optional[str] = None,
) -> List[List[str]]:
    """Commands that create and populate a backend env (pure, for testing)."""
    target = ["-p", spec.env] if os.sep in spec.env else ["-n", spec.env]
    channels = ["-c", "conda-forge", "-c", "bioconda"]
    cmds = [[micromamba, "create", "-y", *target, *channels, f"python={spec.python}",
             *spec.conda]]
    py = python_path or f"<{spec.env}>/bin/python"
    if uv:
        install = [uv, "pip", "install", "--python", py]
        if spec.torch_backend:
            install += ["--torch-backend", spec.torch_backend]
        if spec.overrides:
            install += ["--override", overrides_file or "<overrides.txt>"]
        cmds.append([*install, *spec.pip])
        cmds.append([uv, "pip", "uninstall", "--python", py, *FORBIDDEN_PACKAGES])
    else:
        install = [micromamba, "run", *target, "python", "-m", "pip", "install"]
        if spec.torch_backend:
            install += [
                "--extra-index-url",
                f"https://download.pytorch.org/whl/{spec.torch_backend}",
            ]
        cmds.append([*install, *spec.pip, *spec.overrides])
        cmds.append([micromamba, "run", *target, "python", "-m", "pip",
                     "uninstall", "-y", *FORBIDDEN_PACKAGES])
    return cmds


def build_env(spec: BackendEnvSpec, dry_run: bool = False) -> List[List[str]]:
    """Create the env and install the pinned packages. Refuses to touch an
    existing env whose backend version differs from the pin."""
    env = MicromambaEnv(spec.env)
    if env.is_current:
        raise BackendEnvError("Cannot build the '@current' environment")
    uv = shutil.which("uv")
    if env.env_exists():
        installed = env.get_installed_version(spec.package)
        if installed == spec.version:
            logger.info("%s env %s already has %s==%s", spec.name, spec.env,
                        spec.package, installed)
            return []
        if installed is not None:
            raise BackendEnvError(
                f"Env {spec.env} has {spec.package}=={installed}, pin is "
                f"{spec.version}. ABCFold does not upgrade existing envs; build a "
                f"new env (set [backends.{spec.name}] env = ...) instead."
            )
    with tempfile.TemporaryDirectory() as tmp:
        overrides_file = None
        if spec.overrides:
            overrides_file = str(Path(tmp, "overrides.txt"))
            Path(overrides_file).write_text("\n".join(spec.overrides) + "\n")
        assert env.micromamba is not None
        cmds = build_commands(spec, micromamba=env.micromamba, uv=uv,
                              overrides_file=overrides_file)
        if dry_run:
            return cmds
        create, *rest = cmds
        if not env.env_exists():
            subprocess.check_call(create, env=_clean_env())
        prefix = env.python_prefix()
        if prefix is None:
            raise BackendEnvError(f"Could not locate the python of env {spec.env}")
        cmds = build_commands(spec, micromamba=env.micromamba, uv=uv,
                              python_path=str(Path(prefix, "bin", "python")),
                              overrides_file=overrides_file)
        subprocess.check_call(cmds[1], env=_clean_env())
        subprocess.call(cmds[2], env=_clean_env())
    return cmds


def verify_env(spec: BackendEnvSpec, allow_mismatch: bool = False) -> str:
    """Check (never modify) a backend env. Returns the installed version."""
    env = MicromambaEnv(spec.env)
    if not env.env_exists():
        raise BackendEnvError(
            f"{spec.name} env '{spec.env}' does not exist. Build it with "
            f"`abcfold envs build {spec.name}`."
        )
    installed = env.get_installed_version(spec.package)
    if installed is None:
        raise BackendEnvError(
            f"{spec.package} is not installed in env '{spec.env}'. Build it with "
            f"`abcfold envs build {spec.name}` (or point the backend at another env)."
        )
    if installed != spec.version:
        msg = (
            f"{spec.package}=={installed} in env '{spec.env}' does not match the "
            f"pinned version {spec.version}"
        )
        if not allow_mismatch:
            raise BackendEnvError(
                msg + ". ABCFold does not upgrade envs at run time; build a new env "
                "or override the pin in your config file."
            )
        logger.warning(msg)
    for forbidden in FORBIDDEN_PACKAGES:
        if env.get_installed_version(forbidden) is not None:
            raise BackendEnvError(
                f"Env '{spec.env}' contains {forbidden}, which shadows rdkit. "
                f"Remove it: micromamba run -n {spec.env} pip uninstall -y {forbidden}"
            )
    return installed


def ensure_backend_env(name: str, config: Mapping) -> MicromambaEnv:
    """Verify the env of ``name`` using the runtime config and return it."""
    settings = config.get("_settings")
    if settings is None:
        from abcfold.settings import load_settings

        settings = load_settings()
    spec = BackendEnvSpec.from_settings(name, settings.backend(name))
    env = MicromambaEnv(spec.env)
    if (
        not env.is_current
        and not env.env_exists()
        and settings.get("build_missing_envs", False)
    ):
        logger.info("Building missing %s env %s", name, spec.env)
        build_env(spec)
    allow = bool(config.get("allow_version_mismatch", False))
    if env.is_current:
        installed = env.get_installed_version(spec.package) or "unknown"
    else:
        installed = verify_env(spec, allow_mismatch=allow)
    env.installed_version = installed  # type: ignore[attr-defined]
    logger.info("%s %s (env %s)", name, installed, spec.env)
    return env

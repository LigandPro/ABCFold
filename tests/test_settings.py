from abcfold.abcfold import build_run_parser, resolve_settings
from abcfold.backend_envs import (FORBIDDEN_PACKAGES, BackendEnvSpec,
                                  build_commands)
from abcfold.settings import load_backend_pins, load_settings


def test_defaults_have_no_none_strings():
    settings = load_settings(environ={})
    assert all(v != "None" for v in settings.values.values())
    assert settings.get("model_params") is None
    assert settings.get("msa_server_url") == "https://api.colabfold.com"
    assert settings.get("min_msa_rows") == 10


def test_parser_parses_with_unset_config(tmp_path):
    """Defect 1: a None/"None" default in the config crashed argparse."""
    cfg = tmp_path / "legacy.ini"
    cfg.write_text("[Boltz]\nboltz_max_parallel_samples = None\n"
                   "boltz_num_workers = 3\n[Weights]\nmodel_params = None\n")
    input_json = tmp_path / "in.json"
    input_json.write_text("{}")
    args = build_run_parser().parse_args(
        [str(input_json), str(tmp_path / "out"), "--config-file", str(cfg), "-b"]
    )
    settings = resolve_settings(args)
    assert args.boltz_max_parallel_samples is None
    assert args.boltz_num_workers == "3" or args.boltz_num_workers == 3
    assert args.model_params is None
    assert settings.source_file == cfg


def test_cli_flags_override_config(tmp_path):
    cfg = tmp_path / "c.toml"
    cfg.write_text('[msa]\nmsa_server_url = "http://cfg"\n')
    input_json = tmp_path / "in.json"
    input_json.write_text("{}")
    args = build_run_parser().parse_args([
        str(input_json), str(tmp_path / "o"), "--config-file", str(cfg),
        "--msa_server_url", "http://cli",
    ])
    assert resolve_settings(args).get("msa_server_url") == "http://cli"
    args = build_run_parser().parse_args([
        str(input_json), str(tmp_path / "o"), "--config-file", str(cfg)])
    assert resolve_settings(args).get("msa_server_url") == "http://cfg"


def test_config_versions_are_honoured(tmp_path):
    """Defect 2: versions in the config file were ignored."""
    cfg = tmp_path / "c.toml"
    cfg.write_text('[backends.boltz]\nversion = "2.1.0"\nenv = "my-boltz"\n')
    boltz = load_settings(cfg, environ={}).backend("boltz")
    assert boltz["version"] == "2.1.0"
    assert boltz["env"] == "my-boltz"
    assert any(spec.startswith("boltz") and "==2.1.0" in spec for spec in boltz["pip"])


def test_legacy_ini_versions_and_env_override(tmp_path):
    cfg = tmp_path / "c.ini"
    cfg.write_text("[Versions]\nchai_version = 0.6.0\n[Environments]\n"
                   "protenix_env = px-old\n")
    settings = load_settings(cfg, environ={"ABCFOLD_PROTENIX_VERSION": "1.0.4",
                                           "ABCFOLD_MIN_MSA_ROWS": "0"})
    assert settings.backend("chai1")["version"] == "0.6.0"
    assert settings.backend("protenix")["env"] == "px-old"
    assert settings.backend("protenix")["version"] == "1.0.4"
    assert settings.get("min_msa_rows") == 0


def test_settings_never_write(tmp_path):
    cfg = tmp_path / "c.toml"
    cfg.write_text('[paths]\nmodel_params = "/x"\n')
    before = cfg.read_text()
    load_settings(cfg, environ={}).apply_overrides({"model_params": "/y"})
    assert cfg.read_text() == before
    assert list(tmp_path.iterdir()) == [cfg]


def test_backend_pins_are_exact_and_rdkit_pypi_free():
    pins = load_backend_pins()
    for name in ("boltz", "chai1", "protenix", "openfold3"):
        spec = pins[name]
        assert any(f"=={spec['version']}" in p for p in spec["pip"]), name
        assert not any("rdkit-pypi" in p for p in spec["pip"]), name
    assert pins["protenix"]["model"] == "protenix_base_default_v1.0.0"


def test_build_commands_remove_rdkit_pypi():
    spec = BackendEnvSpec.from_settings("protenix", load_backend_pins()["protenix"])
    cmds = build_commands(spec, python_path="/env/bin/python")
    assert cmds[0][:2] == ["micromamba", "create"]
    install = cmds[1]
    assert install[:3] == ["uv", "pip", "install"]
    assert "--torch-backend" in install
    assert "protenix==2.0.0" in install
    assert cmds[2][-len(FORBIDDEN_PACKAGES):] == list(FORBIDDEN_PACKAGES)
    assert "uninstall" in cmds[2]


def test_runtime_config_exposes_legacy_keys():
    cfg = load_settings(environ={}).runtime_config()
    assert cfg["boltz_env"] == "abcfold2-boltz"
    assert cfg["protenix_model"] == "protenix_base_default_v1.0.0"
    assert cfg["openfold_checkpoint"]
    assert cfg["_settings"] is not None

"""``abcfold`` command line: run, msa, batch and envs subcommands.

``abcfold input.json out_dir [flags]`` (no subcommand) is the same as
``abcfold run input.json out_dir [flags]``.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import List, Optional

SUBCOMMANDS = ("run", "msa", "batch", "envs")

logger = logging.getLogger("logger")


def _msa_main(argv: List[str]) -> int:
    from abcfold.msa.export import FORMATS, export_msas
    from abcfold.msa.resolve import (SOURCES, MsaOptions, parse_chain_paths,
                                     resolve_msas)
    from abcfold.msa.stats import write_msa_stats
    from abcfold.scripts.abc_script_utils import setup_logger
    from abcfold.settings import load_settings

    setup_logger()
    parser = argparse.ArgumentParser(
        prog="abcfold msa",
        description="Compute or collect MSAs for an AlphaFold 3 input JSON and "
        "write them back into the JSON (plus msa_stats.json and optional "
        "backend-specific files).",
    )
    parser.add_argument("input_json")
    parser.add_argument("output_dir")
    parser.add_argument("--source", choices=[s for s in SOURCES if s != "auto"],
                        default="server")
    parser.add_argument("--msa_a3m", nargs="+")
    parser.add_argument("--msa_paired_a3m", nargs="+")
    parser.add_argument("--af3_data_json")
    parser.add_argument("--msa_cache_dir")
    parser.add_argument("--msa_server_url")
    parser.add_argument("--no_paired_msa", action="store_true")
    parser.add_argument("--no_env", action="store_true",
                        help="Do not search the ColabFold environmental databases")
    parser.add_argument("--format", nargs="+", default=[],
                        choices=list(FORMATS) + ["all"],
                        help="Also write backend-native MSA files")
    parser.add_argument("--config-file", dest="config_file")
    args = parser.parse_args(argv)

    settings = load_settings(args.config_file).apply_overrides({
        "msa_cache_dir": args.msa_cache_dir,
        "msa_server_url": args.msa_server_url,
    })
    options = MsaOptions(
        source=args.source,
        cache_dir=settings.get("msa_cache_dir"),
        server_url=settings.get("msa_server_url"),
        user_agent=settings.get("msa_user_agent", "abcfold"),
        paired=not args.no_paired_msa,
        use_env=not args.no_env,
        custom_a3m=parse_chain_paths(args.msa_a3m),
        custom_paired_a3m=parse_chain_paths(args.msa_paired_a3m),
        af3_data_json=args.af3_data_json,
    )
    params = json.loads(Path(args.input_json).read_text())
    result = resolve_msas(params, options)
    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)
    out_json = out / f"{Path(args.input_json).stem}_msa.json"
    out_json.write_text(json.dumps(result.params, indent=2))
    write_msa_stats(out / "msa_stats.json", result.chains, result.source,
                    result.seconds)
    formats = list(FORMATS) if "all" in args.format else args.format
    if formats:
        export_msas(result.params, out / "msa", formats)
    for chain, stats in result.chains.items():
        logger.info("chain %s: depth %d (paired %d)%s", chain, stats["depth"],
                    stats["paired_depth"], " [cached]" if stats["cached"] else "")
    logger.info("Wrote %s", out_json)
    return 0


def _batch_main(argv: List[str]) -> int:
    from abcfold.batch import run_batch
    from abcfold.msa.resolve import MsaOptions
    from abcfold.scripts.abc_script_utils import setup_logger
    from abcfold.settings import load_settings

    setup_logger()
    parser = argparse.ArgumentParser(
        prog="abcfold batch",
        description="Run many jobs from a CSV/JSON manifest. Flags after '--' "
        "are passed to every `abcfold run`.",
    )
    parser.add_argument("manifest")
    parser.add_argument("output_dir")
    parser.add_argument("--max-parallel", "--max_parallel", dest="max_parallel",
                        type=int, default=1)
    parser.add_argument("--gpus", default=None,
                        help="GPU ids handed out round-robin to parallel jobs, "
                        "e.g. '1' or '1,2'")
    parser.add_argument("--msa", default="server",
                        choices=["server", "auto", "none"])
    parser.add_argument("--msa_cache_dir")
    parser.add_argument("--msa_server_url")
    parser.add_argument("--force", action="store_true",
                        help="Re-run jobs that already completed")
    parser.add_argument("--config-file", dest="config_file")
    if "--" in argv:
        split = argv.index("--")
        argv, run_args = argv[:split], argv[split + 1:]
    else:
        run_args = []
    args = parser.parse_args(argv)
    settings = load_settings(args.config_file).apply_overrides({
        "msa_cache_dir": args.msa_cache_dir,
        "msa_server_url": args.msa_server_url,
    })
    options = MsaOptions(
        source="server",
        cache_dir=settings.get("msa_cache_dir"),
        server_url=settings.get("msa_server_url"),
        user_agent=settings.get("msa_user_agent", "abcfold"),
    )
    if args.config_file:
        run_args = ["--config-file", args.config_file, *run_args]
    for key in ("msa_cache_dir", "msa_server_url"):
        if getattr(args, key):
            run_args = [f"--{key}", getattr(args, key), *run_args]
    status = run_batch(
        args.manifest, args.output_dir, max_parallel=args.max_parallel,
        gpus=args.gpus, msa=args.msa, msa_options=options, run_args=run_args,
        force=args.force,
    )
    counts = status.get("counts", {})
    logger.info("Batch finished: %s", counts)
    failed = sum(v for k, v in counts.items() if k not in ("ok",))
    return 0 if failed == 0 else 2


def _envs_main(argv: List[str]) -> int:
    from abcfold.backend_envs import (BackendEnvError, BackendEnvSpec,
                                      build_env, verify_env)
    from abcfold.settings import BACKEND_NAMES, load_settings

    parser = argparse.ArgumentParser(
        prog="abcfold envs",
        description="Show, check or build the pinned backend environments.",
    )
    parser.add_argument("action", choices=["show", "check", "build"])
    parser.add_argument("backends", nargs="*")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--config-file", dest="config_file")
    args = parser.parse_args(argv)
    settings = load_settings(args.config_file)
    names = args.backends or [n for n in BACKEND_NAMES if n != "alphafold3"]
    code = 0
    for name in names:
        pins = settings.backend(name)
        if args.action == "show":
            print(f"{name}: {pins.get('package')}=={pins.get('version')} "
                  f"env={pins.get('env')}")
            continue
        if "pip" not in pins:
            print(f"{name}: not managed by ABCFold (container)")
            continue
        spec = BackendEnvSpec.from_settings(name, pins)
        try:
            if args.action == "check":
                version = verify_env(spec)
                print(f"{name}: OK {spec.package}=={version} ({spec.env})")
            else:
                cmds = build_env(spec, dry_run=args.dry_run)
                for cmd in cmds:
                    print(" ".join(cmd))
                if not args.dry_run:
                    print(f"{name}: built {spec.env}")
        except BackendEnvError as exc:
            print(f"{name}: {exc}", file=sys.stderr)
            code = 1
    return code


def main(argv: Optional[List[str]] = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] in ("-h", "--help"):
        print(__doc__)
        print("Subcommands: " + ", ".join(SUBCOMMANDS))
        print("Use `abcfold <subcommand> --help` for details.")
        return 0
    command = argv[0] if argv and argv[0] in SUBCOMMANDS else "run"
    rest = argv[1:] if argv and argv[0] in SUBCOMMANDS else argv
    if command == "msa":
        return _msa_main(rest)
    if command == "batch":
        return _batch_main(rest)
    if command == "envs":
        return _envs_main(rest)
    from abcfold.abcfold import main as run_main

    return run_main(rest)


if __name__ == "__main__":
    sys.exit(main())

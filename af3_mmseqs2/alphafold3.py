import configparser
import json
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Union

from af3_mmseqs2.add_mmseqs_msa import add_msa_to_json
from af3_mmseqs2.af3_script_utils import make_dir, setup_logger
from af3_mmseqs2.argparse_utils import (alphafold_argparse_util,
                                        boltz_argparse_util,
                                        custom_template_argpase_util,
                                        main_argpase_util,
                                        mmseqs2_argparse_util)
from af3_mmseqs2.processoutput.boltz import BoltzOutput
from af3_mmseqs2.run_boltz import run_boltz

logger = setup_logger()


def run_alphafold3(
    input_json: Union[str, Path],
    output_dir: Union[str, Path],
    model_params: Union[str, Path],
    database_dir: Union[str, Path],
    interactive: bool = True,
) -> None:

    input_json = Path(input_json)
    output_dir = Path(output_dir)
    cmd = generate_af3_cmd(
        input_json=input_json,
        output_dir=output_dir,
        model_params=model_params,
        database_dir=database_dir,
        interactive=interactive,
    )

    logger.info("Running Alphafold3")
    with subprocess.Popen(
        cmd, shell=True, stdout=sys.stdout, stderr=subprocess.PIPE
    ) as p:
        _, stderr = p.communicate()
        if p.returncode != 0:
            logger.error(stderr.decode())
            raise subprocess.CalledProcessError(p.returncode, cmd, stderr)
    logger.info("Alphafold3 run complete")
    logger.info("Output files are in %s", output_dir)


def generate_af3_cmd(
    input_json: Union[str, Path],
    output_dir: Union[str, Path],
    model_params: Union[str, Path],
    database_dir: Union[str, Path],
    interactive: bool = True,
) -> str:
    input_json = Path(input_json)
    output_dir = Path(output_dir)
    return rf"""
    docker run {'-it' if interactive else ''} \
    --volume {input_json.parent.resolve()}:/root/af_input \
    --volume {output_dir.resolve()}:/root/af_output \
    --volume {model_params}:/root/models \
    --volume {database_dir}:/root/public_databases \
    --gpus all \
    alphafold3 \
    python run_alphafold.py \
    --json_path=/root/af_input/{input_json.name} \
    --model_dir=/root/models \
    --output_dir=/root/af_output
    """


def main():
    """Run AlphaFold3"""
    import argparse

    parser = argparse.ArgumentParser(description="Run AlphaFold3 / Boltz1 / Chai_1")

    # Load defaults from config file
    defaults = {}
    config_file = Path(__file__).parent.joinpath("data", "config.ini")
    config = configparser.SafeConfigParser()

    if config_file.exists():
        config.read(str(config_file))
        defaults.update(dict(config.items("Databases")))

    parser = main_argpase_util(parser)
    parser = alphafold_argparse_util(parser)
    parser = boltz_argparse_util(parser)
    parser = mmseqs2_argparse_util(parser)
    parser = custom_template_argpase_util(parser)

    parser.set_defaults(**defaults)
    args = parser.parse_args()

    make_dir(args.output_dir)

    updated_config = False
    if args.model_params != defaults["model_params"]:
        config.set("Databases", "model_params", args.model_params)
        updated_config = True
    if args.database_dir != defaults["database_dir"]:
        config.set("Databases", "database_dir", args.database_dir)
        updated_config = True
    if updated_config:
        with open(config_file, "w") as f:
            config.write(f)

    if not args.database_dir or not Path(args.database_dir).exists():
        logger.error(f"Database directory not found: {args.database_dir}")
        sys.exit(1)
    elif not args.model_params or not Path(args.model_params).exists():
        logger.error(f"Model parameters directory not found: {args.model_params}")
        sys.exit(1)

    with open(args.input_json, "r") as f:
        af3_json = json.load(f)

    with tempfile.TemporaryDirectory() as temp_dir_str:
        temp_dir = Path(temp_dir_str)
        if args.mmseqs2:
            if not args.output_json:
                input_json = Path(args.input_json)
                run_json = temp_dir.joinpath(
                    input_json.name.replace(".json", "_mmseqs.json")
                )
            else:
                run_json = Path(args.output_json)

            af3_json = add_msa_to_json(
                input_json=input_json,
                templates=args.templates,
                num_templates=args.num_templates,
                custom_template=args.custom_template,
                custom_template_chain=args.custom_template_chain,
                target_id=args.target_id,
                af3_json=af3_json,
                output_json=run_json,
                to_file=True,
            )

        else:
            run_json = Path(args.input_json)

        args.chai_1 = False
        if not args.alphafold3 and not args.boltz1 and not args.chai_1:  #
            args.alphafold3 = True

        if args.alphafold3:

            run_alphafold3(
                input_json=run_json,
                output_dir=args.output_dir,
                model_params=args.model_params,
                database_dir=args.database_dir,
            )
        if args.boltz1:
            run_boltz(
                input_json=run_json,
                output_dir=args.output_dir,
                save_input=args.save_input,
            )
            bolt_out_dir = list(Path(args.output_dir).glob("boltz_results*"))[0]
            _ = BoltzOutput(bolt_out_dir)


if __name__ == "__main__":
    main()

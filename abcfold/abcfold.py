import configparser
import json
import sys
import tempfile
from pathlib import Path

from abcfold.add_mmseqs_msa import add_msa_to_json
from abcfold.af3_script_utils import make_dir, setup_logger
from abcfold.argparse_utils import (alphafold_argparse_util,
                                    boltz_argparse_util, chai_argparse_util,
                                    custom_template_argpase_util,
                                    main_argpase_util, mmseqs2_argparse_util,
                                    prediction_argparse_util)
from abcfold.processoutput.alphafold3 import AlphafoldOutput
from abcfold.processoutput.boltz import BoltzOutput
from abcfold.processoutput.chai import ChaiOutput
from abcfold.run_alphafold3 import run_alphafold3

logger = setup_logger()


def run(args, config, defaults, config_file):
    """Run AlphaFold3"""

    args.output_dir = Path(args.output_dir)

    make_dir(args.output_dir, overwrite=args.override)

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

    name = af3_json.get("name")
    if name is None:
        logger.error("Input JSON must contain a 'name' field")
        sys.exit(1)

    if args.boltz1:
        from abcfold.boltz1.check_install import check_boltz1

        check_boltz1()
    if args.chai1:
        from abcfold.chai1.check_install import check_chai1

        check_chai1()

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

        if not args.alphafold3 and not args.boltz1 and not args.chai1:  #
            args.alphafold3 = True

        if args.alphafold3:

            run_alphafold3(
                input_json=run_json,
                output_dir=args.output_dir,
                model_params=args.model_params,
                database_dir=args.database_dir,
                number_of_models=args.number_of_models,
            )

            # Need to find the name of the af3_dir
            af3_out_dir = list(args.output_dir.iterdir())[0]
            _ = AlphafoldOutput(af3_out_dir, name)

        if args.boltz1:
            from abcfold.run_boltz import run_boltz

            run_boltz(
                input_json=run_json,
                output_dir=args.output_dir,
                save_input=args.save_input,
            )
            bolt_out_dir = list(args.output_dir.glob("boltz_results*"))[0]
            _ = BoltzOutput(bolt_out_dir, name)

        if args.chai1:
            from abcfold.run_chai1 import run_chai

            chai_output_dir = args.output_dir.joinpath("chai1")
            run_chai(
                input_json=run_json,
                output_dir=chai_output_dir,
                save_input=args.save_input,
                number_of_models=args.number_of_models,
            )

            _ = ChaiOutput(chai_output_dir, name)


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Run AlphaFold3 / Boltz1 / Chai-1")

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
    parser = chai_argparse_util(parser)
    parser = mmseqs2_argparse_util(parser)
    parser = custom_template_argpase_util(parser)
    parser = prediction_argparse_util(parser)

    parser.set_defaults(**defaults)
    args = parser.parse_args()

    run(
        args,
        config,
        defaults,
        config_file,
    )


if __name__ == "__main__":
    main()

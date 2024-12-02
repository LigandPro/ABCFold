# start by finding the directory where the alphafold3.py script is located

from add_custom_template import custom_template_argpase_util
from add_mmseqs_msa import mmseqs2_argparse_util, add_msa_to_json
from af3_script_utils import setup_logger
import json
from pathlib import Path
import subprocess

logger = setup_logger()

def run_alphafold3(
    input_json: str | Path,
    output_dir: str | Path,
    model_params: str | Path,
    database_dir: str | Path,
) -> None:
    print(input_json)
    input_json = Path(input_json)
    output_dir = Path(output_dir)
    cmd = rf"""
    docker run -it \
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

    with subprocess.Popen(
        cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE
    ) as p:
        stdout, stderr = p.communicate()
        if p.returncode != 0:
            logger.error(stderr.decode())
            logger.debug(stdout.decode())
            raise subprocess.CalledProcessError(p.returncode, cmd, stderr)

    logger.info(stdout.decode())
    logger.error(stderr.decode())

    logger.info("Alphafold3 run complete")
    logger.info("Output files are in", output_dir)


def af3_argparse_main(parser):
    parser.add_argument("input_json", help="Input sequence file")

    parser.add_argument("output_dir", help="Output directory")
    parser.add_argument("--output_json", help="Output json file")
    # make the vartible saved as database_dir
    parser.add_argument(
        "--database",
        help="The Database directory for the generation of the MSA.",
        required=True,
        dest="database_dir",
    )
    parser.add_argument(
        "--mmseqs2",
        help="Use MMseqs2 for MSA",
        action="store_true",
    )

    parser.add_argument(
        "--model_params",
        help="The directory containing the model parameters",
        required=True,
    )

    mmseqs2_argparse_util(parser)
    custom_template_argpase_util(parser)

    return parser


def main():
    """Run AlphaFold3"""
    import argparse
    parser = argparse.ArgumentParser(description="Run AlphaFold3")

    parser = af3_argparse_main(parser)

    args = parser.parse_args()

    with open(args.input_json, "r") as f:
        af3_json = json.load(f)

    if args.mmseqs2:
        af3_json = add_msa_to_json(
            input_json=args.input_json,
            templates=args.templates,
            num_templates=args.num_templates,
            custom_template=args.custom_template,
            custom_template_chain=args.custom_template_chain,
            target_id=args.target_id,
            af3_json=af3_json,
            output_json=args.output_json,
            to_file=True,
        )

        output_json = (
            args.input_json.replace(".json", "_mmseqs.json")
            if args.output_json is None
            else args.output_json
        )
    else:
        output_json = args.input_json
    run_alphafold3(
        input_json=output_json,
        output_dir=args.output_dir,
        model_params=args.model_params,
        database_dir=args.database_dir,
    )


if __name__ == "__main__":
    main()

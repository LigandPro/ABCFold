# start by finding the directory where the alphafold3.py script is located

from add_custom_template import custom_template, custom_template_argpase_util
from add_mmseqs_msa import add_mmseqs_msa, mmseqs2_argparse_util
import json


def af3_argparse_main(parser):
    parser.add_argument("input_json", help="Input sequence file")
    parser.add_argument("output_dir", help="Output directory")
    add_mmseqs_msa(parser)
    custom_template_argpase_util(parser)

    return parser


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Run AlphaFold 3")
    parser = af3_argparse_main(parser)

    args = parser.parse_args()

    with open(args.input_json, "r") as f:
        af3_json = json.load(f)

    if all(
        [
            x is not None
            for x in [args.target_id, args.custom_template, args.custom_template_chain]
        ]
    ):
        af3_json = custom_template(
            args.input_json,
            args.target_id,
            args.custom_template,
            args.custom_template_chain,
            af3_json=af3_json,
            output_json=None,
            to_file=False,
        )

    if all(
        [
            x is not None
            for x in [
                args.templates,
            ]
        ]
    ):
        af3_json = add_mmseqs_msa(
            args.input_json,
            args.target_id,
            args.templates,
            af3_json=af3_json,
            output_json=None,
            to_file=False,
        )

    # Need to ask adam about the custom template stuff tomorrow

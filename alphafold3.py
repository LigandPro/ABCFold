# start by finding the directory where the alphafold3.py script is located

from add_custom_template import custom_template, custom_template_argpase_util
from add_mmseqs_msa import mmseqs2_argparse_util, add_msa_to_json
import json
import os
from pathlib import Path


def af3_argparse_main(parser):
    parser.add_argument("input_json", help="Input sequence file")
    parser.add_argument("output_dir", help="Output directory")
    parser.add_argument(
        "-m",
        "--mmseqs2",
        help="Use MMseqs2 for MSA",
        action="store_true",
    )
    parser.add_argument(
        "-s",
        "--save_json",
        help="Save the modified json file",
        action="store_true",
        default=False,
    )
    mmseqs2_argparse_util(parser)
    custom_template_argpase_util(parser)

    return parser


def alphafold3_directory_finder():
    # take an input of a user and find the directory where the alphafold3 directory is located
    # this is done by finding the directory where the alphafold3.py script is located

    print("Please enter the directory where the alphafold3 directory is located: ")
    directory = input()
    # get the current working directory
    cwd = os.getcwd()
    print("Current working directory: ", cwd)


if __name__ == "__main__":
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

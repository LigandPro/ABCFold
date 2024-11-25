#!/usr/bin/env python

import os
import time
import tarfile
import random
import logging
import json
from io import StringIO
from typing import Tuple, List

import requests
from tqdm.autonotebook import tqdm
import Bio.PDB
from Bio import pairwise2


logger = logging.getLogger(__name__)

TQDM_BAR_FORMAT = (
    "{l_bar}{bar}| {n_fmt}/{total_fmt} [elapsed: {elapsed} remaining: {remaining}]"
)


def run_mmseqs(
    x,
    prefix,
    use_env=True,
    use_filter=True,
    use_templates=False,
    filter=None,
    use_pairing=False,
    host_url="https://a3m.mmseqs.com",
    num_templates=20,
) -> Tuple[List[str], List[str]]:
    submission_endpoint = "ticket/pair" if use_pairing else "ticket/msa"

    def submit(seqs, mode, N=101):
        n, query = N, ""
        for seq in seqs:
            query += f">{n}\n{seq}\n"
            n += 1

        res = requests.post(
            f"{host_url}/{submission_endpoint}", data={"q": query, "mode": mode}
        )
        try:
            out = res.json()
        except ValueError:
            logger.error(f"Server didn't reply with json: {res.text}")
            out = {"status": "ERROR"}
        return out

    def status(ID):
        res = requests.get(f"{host_url}/ticket/{ID}")
        try:
            out = res.json()
        except ValueError:
            logger.error(f"Server didn't reply with json: {res.text}")
            out = {"status": "ERROR"}
        return out

    def download(ID, path):
        res = requests.get(f"{host_url}/result/download/{ID}")
        with open(path, "wb") as out:
            out.write(res.content)

    # process input x
    seqs = [x] if isinstance(x, str) else x

    # compatibility to old option
    if filter is not None:
        use_filter = filter

    # setup mode
    if use_filter:
        mode = "env" if use_env else "all"
    else:
        mode = "env-nofilter" if use_env else "nofilter"

    if use_pairing:
        mode = ""
        use_templates = False
        use_env = False

    # define path
    path = prefix
    if not os.path.isdir(path):
        os.mkdir(path)

    # call mmseqs2 api
    tar_gz_file = f"{path}/out.tar.gz"
    N, REDO = 101, True

    # deduplicate and keep track of order
    seqs_unique = []
    # TODO this might be slow for large sets
    [seqs_unique.append(x) for x in seqs if x not in seqs_unique]
    Ms = [N + seqs_unique.index(seq) for seq in seqs]
    # lets do it!
    if not os.path.isfile(tar_gz_file):
        TIME_ESTIMATE = 150 * len(seqs_unique)
        with tqdm(total=TIME_ESTIMATE, bar_format=TQDM_BAR_FORMAT) as pbar:
            while REDO:
                pbar.set_description("SUBMIT")

                # Resubmit job until it goes through
                out = submit(seqs_unique, mode, N)
                while out["status"] in ["UNKNOWN", "RATELIMIT"]:
                    sleep_time = 5 + random.randint(0, 5)
                    logger.error(f"Sleeping for {sleep_time}s. Reason: {out['status']}")
                    # resubmit
                    time.sleep(sleep_time)
                    out = submit(seqs_unique, mode, N)

                if out["status"] == "ERROR":
                    raise Exception(
                        "MMseqs2 API is giving errors. Please confirm your input is a valid protein sequence. If error persists, please try again an hour later."
                    )

                if out["status"] == "MAINTENANCE":
                    raise Exception(
                        "MMseqs2 API is undergoing maintenance. Please try again in a few minutes."
                    )

                # wait for job to finish
                ID, TIME = out["id"], 0
                pbar.set_description(out["status"])
                while out["status"] in ["UNKNOWN", "RUNNING", "PENDING"]:
                    t = 5 + random.randint(0, 5)
                    logger.error(f"Sleeping for {t}s. Reason: {out['status']}")
                    time.sleep(t)
                    out = status(ID)
                    pbar.set_description(out["status"])
                    if out["status"] == "RUNNING":
                        TIME += t
                        pbar.update(n=t)

                if out["status"] == "COMPLETE":
                    if TIME < TIME_ESTIMATE:
                        pbar.update(n=(TIME_ESTIMATE - TIME))
                    REDO = False

                if out["status"] == "ERROR":
                    REDO = False
                    raise Exception(
                        f"MMseqs2 API is giving errors. Please confirm your input is a valid protein sequence. If error persists, please try again an hour later."
                    )

            # Download results
            download(ID, tar_gz_file)

    # prep list of a3m files
    if use_pairing:
        a3m_files = [f"{path}/pair.a3m"]
    else:
        a3m_files = [f"{path}/uniref.a3m"]
        if use_env:
            a3m_files.append(f"{path}/bfd.mgnify30.metaeuk30.smag30.a3m")

    # extract a3m files
    if any(not os.path.isfile(a3m_file) for a3m_file in a3m_files):
        with tarfile.open(tar_gz_file) as tar_gz:
            tar_gz.extractall(path)

    # gather a3m lines
    a3m_lines = {}
    for a3m_file in a3m_files:
        update_M, M = True, None
        for line in open(a3m_file, "r"):
            if len(line) > 0:
                if "\x00" in line:
                    line = line.replace("\x00", "")
                    update_M = True
                if line.startswith(">") and update_M:
                    M = int(line[1:].rstrip())
                    update_M = False
                    if M not in a3m_lines:
                        a3m_lines[M] = []
                a3m_lines[M].append(line)

    a3m_lines = ["".join(a3m_lines[n]) for n in Ms]

    tested_pdbs = []
    templates = []
    if use_templates:
        count = 0
        for line in open(f"{path}/pdb70.m8", "r"):
            template = {}
            if count < num_templates:
                p = line.rstrip().split()
                M, pdb, qid, alilen, qstart, qend, tstart, tend, e_value, cigar = (
                    p[0],
                    p[1],
                    p[2],
                    p[3],
                    p[6],
                    p[7],
                    p[8],
                    p[9],
                    p[10],
                    p[12],
                )
                coverage = float(alilen) / len(x)
                pdb_id = pdb.split("_")[0]

                # Use the same template filters as AF3 and only use 1 template per PDB
                if (
                    float(qid) == 1.0
                    and coverage >= 0.95
                    or coverage < 0.1
                    or pdb_id in tested_pdbs
                ):
                    continue

                pdb_id = pdb.split("_")[0]
                cif_str = get_mmcif(pdb_id, pdb.split("_")[1], int(tstart), int(tend))
                template["mmcif"] = cif_str

                template_seq = extract_sequence_from_mmcif(StringIO(cif_str))
                query_indices, template_indices = align_and_map(x, template_seq)

                template["queryIndices"] = query_indices
                template["templateIndices"] = template_indices
                templates.append(template)
                tested_pdbs.append(pdb_id)
                count += 1

    return (a3m_lines, templates) if use_templates else a3m_lines


def get_mmcif(pdb_id, chain_id, start, end):
    pdb_id = pdb_id.lower()
    url_base = "http://www.ebi.ac.uk/pdbe-srv/view/files/"
    url = url_base + pdb_id + ".cif"
    response = requests.get(url)
    text = response.text

    output = "tmp/" + pdb_id + ".cif"
    with open(output, "w") as f:
        f.write(text)

    return _get_mmcif(output, pdb_id, chain_id, start, end)


def _get_mmcif(cif, pdb_id, chain_id, start, end):

    parser = Bio.PDB.MMCIFParser(QUIET=True)
    structure = parser.get_structure(pdb_id, cif)

    # Extract release date from the CIF file
    mmcif_dict = parser._mmcif_dict
    headers_to_keep = [
        "_entry.id",
        "_entry.title",
        "_entry.deposition_date",
        "_pdbx_audit_revision_history.revision_date",
    ]
    filtered_metadata = {
        key: mmcif_dict[key] for key in headers_to_keep if key in mmcif_dict
    }

    # Make metadata if missing
    if "_pdbx_audit_revision_history.revision_date" not in filtered_metadata:
        filtered_metadata["_pdbx_audit_revision_history.revision_date"] = time.strftime(
            "%Y-%m-%d"
        )

    for model in structure:
        chain_to_del = []
        for chain in model:
            if chain.id != chain_id:
                chain_to_del.append(chain.id)
                continue

        for unwanted_chain in chain_to_del:
            model.detach_child(unwanted_chain)

        for chain in model:
            res_to_del = []
            for i, res in enumerate(chain):
                rel_pos = i + 1
                if rel_pos < start or rel_pos > end or res.id[0] != " ":
                    res_to_del.append(res)

            for res in res_to_del:
                chain.detach_child(res.id)

    # Save the filtered structure to a new CIF file
    io = Bio.PDB.MMCIFIO()
    io.set_structure(structure)
    filtered_output = f"tmp/{pdb_id}_{chain_id}.cif"
    io.save(filtered_output)

    # Parse the filtered structure to get the modified MMCIF with no metadata
    structure = parser.get_structure(pdb_id, filtered_output)
    mmcif_dict = parser._mmcif_dict

    # Add the filtered metadata to the MMCIF dictionary
    mmcif_dict.update(filtered_metadata)

    # Save the modified MMCIF with wanted metadata to a string
    string_io = StringIO()
    io.set_dict(mmcif_dict)
    io.save(string_io)

    return string_io.getvalue()


def check_chains(mmcif_file):
    parser = Bio.PDB.MMCIFParser(QUIET=True)
    structure = parser.get_structure("template", mmcif_file)
    chains = []
    for model in structure:
        for chain in model:
            chains.append(chain.id)
    return chains


def extract_sequence_from_mmcif(mmcif_file):
    parser = Bio.PDB.MMCIFParser(QUIET=True)
    structure = parser.get_structure("template", mmcif_file)
    sequence = ""
    for model in structure:
        for chain in model:  # Assuming one chain only
            for residue in chain:
                if residue.id[0] == " ":  # Exclude heteroatoms
                    sequence += residue.resname[
                        0
                    ]  # Simplified to take the first letter
    return sequence


def align_and_map(query_seq, template_seq):
    # Perform pairwise alignment
    alignments = pairwise2.align.globalxx(query_seq, template_seq)
    alignment = alignments[0]  # Take the best alignment
    query_aligned, template_aligned, _, _, _ = alignment

    # Map indices
    query_indices = []
    template_indices = []

    query_pos, template_pos = -1, -1
    for q_char, t_char in zip(query_aligned, template_aligned):
        if q_char != "-":  # Not a gap in query
            query_pos += 1
            if t_char != "-":  # Not a gap in template
                query_indices.append(query_pos)
                template_indices.append(template_pos + 1)  # 1-based index for template
        elif t_char != "-":  # Increment template position for gaps in query
            template_pos += 1

    return query_indices, template_indices


if __name__ == "__main__":
    import argparse
    import shutil

    parser = argparse.ArgumentParser(
        description="Add MMseqs2 unpaired MSA to AlphaFold3 json"
    )
    parser.add_argument("--input_json", help="Input alphafold3 json file")
    parser.add_argument("--output_json", help="Output alphafold3 json file")
    parser.add_argument(
        "--templates", action="store_true", help="Include templates in the output json"
    )
    parser.add_argument(
        "--num_templates",
        type=int,
        default=20,
        help="Number of templates to include in the output json",
    )
    parser.add_argument("--target_id", help="Target id relating to the custom template")
    parser.add_argument(
        "--custom_template", help="Custom template to include in the output json"
    )
    parser.add_argument(
        "--custom_template_chain",
        help="Custom template chain to include in the output json",
    )

    args = parser.parse_args()

    af3_json = json.load(open(args.input_json))

    for sequence in af3_json["sequences"]:
        if "protein" in sequence:
            input_sequence = sequence["protein"]["sequence"]

            # Run MMseqs2 to get unpaired MSA
            if args.templates:
                a3m_lines, templates = run_mmseqs(
                    input_sequence,
                    "tmp",
                    use_templates=True,
                    num_templates=args.num_templates,
                )
            else:
                a3m_lines = run_mmseqs(input_sequence, "tmp", use_templates=False)
                templates = []

            if args.custom_template:
                if not os.path.exists(args.custom_template):
                    raise FileNotFoundError(
                        f"Custom template file {args.custom_template} not found"
                    )

                # Can only add templates to protein sequences, so check if there are multiple protein sequences in the input json
                if (
                    len([x for x in af3_json["sequences"] if "protein" in x.keys()]) > 1
                    and not args.target_id
                ):
                    raise ValueError(
                        "Multiple sequences found in input json. Please specify target sequence so that custom template can be added to the correct sequence"
                    )

                chain_info = check_chains(args.custom_template)
                if len(chain_info) != 1 and not args.custom_template_chain:
                    raise ValueError(
                        f"Custom template file {args.custom_template} contains {len(chain_info)} chains. Please specify the chain to use with --custom_template_chain"
                    )

                if (
                    args.custom_template_chain
                    and args.custom_template_chain not in chain_info
                ):
                    raise ValueError(
                        f"Custom template file {args.custom_template} does not contain chain {args.custom_template_chain}"
                    )

                seq_id = sequence["protein"]["id"]
                if isinstance(seq_id, list):
                    if args.target_id and args.target_id not in seq_id:
                        continue
                if isinstance(seq_id, str):
                    if args.target_id and args.target_id != seq_id:
                        continue

                if not args.custom_template_chain:
                    args.custom_template_chain = chain_info[0]

                template = {}
                cif_str = _get_mmcif(
                    args.custom_template,
                    "custom",
                    args.custom_template_chain,
                    1,
                    len(input_sequence),
                )

                template["mmcif"] = cif_str
                template_seq = extract_sequence_from_mmcif(StringIO(cif_str))
                query_indices, template_indices = align_and_map(
                    input_sequence, template_seq
                )

                template["queryIndices"] = query_indices
                template["templateIndices"] = template_indices

                # Add the custom template to the start of the templates list
                templates.insert(0, template)

            # Add unpaired MSA to the json
            sequence["protein"]["unpairedMsa"] = a3m_lines[0]
            sequence["protein"]["pairedMsa"] = ""
            sequence["protein"]["templates"] = templates

            # Remove temporary files
            shutil.rmtree("tmp")

    # Save the output json
    if args.output_json:
        with open(args.output_json, "w") as f:
            json.dump(af3_json, f)
    else:
        output_json = args.input_json.replace(".json", "_mmseqs.json")
        with open(output_json, "w") as f:
            json.dump(af3_json, f)

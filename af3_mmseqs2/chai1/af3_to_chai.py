import json
from pathlib import Path
from typing import Optional, Union

import pandas as pd
from chai_lab.data.parsing.msas.aligned_pqt import \
    merge_multi_a3m_to_aligned_dataframe


class ChaiFasta:
    """
    Object to convert an AlphaFold3 json to a fasta file compatible with CHAI-1
    """

    def __init__(self, working_dir: Union[str, Path]):
        self.working_dir = working_dir
        self.fasta = Path(working_dir) / 'chai1.fasta'
        self.constraints = Path(working_dir) / 'chai1_constraints.csv'
        self.msa_file = Optional[Union[str, Path]] = None

    def msa_to_file(self, msa: str, file_path:  Union[str, Path]):
        """
        Takes an msa string, converts it to pqt format and writes it to a file

        Args:
            msa (str): msa string (a3m format)
            file_path (Union[str, Path]): file path to write the msa to

        Returns:
            None
        """



        with open(file_path, 'w') as f:
            f.write(msa)


def read_af3_json(af3_json: Path):
    with open(af3_json, 'r') as f:
        af3 = json.load(f)
    return af3

def convert_bonded_pairs(bonded_pairs, fasta_data, output_file: Path):
    constraints_headers = ["chainA", "res_idxA", "chainB", "res_idxB", "connection_type", "confidence", "min_distance_angstrom", "max_distance_angstrom", "comment", "restraint_id"]
    df = pd.DataFrame(columns=constraints_headers)

    for i, bonded_pair in enumerate(bonded_pairs):
        pair_data = []
        for pair in bonded_pair:
            chain_id = pair[0]
            seq_idx = pair[1]
            res = fasta_data[chain_id][seq_idx - 1]
            pair_data.append(chain_id)
            pair_data.append(f"{res}{seq_idx}")
        row_data = [pair_data[0], pair_data[1], pair_data[2], pair_data[3], 'contact', 1, 0.0, 5.5, 'No comment', f'restraint_{i}']
        df.loc[i] = row_data
    df.to_csv(output_file, sep=',', index=False)

def write_chai_fasta(af3_dict, fasta: Path):

    fasta_data = {}

    # with open(fasta, 'w') as f:
    for seq in af3_dict['sequences']:
        if 'protein' in seq:
            if isinstance(seq['protein']['id'], list):
                for prot_id in seq['protein']['id']:
                    print(f">protein|{prot_id}")
                    print(seq['protein']['sequence'])
                    fasta_data[prot_id] = seq['protein']['sequence']
            else:
                prot_id = seq['protein']['id']
                print(f">protein|{prot_id}")
                print(seq['protein']['sequence'])
                fasta_data[prot_id] = seq['protein']['sequence']
        if 'nucleotide' in seq:

            if 'U' in seq['nucleotide']['sequence']:
                seq_type = "rna"
            else:
                seq_type = "dna"

            for nucl_id in seq['nucleotide']['id']:
                print(f">{seq_type}|{nucl_id}")
                print(seq['nucleotide']['sequence'])
                fasta_data[nucl_id] = seq['nucleotide']['sequence']
            else:
                nucl_id = seq['nucleotide']['id']
                print(f">{seq_type}|{nucl_id}")
                print(seq['nucleotide']['sequence'])
                fasta_data[nucl_id] = seq['nucleotide']['sequence']
        if 'ligand' in seq:
            if 'smiles' in seq['ligand']:
                if isinstance(seq['ligand']['id'], list):
                    for lig_id in seq['ligand']['id']:
                        print(f">ligand|{lig_id}")
                        print(seq['ligand']['smiles'])
                else:
                    lig_id = seq['ligand']['id']
                    print(f">ligand|{lig_id}")
                    print(seq['ligand']['smiles'])
            else:
                print(f"Ommiting {seq['ligand']['id']}")
                print("Ligand must be in SMILES format for Chai-1")

    bonded_pairs = af3_dict['bondedAtomPairs']
    # convert_bonded_pairs(bonded_pairs, fasta_data)


def af3_to_chai(af3_json: Path):
    af3_dict = read_af3_json(af3_json=af3_json)
    write_chai_fasta(af3_dict=af3_dict, fasta=af3_json.with_suffix('.fasta'))



if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description='Convert AF3 to CHAI')
    parser.add_argument('-af3_json', type=Path, help='AF3 file')

    args = parser.parse_args()

    af3_to_chai(af3_json=args.af3_json)

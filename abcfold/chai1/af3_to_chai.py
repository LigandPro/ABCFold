import hashlib
import json
import logging
import tempfile
from pathlib import Path
from typing import Dict, Optional, Union

import pandas as pd
import requests

try:
    from chai_lab.data.parsing.msas.aligned_pqt import \
        merge_multi_a3m_to_aligned_dataframe
    from chai_lab.data.parsing.msas.data_source import MSADataSource
except ImportError:
    pass

logger = logging.getLogger(__name__)


class ChaiFasta:
    """
    Object to convert an AlphaFold3 json to a fasta file compatible with CHAI-1
    """

    def __init__(self, working_dir: Union[str, Path]):
        self.working_dir = working_dir
        self.fasta = Path(working_dir) / 'chai1.fasta'
        self.constraints = Path(working_dir) / 'chai1_constraints.csv'
        self.msa_file: Optional[Union[str, Path]] = None

    def bonded_pairs_to_file(self, bonded_pairs, fasta_data: dict):
        """
        Converts bonded pairs to a csv file compatible with CHAI-1

        Args:
            bonded_pairs (list): list of bonded pairs in AF3 format
            fasta_data (dict): dictionary with sequence data relating to IDs

        Returns:
            None
        """

        constraints_headers = [
            "chainA", "res_idxA", "chainB", "res_idxB",
            "connection_type", "confidence",
            "min_distance_angstrom", "max_distance_angstrom",
            "comment", "restraint_id"
        ]
        df = pd.DataFrame(columns=constraints_headers)

        for i, bonded_pair in enumerate(bonded_pairs):
            pair_data = []
            for pair in bonded_pair:
                chain_id = pair[0]
                seq_idx = pair[1]
                res = fasta_data[chain_id][seq_idx - 1]
                pair_data.append(chain_id)
                pair_data.append(f"{res}{seq_idx}")
            row_data = [
                pair_data[0],
                pair_data[1],
                pair_data[2],
                pair_data[3],
                'contact',
                1.0,
                0.0,
                5.5,
                'No comment',
                f'restraint_{i}']
            df.loc[i] = row_data
        df.to_csv(self.constraints, sep=',', index=False)

    def msa_to_file(self, msa: str, file_path: Union[str, Path]):
        """
        Takes an msa string, converts it to pqt format and writes it to a file

        Args:
            msa (str): msa string (a3m format)
            file_path (Union[str, Path]): file path to write the msa to

        Returns:
            None
        """

        # Convert msa to CHAI-1 format with additional MSA source information
        with tempfile.NamedTemporaryFile(suffix='.a3m', mode='w') as f:
            f.write(msa)
            f.flush()
            df = merge_multi_a3m_to_aligned_dataframe(
                msa_a3m_files={Path(f.name): MSADataSource.UNIPROT},
                insert_keys_for_sources='uniprot'
            )

        # Write the dataframe to a parquet file
        df.to_parquet(file_path)

    def json_to_fasta(self, json_file_or_dict: Union[dict, str, Path]):
        """
        Main function to convert an AlphaFold3 json to a fasta file
        compatible with CHAI-1

        Args:
            json_file_or_dict (Union[dict, str, Path]):
            json file or dictionary

        Returns:
            None
        """

        if isinstance(json_file_or_dict, str) or isinstance(json_file_or_dict, Path):
            with open(json_file_or_dict, "r") as f:
                json_dict = json.load(f)
        else:
            json_dict = json_file_or_dict

        fasta_data: Dict[str, str] = {}
        with open(self.fasta, 'w') as f:
            for seq in json_dict['sequences']:
                if 'protein' in seq:
                    protein_str, fasta_data = self.add_protein(
                        seq,
                        fasta_data
                        )
                    f.write(protein_str)
                if 'rna' in seq:
                    nucleotide_str, fasta_data = self.add_nucleotide(
                        seq,
                        'rna',
                        fasta_data
                        )
                    f.write(nucleotide_str)
                if 'dna' in seq:
                    nucleotide_str, fasta_data = self.add_nucleotide(
                        seq,
                        'dna',
                        fasta_data
                        )
                    f.write(nucleotide_str)
                if 'ligand' in seq:
                    ligand_str = self.add_ligand(seq)
                    f.write(ligand_str)

        # Check if there are bonded pairs
        if 'bondedAtomPairs' in json_dict.keys():
            bonded_pairs = json_dict['bondedAtomPairs']
            self.bonded_pairs_to_file(bonded_pairs, fasta_data)

    def add_protein(self, seq: dict, fasta_data: dict):
        prot_id = seq['protein']['id']
        if isinstance(prot_id, list):
            protein_str = ""
            for i in seq['protein']['id']:
                temp_prot_str, fasta_data = self._add_protein(
                    seq,
                    i,
                    fasta_data)
                protein_str += temp_prot_str
        else:
            protein_str, fasta_data = self._add_protein(seq,
                                                        prot_id,
                                                        fasta_data)
        return protein_str, fasta_data

    def _add_protein(self, seq: dict, prot_id: str, fasta_data: dict):
        protein_str = f">protein|{prot_id}\n{seq['protein']['sequence']}\n"
        sequence = seq['protein']['sequence']
        if 'unpairedMsa' in seq['protein'].keys():
            seq_hash = hashlib.sha256(sequence.upper().encode()).hexdigest()
            pqt_path = Path(self.working_dir) / f'{seq_hash}.aligned.pqt'
            msa = seq['protein']['unpairedMsa']
            self.msa_to_file(msa=msa, file_path=pqt_path)
        fasta_data[prot_id] = sequence

        return protein_str, fasta_data

    def add_nucleotide(self, seq: dict, seq_type: str, fasta_data: dict):
        nucl_id = seq[seq_type]['id']

        if isinstance(nucl_id, list):
            nucleotide_str = ""
            for i in seq[seq_type]['id']:
                temp_nucl_str, fasta_data = self._add_nucleotide(seq,
                                                                 seq_type,
                                                                 i,
                                                                 fasta_data)
                nucleotide_str += temp_nucl_str
        else:
            nucleotide_str, fasta_data = self._add_nucleotide(seq,
                                                              seq_type,
                                                              nucl_id,
                                                              fasta_data)

        return nucleotide_str, fasta_data

    def _add_nucleotide(self, seq: dict, seq_type: str, nucl_id: str, fasta_data: dict):
        nucleotide_str = f">{seq_type}|{nucl_id}\n{seq[seq_type]['sequence']}\n"
        fasta_data[nucl_id] = seq[seq_type]['sequence']
        return nucleotide_str, fasta_data

    def ccd_to_smiles(self, ccd_id: str):
        url = f"http://cactus.nci.nih.gov/chemical/structure/{ccd_id}/smiles"
        response = requests.get(url)
        if response.status_code == 200:
            ccd_data = response.text
            return ccd_data
        else:
            logger.warning(f"Could not retrieve SMILES for {ccd_id}")
            return None

    def add_ligand(self, seq: dict):
        lig_id = seq['ligand']['id']
        ligand_str = ""
        if 'ccdCode' in seq['ligand']:
            if isinstance(lig_id, list):
                for i in seq['ligand']['id']:
                    smile = self.ccd_to_smiles(seq['ligand']['ccdCode'][0])
                    if smile:
                        ligand_str += f">ligand|{i}\n{smile}\n"
            else:
                smile = self.ccd_to_smiles(seq['ligand']['ccdCode'])
                if smile:
                    ligand_str = f">ligand|{lig_id}\n{smile}\n"
        if 'smiles' in seq['ligand']:
            if isinstance(lig_id, list):
                for i in seq['ligand']['id']:
                    ligand_str += f">ligand|{i}\n{seq['ligand']['smiles']}\n"
            else:
                ligand_str = f">ligand|{lig_id}\n{seq['ligand']['smiles']}\n"

        return ligand_str

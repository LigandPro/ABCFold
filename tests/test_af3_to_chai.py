import tempfile
from pathlib import Path

import pandas as pd
import pytest

from abcfold.chai1.af3_to_chai import ChaiFasta


def test_af3_to_chai(test_data):
    with tempfile.TemporaryDirectory() as temp_dir:
        chai_fasta = ChaiFasta(temp_dir)

        chai_fasta.json_to_fasta(test_data.test_inputAB_json)

        reference = """>protein|A
GMRES
>protein|B
GMRES
>protein|C
YANEN
>ligand|F
CC(=O)OC1C[NH+]2CCC1CC2
"""

        filename = Path(temp_dir) / "chai1.fasta"

        assert filename.exists()
        with open(filename, "r") as f:
            data = f.read()
        print(data)
        assert data == reference


def test_af3_to_chai_rna(test_data):
    with tempfile.TemporaryDirectory() as temp_dir:
        chai_fasta = ChaiFasta(temp_dir)

        chai_fasta.json_to_fasta(test_data.test_inputRNA_json)

        reference = """>rna|A\nAGCU\n"""

        filename = Path(temp_dir) / "chai1.fasta"

        assert filename.exists()
        with open(filename, "r") as f:
            data = f.read()

        assert data == reference


def test_af3_to_chai_dna(test_data):
    with tempfile.TemporaryDirectory() as temp_dir:
        chai_fasta = ChaiFasta(temp_dir)

        chai_fasta.json_to_fasta(test_data.test_inputDNA_json)

        reference = """>dna|A\nAGCT\n>dna|B\nAGCT\n"""

        filename = Path(temp_dir) / "chai1.fasta"

        assert filename.exists()
        with open(filename, "r") as f:
            data = f.read()

        assert data == reference


def test_af3_to_chai_ligand(test_data):
    with tempfile.TemporaryDirectory() as temp_dir:
        chai_fasta = ChaiFasta(temp_dir)

        chai_fasta.json_to_fasta(test_data.test_inputLIG_json)

        reference = """>protein|A
GMRESYANENQFGFKTINSDIHKIVIVGGYGKLGGLFARYLRASGYPISILDREDWAVAESILANADVV\
IVSVPINLTLETIERLKPYLTENMLLADLTSVKREPLAKMLEVHTGAVLGLHPMFGADIASMAKQVVVR\
CDGRFPERYEWLLEQIQIWGAKIYQTNATEHDHNMTYIQALRHFSTFANGLHLSKQPINLANLLALSSP\
IYRLELAMIGRLFAQDAELYADIIMDKSENLAVIETLKQTYDEALTFFENNDRQGFIDAFHKVRDWFGD\
YSEQFLKESRQLLQQANDLKQG
>protein|B
GMRESYANENQFGFKTINSDIHKIVIVGGYGKLGGLFARYLRASGYPISILDREDWAVAESILANADVV\
IVSVPINLTLETIERLKPYLTENMLLADLTSVKREPLAKMLEVHTGAVLGLHPMFGADIASMAKQVVVR\
CDGRFPERYEWLLEQIQIWGAKIYQTNATEHDHNMTYIQALRHFSTFANGLHLSKQPINLANLLALSSP\
IYRLELAMIGRLFAQDAELYADIIMDKSENLAVIETLKQTYDEALTFFENNDRQGFIDAFHKVRDWFGD\
YSEQFLKESRQLLQQANDLKQG
>ligand|C
Nc1ncnc2n(cnc12)C3OC(CO[P](O)(=O)O[P](O)(=O)O[P](O)(O)=O)C(O)C3O
>ligand|D
Nc1ncnc2n(cnc12)C3OC(CO[P](O)(=O)O[P](O)(=O)O[P](O)(O)=O)C(O)C3O
>ligand|E
CC(=O)OC1C[NH+]2CCC1CC2
>ligand|F
[Na+]
>ligand|G
CCCCCCCCCCCC(O)=O
>ligand|H
CCCCCCCCCCCC(O)=O
"""

        filename = Path(temp_dir) / "chai1.fasta"

        assert filename.exists()
        with open(filename, "r") as f:
            data = f.read()

        assert data == reference


def test_chai_output_constraints(test_data):
    with tempfile.TemporaryDirectory() as temp_dir:
        chai_fasta = ChaiFasta(temp_dir)

        chai_fasta.json_to_fasta(test_data.test_inputBOND_json)

        filename = Path(temp_dir) / "chai1_constraints.csv"

        assert filename.exists()

        df = pd.read_csv(filename)

        assert list(df.columns) == [
            "chainA",
            "res_idxA",
            "chainB",
            "res_idxB",
            "connection_type",
            "confidence",
            "min_distance_angstrom",
            "max_distance_angstrom",
            "comment",
            "restraint_id",
        ]

        assert len(df) == 2

        assert df.iloc[0]["chainA"] == "A"
        assert df.iloc[0]["res_idxA"] == "C387"
        assert df.iloc[0]["chainB"] == "B"
        assert df.iloc[0]["res_idxB"] == "Y101"
        assert df.iloc[0]["connection_type"] == "contact"
        assert df.iloc[0]["confidence"] == 1.0
        assert df.iloc[0]["min_distance_angstrom"] == 0.0
        assert df.iloc[0]["max_distance_angstrom"] == 5.5
        assert df.iloc[0]["comment"] == "No comment"
        assert df.iloc[0]["restraint_id"] == "restraint_0"


def test_chai_output_msa(test_data):
    pytest.importorskip("chai_lab")
    with tempfile.TemporaryDirectory() as temp_dir:
        chai_fasta = ChaiFasta(temp_dir)

        chai_fasta.json_to_fasta(test_data.test_inputAmsa_json)

        filename = (
            Path(temp_dir)
            / "1573f21c6a9eb5fb0727d8661eef242d8c09a481f\
c008b01ba22596b3bf31151.aligned.pqt"
        )

        assert filename.exists()

        df = pd.read_parquet(filename)

        ref_columns = ["sequence", "source_database", "pairing_key", "comment"]
        assert list(df.columns) == ref_columns

        assert len(df) == 4256

        assert (
            df.iloc[0]["sequence"]
            == "GMRESYANENQFGFKTINSDIHKIVIVGGYGKLGGL\
FARYLRASGYPISILDREDWAVAESILANADVVIVSVPINLTLETIERLKPYLTENMLLADLTSVKREPLAKMLEVHT\
GAVLGLHPMFGADIASMAKQVVVRCDGRFPERYEWLLEQIQIWGAKIYQTNATEHDHNMTYIQALRHFSTFANGLHLS\
KQPINLANLLALSSPIYRLELAMIGRLFAQDAELYADIIMDKSENLAVIETLKQTYDEALTFFENNDRQGFIDAFHKV\
RDWFGDYSEQFLKESRQLLQQANDLKQG"
        )
        assert df.iloc[0]["source_database"] == "query"
        assert df.iloc[0]["pairing_key"] == ""
        assert df.iloc[0]["comment"] == "101"


def test_ccd_to_smiles():
    chai_fasta = ChaiFasta(".")

    smiles = chai_fasta.ccd_to_smiles("DAO")
    assert smiles == "CCCCCCCCCCCC(O)=O"

    smiles = chai_fasta.ccd_to_smiles("NOT_A_CCD")
    assert smiles is None

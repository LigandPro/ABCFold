import json
import tempfile
from pathlib import Path

from src.boltz1.af3_to_boltz1 import DELIM, BoltzYaml


def test_af3_to_boltz(test_data):
    with tempfile.TemporaryDirectory() as temp_dir:
        boltz_yaml = BoltzYaml(temp_dir)

        yaml_string_multi = boltz_yaml.json_to_yaml(test_data.test_inputAB_json)

        yaml_string_multi = yaml_string_multi.split("\n")

        assert yaml_string_multi[0] == "version: 1"
        assert yaml_string_multi[1] == "sequences:"
        assert yaml_string_multi[2] == f"{DELIM}- protein:"
        assert yaml_string_multi[3] == f"{DELIM}{DELIM}id: [A, B]"
        assert yaml_string_multi[4] == f"{DELIM}{DELIM}sequence: GMRES"
        assert yaml_string_multi[5] == f"{DELIM}- protein:"
        assert yaml_string_multi[6] == f"{DELIM}{DELIM}id: C"
        assert yaml_string_multi[7] == f"{DELIM}{DELIM}sequence: YANEN"
        assert yaml_string_multi[8] == f"{DELIM}- ligand:"
        assert yaml_string_multi[9] == f"{DELIM}{DELIM}id: [D, E]"
        assert yaml_string_multi[10] == f"{DELIM}{DELIM}ccd: ['ATP']"
        assert yaml_string_multi[11] == f"{DELIM}- ligand:"
        assert yaml_string_multi[12] == f"{DELIM}{DELIM}id: F"
        assert yaml_string_multi[13] == f"{DELIM}{DELIM}smiles: CC(=O)OC1C[NH+]2CCC1CC2"

        yaml_string_bonds = boltz_yaml.json_to_yaml(test_data.test_inputA_json)
        yaml_string_bonds = yaml_string_bonds.split("\n")

        assert yaml_string_bonds[0] == "version: 1"
        assert yaml_string_bonds[1] == "sequences:"
        assert yaml_string_bonds[2] == f"{DELIM}- protein:"
        assert yaml_string_bonds[3] == f"{DELIM}{DELIM}id: A"
        assert (
            yaml_string_bonds[4]
            == f"{DELIM}{DELIM}sequence: GMRESYANENQFGFKTINSDIHKIVIVGGYGKLGGLFARY\
LRASGYPISILDREDWAVAESILANADVVIVSVPINLTLETIERLKPYLTENMLLADLTSVKREPLAKMLEVHTGAVLGLHPMFG\
ADIASMAKQVVVRCDGRFPERYEWLLEQIQIWGAKIYQTNATEHDHNMTYIQALRHFSTFANGLHLSKQPINLANLLALSSPIYRL\
ELAMIGRLFAQDAELYADIIMDKSENLAVIETLKQTYDEALTFFENNDRQGFIDAFHKVRDWFGDYSEQFLKESRQLLQQANDLKQG"
        )
        assert yaml_string_bonds[5] == "constraints:"
        assert yaml_string_bonds[6] == f"{DELIM}- bond:"
        assert yaml_string_bonds[7] == f"{DELIM}{DELIM}atom1: ['A', 1, 'CA']"
        assert yaml_string_bonds[8] == f"{DELIM}{DELIM}atom2: ['A', 20, 'CA']"

        with open(test_data.test_inputAB_json, "r") as f:
            json_dict = json.load(f)

        yaml_string = boltz_yaml.json_to_yaml(json_dict)
        yaml_string = yaml_string.split("\n")

        assert yaml_string[0] == "version: 1"
        assert yaml_string[1] == "sequences:"
        assert yaml_string_multi[2] == f"{DELIM}- protein:"
        assert yaml_string_multi[3] == f"{DELIM}{DELIM}id: [A, B]"
        assert yaml_string_multi[4] == f"{DELIM}{DELIM}sequence: GMRES"
        assert yaml_string_multi[5] == f"{DELIM}- protein:"
        assert yaml_string_multi[6] == f"{DELIM}{DELIM}id: C"
        assert yaml_string_multi[7] == f"{DELIM}{DELIM}sequence: YANEN"
        assert yaml_string_multi[8] == f"{DELIM}- ligand:"
        assert yaml_string_multi[9] == f"{DELIM}{DELIM}id: [D, E]"
        assert yaml_string_multi[10] == f"{DELIM}{DELIM}ccd: ['ATP']"
        assert yaml_string_multi[11] == f"{DELIM}- ligand:"
        assert yaml_string_multi[12] == f"{DELIM}{DELIM}id: F"
        assert yaml_string_multi[13] == f"{DELIM}{DELIM}smiles: CC(=O)OC1C[NH+]2CCC1CC2"


def test_boltz_output_yaml(test_data):
    with tempfile.TemporaryDirectory() as temp_dir:
        boltz_yaml = BoltzYaml(temp_dir)

        assert not boltz_yaml.yaml_string
        boltz_yaml.json_to_yaml(test_data.test_inputAB_json)

        assert boltz_yaml.yaml_string

        file_name = Path(temp_dir) / "output.yaml"
        boltz_yaml.write_yaml(file_name)

        assert file_name.exists()
        assert file_name.is_file()


def test_boltz_output_msa(test_data):
    with tempfile.TemporaryDirectory() as temp_dir:
        boltz_yaml = BoltzYaml(temp_dir)

        assert boltz_yaml.msa_file is None

        boltz_yaml.json_to_yaml(test_data.test_inputAmsa_json)

        assert boltz_yaml.msa_file is not None
        assert boltz_yaml.msa_file.exists()
        assert boltz_yaml.msa_file.is_file()

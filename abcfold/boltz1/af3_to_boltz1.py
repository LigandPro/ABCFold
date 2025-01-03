import json
import logging
import random
import string
from pathlib import Path
from typing import Optional, Union

DELIM = "      "

logger = logging.getLogger("logger")


class BoltzYaml:
    """
    Object to convert an AlphaFold3 json file to a boltzmann yaml file.
    """

    def __init__(self, working_dir: Union[str, Path]):
        self.working_dir = working_dir
        self.yaml_string: str = ""
        self.msa_file: Optional[Union[str, Path]] = None

    def msa_to_file(self, msa: str, file_path: Union[str, Path]):
        """
        Takes a msa string and writes it to a file

        Args:
            msa (str): msa string
            file_path (Union[str, Path]): file path to write the msa to

        Returns:
            None
        """
        with open(file_path, "w") as f:
            f.write(msa)

    def json_to_yaml(self, json_file_or_dict: Union[dict, str, Path]):
        """
        Main function to convert a json file or dict to a yaml string

        Args:
            json_file_or_dict (Union[dict, str, Path]): json file or dict

        Returns:
            str: a string representation of string
        """
        if isinstance(json_file_or_dict, str) or isinstance(json_file_or_dict, Path):
            with open(json_file_or_dict, "r") as f:
                json_dict = json.load(f)
        else:
            json_dict = json_file_or_dict

        self.yaml_string = ""

        self.yaml_string += self.add_version_number("1")
        for key, value in json_dict.items():
            if key == "sequences":
                if "sequences" not in self.yaml_string:
                    self.yaml_string += self.add_non_indented_string("sequences")
                for sequence_dict in value:
                    if any([key in sequence_dict for key in ["protein", "rna", "dna"]]):
                        self.yaml_string += self.sequence_to_yaml(sequence_dict)
                    if any([key in sequence_dict for key in ["ligand"]]):
                        self.yaml_string += self.add_ligand_information(
                            sequence_dict["ligand"]
                        )
            if key == "bondedAtomPairs":
                if "constraints" not in self.yaml_string:
                    self.yaml_string += self.add_non_indented_string("constraints")
                self.yaml_string += self.bonded_atom_pairs_to_yaml(value)

        return self.yaml_string

    def bonded_atom_pairs_to_yaml(self, bonded_atom_pairs: list):
        yaml_string = ""
        for pair in bonded_atom_pairs:
            yaml_string += self.add_title("bond")
            yaml_string += self.add_key_and_value("atom1", pair[0])
            yaml_string += self.add_key_and_value("atom2", pair[1])

        return yaml_string

    def add_version_number(self, version: str):
        """
        Adds the version number to the yaml string

        Args:
            version (str): version number

        Returns:
            str: yaml string
        """
        return f"version: {version}\n"

    def add_non_indented_string(self, string: str):
        """
        Adds the sequence string to the yaml string

        Returns:
            str: yaml string
        """
        return f"{string}:\n"

    def add_id(self, id_: Union[str, list, int]):
        """
        Adds the id to the yaml string

        Args:
            id_ (Union[str, list, int]): id

        Returns:
            str: yaml string

        """
        if isinstance(id_, list):
            new_id = ", ".join([str(i).replace('"', "").replace("'", "") for i in id_])
        else:
            new_id = str(id_).replace('"', "").replace("'", "")

        return (
            f"{DELIM}{DELIM}id: {new_id}\n"
            if not isinstance(id_, list)
            else f"{DELIM}{DELIM}id: [{new_id}]\n"
        )

    def add_sequence(self, sequence: str):
        """
        Adds the sequence to the yaml string

        Args:
            sequence (str): sequence

        Returns:
            str: yaml string

        """
        return f"{DELIM}{DELIM}sequence: {sequence}\n"

    def add_msa(self, msa: Union[str, Path]):
        """
        Adds the msa file_path to the yaml string, double tabbed

        Args:
            msa (str): msa file_path

        Returns:
            str: yaml string
        """
        if not Path(msa).exists():
            msg = f"File {msa} does not exist"
            logger.critical(msg)
            raise FileNotFoundError()
        return f"{DELIM}{DELIM}msa: {msa}\n"

    def add_key_and_value(self, key: str, value: str):
        """
        Adds the key and value to the yaml string, double tabbed

        Args:
            key (str): The key on the left of ':'
            value (str): The value on the right of ':'
        Returns:
            str: yaml string
        """
        return f"{DELIM}{DELIM}{key}: {value}\n"

    def add_ligand_information(self, ligand_dict: dict):
        """
        Function to add ligand information to the yaml string

        Args:
            ligand_dict (dict): ligand dict

        Returns:
            str: yaml string
        """
        yaml_string = ""
        yaml_string += self.add_title("ligand")
        yaml_string += self.add_id(ligand_dict["id"])

        if "smiles" in ligand_dict:
            yaml_string += self.add_key_and_value("smiles", ligand_dict["smiles"])
        elif "ccdCodes" in ligand_dict:
            yaml_string += self.add_key_and_value("ccd", ligand_dict["ccdCodes"])
        else:

            msg = "Ligand must have either a smiles or ccdCCodes"
            logger.critical(msg)
            raise ValueError()

        return yaml_string

    def add_sequence_information(self, sequence_dict: dict):
        """
        Adds the sequence information of protein, rna, dna to the yaml string

        Args:
            sequence_dict (dict): sequence dict
            msa_file (Union[str, Path]): msa file_path

        Returns:
            str: yaml string
        """
        yaml_string = ""
        yaml_string += self.add_id(sequence_dict["id"])
        yaml_string += (
            self.add_sequence(sequence_dict["sequence"])
            if "sequence" in sequence_dict
            else ""
        )
        if self.msa_file is None:
            return yaml_string
        self.msa_to_file(sequence_dict["unpairedMsa"], self.msa_file)
        yaml_string += self.add_msa(self.msa_file)
        return yaml_string

    def add_title(self, name: str):
        """
        Adds the title to the yaml string

        args:
            name (str): name of the title

        Returns:
            str: yaml string
        """
        return f"{DELIM}- {name}:\n"

    def sequence_to_yaml(self, sequence_dict: dict, yaml_string: str = ""):
        """
        Adds the sequence information to the yaml string

        Args:
            sequence_dict (dict): sequence dict
            yaml_string (str): yaml string

        Returns:
            str: yaml string
        """
        for sequence_type, sequence_info_dict in sequence_dict.items():
            yaml_string += self.add_title(sequence_type)
            self.msa_file = (
                (
                    Path(self.working_dir)
                    / f"{''.join(random.choices(string.ascii_letters, k=5))}.a3m"
                )
                if "unpairedMsa" in sequence_info_dict
                else None
            )

            yaml_string += self.add_sequence_information(sequence_info_dict)

        return yaml_string

    def write_yaml(self, file_path: Union[str, Path]):
        """
        Writes the yaml string to a file

        Args:
            file_path (Union[str, Path]): file path

        Returns:
            None
        """

        assert self.yaml_string, "No yaml string to write to file"
        assert Path(file_path).suffix == ".yaml", "File must have a .yaml extension"
        with open(file_path, "w") as f:
            f.write(self.yaml_string)

import json
import random
import string
from pathlib import Path
from typing import Union


class BoltzYaml:
    """
    Object to convert an AlphaFold3 json file to a boltzmann yaml file.
    """

    def __init__(self, temp_dir: Union[str, Path]):
        self.temp_dir = temp_dir

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

        yaml_string = ""

        yaml_string += self.add_version_number("1")
        for key, value in json_dict.items():
            if key == "sequences":
                if "sequences" not in yaml_string:
                    yaml_string += self.add_sequence_string()
                for sequence_dict in value:
                    if any([key in sequence_dict for key in ["protein", "rna", "dna"]]):
                        yaml_string += self.sequence_to_yaml(sequence_dict)
                    if any([key in sequence_dict for key in ["ligand"]]):
                        yaml_string += self.add_ligand_information(
                            sequence_dict["ligand"]
                        )

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

    def add_sequence_string(self):
        """
        Adds the sequence string to the yaml string

        Returns:
            str: yaml string
        """
        return "sequences:\n"

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
            f"\t\tid: {new_id}\n"
            if not isinstance(id_, list)
            else f"\t\tid: [{new_id}]\n"
        )

    def add_sequence(self, sequence: str):
        """
        Adds the sequence to the yaml string

        Args:
            sequence (str): sequence

        Returns:
            str: yaml string

        """
        return f"\t\tsequence: {sequence}\n"

    def add_msa(self, msa: str):
        """
        Adds the msa file_path to the yaml string

        Args:
            msa (str): msa file_path

        Returns:
            str: yaml string
        """
        if not Path(msa).exists():
            raise FileNotFoundError(f"File {msa} does not exist")
        return f"\t\tmsa: {msa}\n"

    def add_ligand(self, source: str, code: str):
        """
        Adds the ligand information to the yaml string

        Args:
            source (str): source of the ligand
            code (str): code of the ligand

        Returns:
            str: yaml string
        """
        return f"\t\t{source}: {code}\n"

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
            yaml_string += self.add_ligand("smiles", ligand_dict["smiles"])
        elif "ccdCode" in ligand_dict:
            yaml_string += self.add_ligand("ccd", ligand_dict["ccdCode"])
        else:
            msg = "Ligand must have either a smiles or ccdCode"
            raise ValueError(msg)

        return yaml_string

    def add_sequence_information(self, sequence_dict: dict, msa_file=None):
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
        if msa_file is None:
            return yaml_string
        self.msa_to_file(sequence_dict["msa"], msa_file)
        yaml_string += self.add_msa(msa_file)
        return yaml_string

    def add_title(self, name: str):
        """
        Adds the title to the yaml string

        args:
            name (str): name of the title

        Returns:
            str: yaml string
        """
        return f"\t{name}:\n"

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
            msa_file = (
                (
                    Path(self.temp_dir)
                    / f"{''.join(random.choices(string.ascii_letters, k=5))}.a3m"
                )
                if "msa" not in sequence_info_dict
                else None
            )

            yaml_string += self.add_sequence_information(
                sequence_info_dict, msa_file=msa_file
            )

        return yaml_string


if __name__ == "__main__":
    pass

import json
import logging
import re
from abc import ABC
from enum import Enum
from pathlib import Path
from typing import Union

import gemmi
import numpy as np

logger = logging.getLogger("logger")


class FileTypes(Enum):
    NPZ = "npz"
    CIF = "cif"
    JSON = "json"


class ModelCount:
    ALL = "all"
    RESIDUES = "residues"


class FileBase(ABC):

    def __init__(self, pathway: Union[str, Path]):
        self.pathway = Path(pathway)
        self.suffix = self.pathway.suffix[1:]

    def __str__(self):
        return str(self.pathway)

    def __repr__(self):
        return f"{self.__class__.__name__}({self.pathway})"


class BoltzOutput:
    def __init__(self, boltz_output_dir: Union[str, Path]):
        self.boltz_dir = Path(boltz_output_dir)
        self.name = re.sub(r"boltz_results_", "", self.boltz_dir.name, count=1)

        self.boltz_output = self.process_boltz_output()

        self.pae_files = [value["pae"] for value in self.boltz_output.values()]
        self.plddt_files = [value["plddt"] for value in self.boltz_output.values()]
        self.pde_files = [value["pde"] for value in self.boltz_output.values()]
        self.cif_files = [value["cif"] for value in self.boltz_output.values()]
        self.json_files = [value["json"] for value in self.boltz_output.values()]

    def process_boltz_output(self):
        # find all the directories in the boltz output directory
        # process all the files
        file_groups = {}
        for pathway in self.boltz_dir.rglob("*"):
            number = pathway.stem.split(f"{self.name}_model_")[-1]
            if not number.isdigit():
                continue
            number = int(number)

            file_type = pathway.suffix[1:]
            if file_type == FileTypes.NPZ.value:
                file_ = NpzFile(str(pathway))
            elif file_type == FileTypes.CIF.value:
                file_ = CifFile(str(pathway))
            elif file_type == FileTypes.JSON.value:
                file_ = ConfidenceJsonFile(str(pathway))
            else:
                continue
            if number not in file_groups:
                file_groups[number] = [file_]
            else:
                file_groups[number].append(file_)

        model_number_file_type_file = {}
        for model_number, files in file_groups.items():
            intermediate_dict = {}
            for file_ in sorted(files, key=lambda x: x.suffix):
                if file_.pathway.stem.startswith("pae"):
                    intermediate_dict["pae"] = file_
                elif file_.pathway.stem.startswith("plddt"):
                    intermediate_dict["plddt"] = file_
                elif file_.pathway.stem.startswith("pde"):
                    intermediate_dict["pde"] = file_
                else:
                    intermediate_dict[file_.suffix] = file_

            model_number_file_type_file[model_number] = intermediate_dict

        model_number_file_type_file = {
            key: model_number_file_type_file[key]
            for key in sorted(model_number_file_type_file)
        }
        return model_number_file_type_file

    def add_plddt_to_cif(self):
        for cif_file, plddt_scores in zip(self.cif_files, self.plddt_files):
            plddt_scores = plddt_scores.data["plddt"]
            if max(plddt_scores) <= 1:
                plddt_scores = (plddt_scores * 100).astype(float)

            chain_lengths = cif_file.chain_lengths(mode=ModelCount.RESIDUES)
            assert sum(chain_lengths.values()) == len(plddt_scores), "Length mismatch"
            counter = 0
            for chain in cif_file.model[0]:
                for residue in chain:
                    for atom in residue:
                        atom.b_iso = plddt_scores[counter]
                    counter += 1


class NpzFile(FileBase):
    def __init__(self, npz_file: Union[str, Path]):
        super().__init__(npz_file)
        self.npz_file = Path(npz_file)
        self.data = self.load_npz_file()

    def load_npz_file(self):
        return dict(np.load(self.npz_file))


class CifFile(FileBase):
    def __init__(self, cif_file: Union[str, Path]):
        super().__init__(cif_file)
        self.cif_file = Path(cif_file)
        self.model = self.load_cif_file()

    def load_cif_file(self):
        # load the cif file
        return gemmi.read_structure(str(self.cif_file))

    def chain_lengths(self, mode=ModelCount.RESIDUES):
        chains = self.model[0]
        if mode == ModelCount.ALL:
            return {chain.name: len([atom for atom in chain]) for chain in chains}

        elif mode == ModelCount.RESIDUES:

            return {chain.name: len(chain) for chain in chains}
        else:
            msg = "Invalid mode. Please use ModelCount.ALL or ModelCount.RESIDUES"
            logger.critical(msg)
            raise ValueError()

    def to_file(self, output_file: Union[str, Path]):
        # Taken from ccpem_utils/mode/gemmi_model_utils
        st_new = self.model.clone()
        st_new.name = st_new.name[:78]
        if "_entry.id" in st_new.info:
            st_new.info["_entry.id"] = st_new.info["_entry.id"][:78]

        st_new.make_mmcif_document().write_file(str(output_file))


class ConfidenceJsonFile(FileBase):
    def __init__(self, json_file: Union[str, Path]):
        super().__init__(json_file)
        self.data = self.load_json_file()

    def load_json_file(self):
        # load the json file
        with open(self.pathway, "r") as f:
            data = json.load(f)

        return data

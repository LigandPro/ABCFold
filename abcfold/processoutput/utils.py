import json
import logging
from abc import ABC
from enum import Enum
from pathlib import Path
from typing import Optional, Union

import numpy as np
from Bio.PDB import MMCIFIO, MMCIFParser

logger = logging.getLogger("logger")


class FileTypes(Enum):
    NPZ = "npz"
    NPY = "npy"
    CIF = "cif"
    JSON = "json"

    @classmethod
    def values(cls):
        return [value.value for value in cls.__members__.values()]


class ModelCount(Enum):
    ALL = "all"
    RESIDUES = "residues"

    @classmethod
    def values(cls):
        return [value.value for value in cls.__members__.values()]


class ResidueCountType(Enum):
    AVERAGE = "average"
    CARBONALPHA = "carbonalpha"

    @classmethod
    def values(cls):
        return [value.value for value in cls.__members__.values()]


class FileBase(ABC):

    def __init__(self, pathway: Union[str, Path]):
        self.pathway = Path(pathway)
        self.suffix = self.pathway.suffix[1:]

    def __str__(self):
        return str(self.pathway)

    def __repr__(self):
        return f"{self.__class__.__name__}({self.pathway})"


class NpzFile(FileBase):
    def __init__(self, npz_file: Union[str, Path]):
        super().__init__(npz_file)
        self.npz_file = Path(npz_file)
        self.data = self.load_npz_file()

    def load_npz_file(self) -> dict:
        return dict(np.load(self.npz_file))


class NpyFile(FileBase):
    def __init__(self, npy_file: Union[str, Path]):
        super().__init__(npy_file)
        self.npy_file = Path(npy_file)
        self.data = self.load_npy_file()

    def load_npy_file(self) -> np.ndarray:
        return np.load(self.npy_file)


class CifFile(FileBase):
    def __init__(self, cif_file: Union[str, Path], input_params: Optional[dict] = None):
        if input_params is None:
            self.input_params = {}
        else:
            self.input_params = input_params

        super().__init__(cif_file)
        self.cif_file = Path(cif_file)
        self.model = self.load_cif_file()
        self.atom_plddt_per_chain = self.get_plddt_per_atom()
        self.residue_plddt_per_chain = self.get_plddt_per_residue()
        self.__plddts = [
            plddts for plddts in self.atom_plddt_per_chain.values() for plddts in plddts
        ]
        self.__residue_plddts = [
            plddts
            for plddts in self.residue_plddt_per_chain.values()
            for plddts in plddts
        ]
        self.__name = self.cif_file.stem

    @property
    def name(self):
        return self.__name

    # name setter
    @name.setter
    def name(self, name: str):
        if not isinstance(name, str):
            logger.error("Name must be a string")
            raise ValueError()
        self.__name = name

    @property
    def plddts(self):
        """
        The pLDDT scores for each atom in the model
        """
        return self.__plddts

    @property
    def residue_plddts(self):
        """
        The pLDDT scores for each residue in the model
        """
        return self.__residue_plddts

    def load_cif_file(self):
        # load the cif file
        parser = MMCIFParser(QUIET=True)
        return parser.get_structure(self.pathway.stem, self.pathway)

    def chain_lengths(self, mode=ModelCount.RESIDUES):
        chains = self.model[0]
        if mode == ModelCount.ALL:
            return {chain.id: len([atom for atom in chain]) for chain in chains}

        elif mode == ModelCount.RESIDUES:

            return {chain.id: len(chain) for chain in chains}
        else:
            msg = f"Invalid mode. Please use {', '.join(ModelCount.__members__)}"
            logger.critical(msg)
            raise ValueError()

    def get_plddt_per_atom(self):
        plddt = {}
        for chain in self.model[0]:
            if self.input_params.get("sequences") is not None:
                if self.check_ligand(chain, self.input_params["sequences"]):
                    continue
            for residue in chain:
                for atom in residue:
                    if chain.id in plddt:
                        plddt[chain.id].append(atom.bfactor)
                    else:
                        plddt[chain.id] = [atom.bfactor]

        return plddt

    def get_plddt_per_residue(self, method=ResidueCountType.AVERAGE.value):
        plddts = {}

        if method not in ResidueCountType.values():
            logger.error(
                f"Invalid method. Please use {', '.join(ResidueCountType.__members__)}"
            )
            raise ValueError()

        for chain in self.model[0]:
            if self.input_params.get("sequences") is not None:
                if self.check_ligand(chain, self.input_params["sequences"]):
                    continue
            for residue in chain:
                if method == ResidueCountType.AVERAGE.value:
                    scores = 0
                    for atom in residue:
                        scores += atom.bfactor
                    score = scores / len(residue)

                elif method == ResidueCountType.CARBONALPHA.value:
                    for atom in residue:
                        if atom.id == "CA":
                            score = atom.bfactor
                            break

                if chain.id in plddts:
                    plddts[chain.id].append(score)

                else:
                    plddts[chain.id] = [score]

        return plddts

    def check_ligand(self, chain, sequences):
        """
        Check if the chain is a ligand, if it is, return True
        """
        for sequence in sequences:
            for sequence_type, sequence_data in sequence.items():
                if sequence_type == "ligand":
                    if "id" not in sequence_data:
                        continue
                    if isinstance(sequence_data["id"], str):
                        if chain.id == sequence_data["id"]:
                            return True
                    elif isinstance(sequence_data["id"], list):
                        if chain.id in sequence_data["id"]:
                            return True
        return False

    def to_file(self, output_file: Union[str, Path]):
        io = MMCIFIO()
        io.set_structure(self.model)
        io.save(str(output_file))


class ConfidenceJsonFile(FileBase):
    def __init__(self, json_file: Union[str, Path]):
        super().__init__(json_file)
        self.data = self.load_json_file()

    def load_json_file(self):
        # load the json file
        with open(self.pathway, "r") as f:
            data = json.load(f)

        return data

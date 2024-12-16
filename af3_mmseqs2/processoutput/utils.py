import json
import logging
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

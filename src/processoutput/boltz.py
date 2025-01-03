import logging
import re
from pathlib import Path
from typing import Union

from src.processoutput.utils import (CifFile, ConfidenceJsonFile, FileTypes,
                                     ModelCount, NpzFile)

logger = logging.getLogger("logger")


class BoltzOutput:
    def __init__(self, boltz_output_dir: Union[str, Path]):
        self.output_dir = Path(boltz_output_dir)
        self.name = re.sub(r"boltz_results_", "", self.output_dir.name, count=1)

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
        for pathway in self.output_dir.rglob("*"):
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

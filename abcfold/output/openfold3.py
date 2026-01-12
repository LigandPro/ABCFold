import logging
from pathlib import Path
from typing import Union

from abcfold.output.file_handlers import (CifFile, ConfidenceJsonFile,
                                          FileTypes, NpzFile)
from abcfold.output.utils import Af3Pae

logger = logging.getLogger("logger")


class OpenfoldOutput:
    def __init__(
        self,
        openfold_output_dirs: list[Union[str, Path]],
        input_params: dict,
        name: str,
        save_input: bool = False,
    ):
        """
        Object to process the output of an OpenFold 3 run

        Args:
            openfold_output_dirs (list[Union[str, Path]]): Path to the OpenFold 3
            output directory
            input_params (dict): Dictionary containing the input parameters used for the
            OpenFold 3 run
            name (str): Name given to the OpenFold 3 run
            save_input (bool): If True, OpenFold 3 was run with the save_input flag

        Attributes:
            output_dirs (list): List of paths to the OpenFold 3 output directory(s)
            input_params (dict): Dictionary containing the input parameters used for the
            OpenFold 3 run
            name (str): Name given to the OpenFold 3 run
            output (dict): Dictionary containing the processed output the contents
            of the OpenFold 3 output directory(s). The dictionary is structured as
            follows:

            {
                "seed-1": {
                    1: {
                        "cif": CifFile,
                        "scores": ConfidenceJsonFile,
                        "af3_pae": ConfidenceJsonFile,
                    },
                    2: {
                        "cif": CifFile,
                        "scores": ConfidenceJsonFile,
                        "af3_pae": ConfidenceJsonFile,
                    },
                },
                etc...
            }
            pae_files (list): Ordered list of ConfidenceJsonFile objects containing the
            PAE data
            cif_files (list): Ordered list of CifFile objects containing the model data
            scores_files (list): Ordered list of ConfidenceJsonFile objects containing
            the model scores
        """
        self.output_dirs = [Path(x) for x in openfold_output_dirs]
        self.input_params = input_params
        self.name = name
        self.save_input = save_input

        parent_dir = self.output_dirs[0].parent
        new_parent = parent_dir / f"openfold_{self.name}"
        new_parent.mkdir(parents=True, exist_ok=True)

        # add save input code

        new_output_dirs = []
        for output_dir in self.output_dirs:
            if output_dir.name.startswith("openfold3_results_"):
                new_path = new_parent / output_dir.name
                output_dir.rename(new_path)
                new_output_dirs.append(new_path)
            else:
                new_output_dirs.append(output_dir)
        self.output_dirs = new_output_dirs

        self.output = self.process_openfold_output()

        self.seeds = list(self.output.keys())
        self.pae_files = {
            seed: [value["pae"] for value in self.output[seed].values()]
            for seed in self.seeds
        }
        self.cif_files = {
            seed: [value["cif"] for value in self.output[seed].values()]
            for seed in self.seeds
        }
        self.scores_files = {
            seed: [value["score"] for value in self.output[seed].values()]
            for seed in self.seeds
        }
        self.pae_to_af3()
        self.af3_pae_files = {
            seed: [value["af3_pae"] for value in self.output[seed].values()]
            for seed in self.seeds
        }

    def process_openfold_output(self):
        """
        Function to process the output of a OpenFold 3 run
        """

        # TODO: Update this to match openfold output

        file_groups = {}
        for pathway in self.output_dirs:
            seed = pathway.name.split("_")[-1]
            if seed not in file_groups:
                file_groups[seed] = {}

            for output in pathway.rglob("*"):
                number = output.stem.split("_sample_")[-1]
                if not number.isdigit():
                    continue
                number = int(number)

                file_type = output.suffix[1:]

                if file_type == FileTypes.NPZ.value:
                    file_ = NpzFile(str(output))
                elif file_type == FileTypes.CIF.value:
                    file_ = CifFile(str(output), self.input_params)
                elif file_type == FileTypes.JSON.value:
                    file_ = ConfidenceJsonFile(str(output))
                else:
                    continue
                if number not in file_groups[seed]:
                    file_groups[seed][number] = [file_]
                else:
                    file_groups[seed][number].append(file_)

        seed_dict = {}
        for seed, models in file_groups.items():
            model_number_file_type_file = {}
            for model_number, files in models.items():
                intermediate_dict = {}
                for file_ in sorted(files, key=lambda x: x.suffix):
                    if "full_data" in file_.pathway.stem:
                        intermediate_dict["pae"] = file_
                    elif "summary_confidence" in file_.pathway.stem:
                        intermediate_dict["score"] = file_
                    elif file_.pathway.suffix == ".cif":
                        file_.name = f"openfold_{seed}_{model_number}"
                        intermediate_dict["cif"] = file_
                    else:
                        intermediate_dict[file_.suffix] = file_

                model_number_file_type_file[model_number] = intermediate_dict

            model_number_file_type_file = {
                key: model_number_file_type_file[key]
                for key in sorted(model_number_file_type_file)
            }
            seed_dict[seed] = model_number_file_type_file

        return seed_dict

    def pae_to_af3(self):
        """
        Convert the PAE data from OpenFold 3 to the format used by Alphafold3

        Returns:
            None
        """
        new_pae_files = {}
        for seed in self.seeds:
            for (pae_file, cif_file) in zip(self.pae_files[seed], self.cif_files[seed]):
                pae = Af3Pae.from_protenix(
                    pae_file.data,
                    cif_file,
                )

                out_name = pae_file.pathway

                pae.to_file(out_name)

                if seed not in new_pae_files:
                    new_pae_files[seed] = []
                new_pae_files[seed].append(ConfidenceJsonFile(out_name))

        self.output = {
            seed: {
                i: {
                    "cif": cif_file,
                    "af3_pae": new_pae_files[seed][i],
                    "scores": self.output[seed][i]["score"],
                }
                for i, cif_file in enumerate(self.cif_files[seed])
            }
            for seed in self.seeds
        }

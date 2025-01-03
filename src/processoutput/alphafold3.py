from pathlib import Path
from typing import Union

from src.processoutput.utils import CifFile, ConfidenceJsonFile


class AlphafoldOutput:
    def __init__(self, af3_output_dir: Union[str, Path]):
        self.output_dir = Path(af3_output_dir)
        self.name = self.output_dir.name

        self.af3_output = self.process_af3_output()
        self.seeds = list(self.af3_output.keys())
        self.cif_files = {
            seed: {
                model_number: value["cif"]
                for model_number, value in self.af3_output[seed].items()
            }
            for seed in self.seeds
        }
        self.json_files = {
            seed: {
                model_number: value["json"]
                for model_number, value in self.af3_output[seed].items()
            }
            for seed in self.seeds
        }

    def process_af3_output(self):
        file_groups = {}
        for pathway in self.output_dir.iterdir():
            if pathway.is_dir():
                seed = pathway.name.split("_")[0]
                sample = pathway.name.split("-")[-1]
                if seed not in file_groups:
                    file_groups[seed] = {}
                if not sample.isdigit():
                    continue
                sample = int(sample)
                if sample not in file_groups[seed]:
                    file_groups[seed][sample] = {}
                for file in pathway.iterdir():
                    if file.suffix == ".cif":
                        file_groups[seed][sample]["cif"] = CifFile(str(file))
                    elif file.suffix == ".json" and "summary" not in file.stem:
                        file_groups[seed][sample]["json"] = ConfidenceJsonFile(
                            str(file)
                        )
                    else:
                        continue

        for seed in file_groups:
            file_groups[seed] = {
                sample: file_groups[seed][sample]
                for sample in sorted(file_groups[seed])
            }
        return file_groups

import json
import shutil

from abcfold.output.file_handlers import CifFile, ConfidenceJsonFile
from abcfold.output.rosettafold3 import RosettafoldOutput
from abcfold.output.utils import Af3Pae, flatten


def test_process_rosettafold_output(test_data, tmp_path):
    with open("tests/test_data/alphafold3_6BJ9/6bj9_data.json", "r") as f:
        input_params = json.load(f)

    output_dir = tmp_path / "rosettafold_results_seed-1"
    output_dir.mkdir()
    cif_path = output_dir / "6BJ9_seed-1_sample-0_model.cif"
    shutil.copyfile("tests/test_data/alphafold3_6BJ9/6bj9_model.cif", cif_path)

    cif_file = CifFile(cif_path, input_params)
    token_count = len(flatten(cif_file.token_residue_ids().values()))
    pae = [[0.0 for _ in range(token_count)] for _ in range(token_count)]

    confidence_path = output_dir / "6BJ9_seed-1_sample-0_confidences.json"
    confidence_path.write_text(json.dumps({"pae": pae}))
    summary_path = output_dir / "6BJ9_seed-1_sample-0_summary_confidences.json"
    summary_path.write_text(json.dumps({"ptm": 0.2, "iptm": 0.3}))

    rosettafold_output = RosettafoldOutput([output_dir], input_params, "6BJ9")

    assert "seed-1" in rosettafold_output.output
    assert 0 in rosettafold_output.output["seed-1"]
    assert isinstance(rosettafold_output.cif_files["seed-1"][0], CifFile)
    assert isinstance(rosettafold_output.pae_files["seed-1"][0], ConfidenceJsonFile)
    assert isinstance(rosettafold_output.scores_files["seed-1"][0], ConfidenceJsonFile)


def test_rosettafold_pae_to_af3_pae(test_data):
    with open("tests/test_data/alphafold3_6BJ9/6bj9_data.json", "r") as f:
        input_params = json.load(f)

    cif_file = CifFile("tests/test_data/alphafold3_6BJ9/6bj9_model.cif", input_params)
    token_count = len(flatten(cif_file.token_residue_ids().values()))
    pae_matrix = [[0.0 for _ in range(token_count)] for _ in range(token_count)]
    pae = Af3Pae.from_rosettafold3({"pae": pae_matrix}, cif_file)

    assert len(pae.scores["pae"]) == token_count
    assert len(pae.scores["contact_probs"]) == token_count
    assert len(pae.scores["token_chain_ids"]) == token_count
    assert len(pae.scores["token_res_ids"]) == token_count

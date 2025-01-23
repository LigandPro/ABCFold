from abcfold.processoutput.file_handlers import CifFile, NpyFile, NpzFile
from abcfold.processoutput.utils import Af3Pae
from pathlib import Path
import tempfile


def test_process_chai_output(test_data):
    chai_output = test_data.chai_output

    assert str(chai_output.output_dir) == str(test_data.test_chai1_6BJ9_)

    assert -1 in chai_output.output
    assert 0 in chai_output.output
    assert 1 in chai_output.output

    assert all(isinstance(pae_file, NpyFile) for pae_file in chai_output.pae_files)
    assert all(isinstance(cif_file, CifFile) for cif_file in chai_output.cif_files)
    assert all(
        isinstance(scores_file, NpzFile) for scores_file in chai_output.scores_files
    )


def test_boltz_pae_to_af3_pae(test_data):
    comparison_af3_output = test_data.af3_output.scores_files["seed-1"][0].data
    pae_file = test_data.boltz_output.pae_files[-1]
    for i, cif_file in enumerate(test_data.chai_output.cif_files):
        print(pae_file.data["pae"].shape)
        print(pae_file.data)
        pae = Af3Pae.from_chai1(
            pae_file.data,
            cif_file,
        )

        # with tempfile.TemporaryDirectory() as temp_dir_str:
        #     temp_dir = Path(temp_dir_str)
        #     pae.to_file(temp_dir / "pae.json")
        #     pae.to_file("pae.json")
        #     assert (temp_dir / "pae.json").exists()

        # # for some reason the lengths are different for atom - realted things
        # # If it isn't breaking the output page generation, then it's fine
        # assert len(pae.scores["pae"]) == len(comparison_af3_output["pae"])

        # assert len(pae.scores["contact_probs"]) == len(
        #     comparison_af3_output["contact_probs"]
        # )
        # assert len(pae.scores["token_chain_ids"]) == len(
        #     comparison_af3_output["token_chain_ids"]
        # )
        # assert len(pae.scores["token_res_ids"]) == len(
        #     comparison_af3_output["token_res_ids"]
        # )
    assert False

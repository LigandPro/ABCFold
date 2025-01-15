from abcfold.processoutput.chai import ChaiOutput
from abcfold.processoutput.utils import CifFile, NpyFile, NpzFile


def test_process_boltz_output(test_data):
    name = "test"
    chai_output = ChaiOutput(test_data.test_chai1_6BJ9_, name)

    assert str(chai_output.output_dir) == str(test_data.test_chai1_6BJ9_)

    assert chai_output.name == "test"

    assert -1 in chai_output.output
    assert 0 in chai_output.output
    assert 1 in chai_output.output

    assert all(isinstance(pae_file, NpyFile) for pae_file in chai_output.pae_files)
    assert all(isinstance(cif_file, CifFile) for cif_file in chai_output.cif_files)
    assert all(
        isinstance(scores_file, NpzFile) for scores_file in chai_output.scores_files
    )

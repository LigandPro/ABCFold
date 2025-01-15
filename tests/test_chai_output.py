from abcfold.processoutput.chai import ChaiOutput
from abcfold.processoutput.utils import CifFile, NpyFile, NpzFile


def test_process_boltz_output(test_data):
    chai_output = ChaiOutput(test_data.test_chai1_)

    assert str(chai_output.output_dir) == str(test_data.test_chai1_)

    assert chai_output.name == "chai1"

    assert -1 in chai_output.output
    assert 0 in chai_output.output
    assert 1 in chai_output.output

    assert all(isinstance(pae_file, NpyFile) for pae_file in chai_output.pae_files)
    assert all(isinstance(cif_file, CifFile) for cif_file in chai_output.cif_files)
    assert all(
        isinstance(scores_file, NpzFile) for scores_file in chai_output.scores_files
    )

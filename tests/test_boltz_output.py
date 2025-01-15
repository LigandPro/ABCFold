import tempfile
from pathlib import Path

from abcfold.processoutput.boltz import BoltzOutput
from abcfold.processoutput.utils import CifFile, ConfidenceJsonFile, NpzFile


def test_process_boltz_output(test_data):
    name = "6BJ9"
    boltz_output = BoltzOutput(test_data.test_boltz_1_6BJ9_, name)
    assert str(boltz_output.output_dir) == str(
        Path(test_data.test_boltz_1_6BJ9_).parent.joinpath("boltz-1_6BJ9")
    )

    assert boltz_output.name == "6BJ9"

    assert 0 in boltz_output.output
    assert 1 in boltz_output.output
    assert 2 in boltz_output.output
    assert 3 in boltz_output.output
    assert 4 in boltz_output.output

    assert "plddt" in boltz_output.output[0]
    assert "pae" in boltz_output.output[0]
    assert "pde" in boltz_output.output[0]
    assert "cif" in boltz_output.output[0]
    assert "json" in boltz_output.output[0]

    assert "plddt" in boltz_output.output[1]
    assert "pae" in boltz_output.output[1]
    assert "pde" in boltz_output.output[1]
    assert "cif" in boltz_output.output[4]
    assert "json" in boltz_output.output[4]

    assert all(isinstance(pae_file, NpzFile) for pae_file in boltz_output.pae_files)
    assert all(
        isinstance(plddt_file, NpzFile) for plddt_file in boltz_output.plddt_files
    )
    assert all(isinstance(pde_file, NpzFile) for pde_file in boltz_output.pde_files)
    assert all(isinstance(cif_file, CifFile) for cif_file in boltz_output.cif_files)
    assert all(
        isinstance(scores_file, ConfidenceJsonFile)
        for scores_file in boltz_output.scores_files
    )

    assert boltz_output.cif_files[0].chain_lengths() == {"A": 20, "B": 16}

    boltz_output.add_plddt_to_cif()
    with tempfile.TemporaryDirectory() as temp_dir_str:
        temp_dir = Path(temp_dir_str)
        for i, cif_file in enumerate(boltz_output.cif_files):
            cif_file.to_file(temp_dir / f"{i}.cif")
            assert (temp_dir / f"{i}.cif").exists()

import tempfile
from pathlib import Path

from src.processoutput.boltz import BoltzOutput


def test_process_boltz_output(test_data):
    boltz_output = BoltzOutput(test_data.test_boltz_results_boltz_test_)
    assert str(boltz_output.output_dir) == test_data.test_boltz_results_boltz_test_

    assert boltz_output.name == "boltz_test"

    assert 0 in boltz_output.boltz_output
    assert 1 in boltz_output.boltz_output
    assert 2 in boltz_output.boltz_output
    assert 3 in boltz_output.boltz_output
    assert 4 in boltz_output.boltz_output

    assert "plddt" in boltz_output.boltz_output[0]
    assert "pae" in boltz_output.boltz_output[0]
    assert "pde" in boltz_output.boltz_output[0]
    assert "cif" in boltz_output.boltz_output[0]
    assert "json" in boltz_output.boltz_output[0]

    assert "plddt" in boltz_output.boltz_output[1]
    assert "pae" in boltz_output.boltz_output[1]
    assert "pde" in boltz_output.boltz_output[1]
    assert "cif" in boltz_output.boltz_output[4]
    assert "json" in boltz_output.boltz_output[4]

    assert boltz_output.cif_files[0].chain_lengths() == {"A": 20, "B": 16}

    boltz_output.add_plddt_to_cif()
    with tempfile.TemporaryDirectory() as temp_dir_str:
        temp_dir = Path(temp_dir_str)
        for i, cif_file in enumerate(boltz_output.cif_files):
            cif_file.to_file(temp_dir / f"{i}.cif")
            assert (temp_dir / f"{i}.cif").exists()

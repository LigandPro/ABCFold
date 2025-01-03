from abcfold.processoutput.alphafold3 import AlphafoldOutput


def test_process_boltz_output(test_data):
    af3_output = AlphafoldOutput(test_data.test_af3test_)
    assert str(af3_output.output_dir) == test_data.test_af3test_

    assert af3_output.name == "af3test"

    assert "seed-1" in af3_output.af3_output

    files = af3_output.af3_output["seed-1"]

    assert 0 in files
    assert 1 in files
    assert 2 in files
    assert 3 in files
    assert 4 in files

    assert "cif" in files[0]
    assert "json" in files[0]

    assert "cif" in files[4]
    assert "json" in files[4]

    json_file = af3_output.json_files["seed-1"][0]

    assert "atom_plddts" in json_file.data
    assert "pae" in json_file.data

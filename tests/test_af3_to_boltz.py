import tempfile

from af3_mmseqs2.boltz1.af3_to_boltz1 import BoltzYaml


def test_af3_to_boltz(test_data):
    with tempfile.TemporaryDirectory() as temp_dir:
        boltz_yaml = BoltzYaml(temp_dir)

        yaml_string_multi = boltz_yaml.json_to_yaml(test_data.test_inputAB_json)

        yaml_string_multi = yaml_string_multi.split("\n")

        assert yaml_string_multi[0] == "version: 1"
        assert yaml_string_multi[1] == "sequences:"
        assert yaml_string_multi[2] == "\tprotein:"
        assert yaml_string_multi[3] == "\t\tid: [A, B]"
        assert yaml_string_multi[4] == "\t\tsequence: GMRES"
        assert yaml_string_multi[5] == "\tprotein:"
        assert yaml_string_multi[6] == "\t\tid: C"
        assert yaml_string_multi[7] == "\t\tsequence: YANEN"
        assert yaml_string_multi[8] == "\tligand:"
        assert yaml_string_multi[9] == "\t\tid: [D, E]"
        assert yaml_string_multi[10] == "\t\tccd: ['ATP']"
        assert yaml_string_multi[11] == "\tligand:"
        assert yaml_string_multi[12] == "\t\tid: F"
        assert yaml_string_multi[13] == "\t\tsmiles: CC(=O)OC1C[NH+]2CCC1CC2"

        # assert False

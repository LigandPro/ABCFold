from abcfold.plots.plddt_plots import plot_plddt_distribution
from abcfold.processoutput.alphafold3 import AlphafoldOutput
from abcfold.processoutput.boltz import BoltzOutput
from abcfold.processoutput.chai import ChaiOutput


def test_plddt_plot(test_data):
    aname = "af3test"
    bname = "boltz_test"
    cname = "test"

    af3_output = AlphafoldOutput(test_data.test_alphafold3_6BJ9_, aname)
    boltz_output = BoltzOutput(test_data.test_boltz_1_6BJ9_, bname)
    chai_output = ChaiOutput(test_data.test_chai1_6BJ9_, cname)

    af3_files = af3_output.cif_files["seed-1"][0:2]
    boltz_files = boltz_output.cif_files[0:2]
    chai_files = chai_output.cif_files

    print(af3_files, boltz_files, chai_files)

    assert len(af3_files) == len(boltz_files) == len(chai_files)

    plot_plddt_distribution(*af3_files, *boltz_files, *chai_files)
    assert False

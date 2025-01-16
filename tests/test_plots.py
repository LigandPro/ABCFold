from abcfold.plots.plddt_plots import plot_plddt_distribution_plotly
from abcfold.processoutput.alphafold3 import AlphafoldOutput
from abcfold.processoutput.boltz import BoltzOutput
from abcfold.processoutput.chai import ChaiOutput


def test_plddt_plot(test_data):
    name = "6BJ9"

    af3_output = AlphafoldOutput(test_data.test_alphafold3_6BJ9_, name)
    boltz_output = BoltzOutput(test_data.test_boltz_1_6BJ9_, name)
    chai_output = ChaiOutput(test_data.test_chai1_6BJ9_, name)

    af3_files = af3_output.cif_files["seed-1"][0]
    boltz_files = boltz_output.cif_files[0]
    chai_files = chai_output.cif_files[0]

    print(af3_files, boltz_files, chai_files)

    # assert len(af3_files) == len(boltz_files) == len(chai_files)
    plot_files = [af3_files, boltz_files, chai_files]

    # plot_plddt_distribution(*af3_files, *boltz_files, *chai_files)
    plot_plddt_distribution_plotly(*plot_files)
    assert False

    # Issues with plot:
    # - Too mnay residues so might be useful to plot per chain and do comparison
    # - Make an option to plot full model with chain areas highlighted
    # - Make an option to only take the top plddt scores

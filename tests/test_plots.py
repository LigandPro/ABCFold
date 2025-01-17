from abcfold.plots.plddt_plots import plot_plddt_distribution_plotly


def test_plddt_plot(test_data):
    af3_files = test_data.af3_output.cif_files["seed-1"][0]
    boltz_files = test_data.boltz_output.cif_files[0]
    chai_files = test_data.chai_output.cif_files[0]

    # assert len(af3_files) == len(boltz_files) == len(chai_files)
    plot_files = [
        af3_files,
        boltz_files,
        chai_files,
    ]

    # plot_plddt_distribution(*af3_files, *boltz_files, *chai_files)
    plot_plddt_distribution_plotly(*plot_files)
    assert False

    # Issues with plot:
    # - Too mnay residues so might be useful to plot per chain and do comparison
    # - Make an option to plot full model with chain areas highlighted
    # - Make an option to only take the top plddt scores

import tempfile
from pathlib import Path

from abcfold.plots.plddt_plot import plot_plddt_distribution_plotly
from abcfold.plots.pae_plots import create_pae_plots


# def test_plddt_plot(test_data):
#     af3_files = test_data.af3_output.cif_files["seed-1"][0:1]
#     boltz_files = test_data.boltz_output.cif_files[0:1]
#     chai_files = test_data.chai_output.cif_files[0:1]

#     af3_files = test_data.af3_output.cif_files["seed-1"]
#     boltz_files = test_data.boltz_output.cif_files
#     chai_files = test_data.chai_output.cif_files

#     assert len(af3_files) == len(boltz_files) == len(chai_files)
#     plot_files = {
#         "Alphafold3": af3_files,
#         "Boltz-1": boltz_files,
#         "Chai-1": chai_files,
#     }

#     with tempfile.TemporaryDirectory() as temp_dir:
#         plot_plddt_distribution_plotly(
#             plot_files,
#             output_name=f"{temp_dir}/test.html",
#         )

#         assert Path(f"{temp_dir}/test.html").exists()


def test_pae_plots(test_data):
    outputs = [test_data.af3_output, test_data.boltz_output, test_data.chai_output]

    with tempfile.TemporaryDirectory() as temp_dir_str:
        temp_dir = Path(temp_dir_str)
        create_pae_plots(*outputs, output_dir=temp_dir)
        print([file for file in temp_dir.iterdir()])

    assert False

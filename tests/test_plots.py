import tempfile
from pathlib import Path

from abcfold.plots.pae_plot import create_pae_plots
from abcfold.plots.plddt_plot import plot_plddt


def test_plddt_plot(output_objs):
    af3_files = output_objs.af3_output.cif_files["seed-1"][0:1]
    boltz_files = output_objs.boltz_output.cif_files[0:1]
    chai_files = output_objs.chai_output.cif_files[0:1]

    af3_files = output_objs.af3_output.cif_files["seed-1"]
    boltz_files = output_objs.boltz_output.cif_files
    chai_files = output_objs.chai_output.cif_files

    assert len(af3_files) == len(boltz_files) == len(chai_files)
    plot_files = {
        "Alphafold3": af3_files,
        "Boltz-1": boltz_files,
        "Chai-1": chai_files,
    }

    with tempfile.TemporaryDirectory() as temp_dir:
        plot_plddt(
            plot_files,
            output_name=f"{temp_dir}/test.html",
        )

        assert Path(f"{temp_dir}/test.html").exists()


def test_pae_plots(output_objs):
    outputs = [
        output_objs.af3_output,
        output_objs.boltz_output,
        output_objs.chai_output,
    ]

    with tempfile.TemporaryDirectory() as temp_dir_str:
        temp_dir = Path(temp_dir_str)
        create_pae_plots(outputs, output_dir=temp_dir)
        assert len(list(temp_dir.glob("*.html"))) == 6

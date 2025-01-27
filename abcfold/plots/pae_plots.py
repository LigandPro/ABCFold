# Run the code for the PAE plots

from pathlib import Path
from typing import Union, List, Optional
from abcfold.processoutput.alphafold3 import AlphafoldOutput
from abcfold.processoutput.boltz import BoltzOutput
from abcfold.processoutput.chai import ChaiOutput

from multiprocessing import Process
import subprocess
import logging

logger = logging.getLogger(__name__)

CSSPATHS = {
    "A": Path(__file__).parent.joinpath(
        "pae-viewer-main", "standalone", "css", "paeViewerStandaloneLayoutAF3.css"
    ),
    "B": Path(__file__).parent.joinpath(
        "pae-viewer-main", "standalone", "css", "paeViewerStandaloneLayoutBoltz.css"
    ),
    "C": Path(__file__).parent.joinpath(
        "pae-viewer-main", "standalone", "css", "paeViewerStandaloneLayoutChai.css"
    ),
}

PAEVIEWER = pae_viewer_main = Path(__file__).parent.joinpath(
    "pae-viewer-main", "standalone", "pae_viewer.py"
)

CREATETEMPLATE = Path(__file__).parent.joinpath(
    "pae-viewer-main", "standalone", "create_template.py"
)


def create_pae_plots(
    *outputs: List[Union[AlphafoldOutput, BoltzOutput, ChaiOutput]],
    output_dir: Optional[Union[str, Path]] = None,
):
    pathway_plot = {}
    run_scripts = []

    for output in outputs:
        plots_dir = (
            Path(output_dir)
            if output_dir
            else output.output_dir.parent.joinpath(".plots")
        )
        plots_dir.mkdir(exist_ok=True)
        #
        if isinstance(output, BoltzOutput):
            css_path = CSSPATHS["B"]
            template_file = plots_dir.joinpath("boltz_template.html")
            cmd = get_template_run_script(
                "ABCFold - Boltz-1 Output",
                css_path,
                template_file,
            )
            run_script(cmd)

        elif isinstance(output, ChaiOutput):
            css_path = CSSPATHS["C"]
            cmd = get_template_run_script(
                "ABCFold - Chai-1 Output",
                css_path,
                template_file,
            )
            run_script(cmd)

        elif isinstance(output, AlphafoldOutput):
            css_path = CSSPATHS["A"]
            cmd = get_template_run_script(
                "ABCFold - AlphaFold-3 Output",
                css_path,
                template_file,
            )
            run_script(cmd)

            for seed in output.seeds:
                run_scripts.extend(
                    prepare_scripts(
                        output.cif_files[seed],
                        output.af3_pae_files[seed],
                        plots_dir,
                        pathway_plot,
                        True,
                    )
                )
            continue
        else:
            logger.error("Invalid output type")
            raise ValueError()

        run_scripts.extend(
            prepare_scripts(
                output.cif_files,
                output.af3_pae_files,
                plots_dir,
                pathway_plot,
                False,
            )
        )

    processes = [Process(target=run_script, args=(script,)) for script in run_scripts]
    for process in processes:
        process.start()
    for process in processes:
        process.join()

    # remove the template file
    template_file.unlink()

    return pathway_plot


def prepare_scripts(cif_files, pae_files, plots_dir, pathway_plot, is_af3):
    scripts = []
    for cif_file, pae_file in zip(cif_files, pae_files):
        labels = [f"Chain-{chain}" for chain in cif_file.chain_lengths()]
        print(pae_file)
        plot_pathway = plots_dir.joinpath(
            f"{pae_file.pathway.stem}_{'af3_' if is_af3 else ''}pae_plot.html"
        )
        pae_viewer_script = get_pae_run_script(
            cif_file.pathway, labels, pae_file.pathway, plot_pathway
        )
        pathway_plot[plot_pathway] = plot_pathway
        scripts.append(pae_viewer_script)
    return scripts


def run_script(cmd):

    with subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE) as proc:
        stdout, stderr = proc.communicate()
        proc.wait()
        print(" ".join(cmd))
        print(stdout.decode())
        if proc.returncode != 0:
            raise subprocess.CalledProcessError(proc.returncode, cmd, stderr)


def get_pae_run_script(
    cif_path: Union[str, Path],
    labels: List[str],
    pae_path: Union[str, Path],
    output_file: Union[str, Path],
    template_file: Union[str, Path],
):
    """ """
    cif_path = Path(cif_path)
    pae_path = Path(pae_path)
    output_file = Path(output_file)

    cmd = []
    labels_string = ";".join(labels)
    labels_string = rf'"{labels_string}"'

    cmd.append("python")
    cmd.append(str(PAEVIEWER.resolve()))
    cmd.append("--structure")
    cmd.append(str(cif_path.resolve()))
    cmd.append("--labels")

    cmd.append(labels_string)
    cmd.append("--scores")
    cmd.append(str(pae_path.resolve()))
    cmd.append("--output_file")
    cmd.append(str(output_file.resolve()))
    cmd.append("--template_file")
    cmd.append(str(template_file.resolve()))

    return cmd


def get_template_run_script(
    title: str,
    standalonecss: str,
    output_file: Union[str, Path],
):
    """ """
    cmd = []
    cmd.append("python")
    cmd.append(str(CREATETEMPLATE.resolve()))
    cmd.append("--title")
    title = rf'"{title}"'
    cmd.append(title)
    cmd.append("--standalonecss")
    cmd.append(standalonecss)
    cmd.append("--output_file")
    cmd.append(str(output_file.resolve()))

    return cmd

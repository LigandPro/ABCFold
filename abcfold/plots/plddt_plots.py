# using matplotlib or seaborn to plot the pLDDT distribution
# import plotly.express as px
# import plotly.graph_objects as go
import matplotlib.pyplot as plt

from abcfold.processoutput.utils import CifFile


def plot_plddt_distribution(*cif_models: CifFile, source_amount=3):

    fig, ax = plt.subplots(figsize=(12, 5))

    colours = list(plt.cm.tab20.colors)
    for i, cif_model in enumerate(cif_models):
        i = i % source_amount
        plddt = cif_model.residue_plddts
        chain_ranges = {
            chain: range(len(plddt))
            for chain, plddt in cif_model.residue_plddt_per_chain.items()
        }
        counter = 0
        ax.legend()
        for chain, chain_range in chain_ranges.items():
            counter += chain_range[-1]
            # check if the there is a vertical line on the plot already with the label
            # of the chain
            if not ax.get_legend().get_texts():
                ax.axvline(
                    x=counter,
                    color=colours.pop(),
                    linestyle="--",
                    alpha=0.8,
                    label=f"Chain {chain}",
                )

        ax.plot(
            range(len(plddt)),
            plddt,
            label=cif_model.cif_file.stem,
            linestyle="dotted",
        )
        for line in ax.lines:
            line.set_linewidth(1.2)

    ax.set_xlabel("Residue Number")
    ax.set_ylabel("pLDDT Score")
    ax.set_title("pLDDT Distribution")
    ax.legend()
    plt.savefig("plddt_distribution.png")


def plot_plddt_distribution_plotly(*cif_models: CifFile, source_amount=3):
    pass

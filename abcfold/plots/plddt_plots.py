# using matplotlib or seaborn to plot the pLDDT distribution
# import plotly.express as px
import matplotlib.pyplot as plt

from abcfold.processoutput.utils import CifFile


def plot_plddt_distribution(*cif_models: CifFile):
    # create line plots with the residue numbers on the x-axis and the pLDDT scores
    # on the y-axis
    # using plotly

    # Make each line a seperate model

    # Create a figure

    # Add traces for each model

    # plddts = []
    # for cif_model in cif_models:
    #     plddts.append(cif_model.get_plddt())

    # fig = px.line(
    #     plddts,
    #     title="pLDDT Distribution",
    #     labels={"x": "Residue Number", "y": "pLDDT Score"},
    # )

    # for i, plddt in enumerate(plddts):
    #     fig.add_scatter(x=range(len(plddt)), y=plddt, name=f"Model {i}")

    # fig.show()

    # using matplotlib

    fig, ax = plt.subplots()
    for cif_model in cif_models:
        plddt = cif_model.get_plddt()
        ax.plot(range(len(plddt)), plddt, label=cif_model.cif_file.stem)
    ax.set_xlabel("Residue Number")
    ax.set_ylabel("pLDDT Score")
    ax.set_title("pLDDT Distribution")
    ax.legend()
    plt.savefig("plddt_distribution.png")

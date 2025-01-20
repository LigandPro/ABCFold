# import numpy as np
import logging
from typing import Dict, List

import plotly.express as px
import plotly.graph_objects as go

from abcfold.processoutput.utils import CifFile

logger = logging.getLogger("logger")


def plot_plddt_distribution_plotly(cif_models_dict: Dict[str, List[CifFile]]):

    fig = go.Figure()
    fig.update_xaxes(showgrid=True, gridwidth=1, gridcolor="LightGrey")
    fig.update_yaxes(showgrid=True, gridwidth=1, gridcolor="LightGrey")

    colours = list(px.colors.qualitative.T10)
    colour_index = 0

    cif_models = [
        cif_file for cif_files in cif_models_dict.values() for cif_file in cif_files
    ]

    for i, (key, cif_models) in enumerate(cif_models_dict.items()):
        for cif_model in cif_models:
            plddt = cif_model.residue_plddts
            chain_ranges = {
                chain: range(len(plddt))
                for chain, plddt in cif_model.residue_plddt_per_chain.items()
            }
            counter = 0
            for chain, chain_range in chain_ranges.items():
                counter += chain_range[-1]
                fig.add_vline(
                    x=counter,
                    line=dict(color=colours[colour_index % len(colours)], dash="dash"),
                    opacity=0.8,
                    annotation_text=f"Chain {chain}",
                    annotation_position="top left",
                )
                colour_index += 1

            fig.add_trace(
                go.Scatter(
                    x=list(range(len(plddt))),
                    y=plddt,
                    mode="lines",
                    legendgroup=key,
                    legendgrouptitle_text=Bold(key),
                    name=int(cif_model.name.split("_")[-1]) + 1,
                    line=dict(dash="dot", width=1.6),
                )
            )
    models_no = len(cif_models)
    sources = i + 1

    steps = []
    steps.append(
        dict(
            method="restyle",
            args=[
                {"visible": [True] * models_no * (i + 1)},
                {"title": "All Models"},
            ],
            label="All Models",
        )
    )

    for i in range(sources - 1):
        step = dict(
            method="restyle",
            args=[
                {"visible": [False] * models_no * sources},
                {"title": f"Model {i+1}"},
            ],
            label=f"Model {i+1}",
        )
        for j in range(i, models_no * sources, models_no):
            step_list = step["args"]
            if isinstance(step_list, list):
                step_list[0]["visible"][j] = True
            else:
                logger.error(
                    "Error, MyPy made me change this for some reason and if \
this if failing that means the computer wins."
                )
                raise ValueError()
            # step["args"][0]["visible"][j] = True
        steps.append(step)

    fig.update_layout(
        xaxis_title=Bold("Residue Number"),
        yaxis_title=Bold("pLDDT Score"),
        title=Bold("pLDDT Distribution"),
        legend_title=Bold("Models"),
        plot_bgcolor="white",
        sliders=[dict(steps=steps, currentvalue={"prefix": Bold("Selection: ")})],
    )

    fig.update_layout(
        showlegend=True,
    )

    fig.show()


def Bold(string):
    return f"<b>{string}</b>"

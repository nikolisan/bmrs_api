from typing import Any

import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.figure import Figure

from src.data.metrics import compute_imbalance_cost

GREEN = "#2ca02c"
RED = "#d62728"
GREY = "#7f7f7f"


def build_price_scatter(df: pd.DataFrame) -> Figure:
    """NIV vs system price"""
    fig, ax = plt.subplots(figsize=(8, 8), layout="constrained")
    ax.scatter(df["netImbalanceVolume"], df["systemSellPrice"], alpha=0.7)
    ax.set_title("NIV vs System Price")
    ax.set_xlabel("NIV (MWh)")
    ax.set_ylabel("System Price (£/MWh)")
    ax.grid(True, alpha=0.3)

    x_lim = max(abs(df["netImbalanceVolume"].min()), abs(df["netImbalanceVolume"].max()))
    ax.set_xlim(-x_lim, x_lim)
    ax.axvline(0, color="black", linewidth=0.5)
    ax.axhline(0, color="black", linewidth=0.5)
    ax.set_box_aspect(1)
    return fig


def build_report_figure(df: pd.DataFrame, metrics: dict[str, Any]) -> Figure:
    fig, axes = plt.subplots(
        3, 1, sharex=True, figsize=(12, 10),
        gridspec_kw={"height_ratios": [0.3, 0.4, 0.3]},
        layout="constrained",
    )
    ax_price, ax_niv, ax_cash = axes
    x = df.index

    ax_price.plot(x, df["systemSellPrice"], label="System Price")
    ax_price.set_title("System Price (£/MWh)")
    ax_price.set_ylabel("£/MWh")
    ax_price.grid(True, alpha=0.3)

    niv_colors = [GREEN if v < 0 else RED for v in df["netImbalanceVolume"]]
    ax_niv.bar(x, df["netImbalanceVolume"], color=niv_colors, label="NIV", width=0.9)
    ax_niv.set_title("Net Imbalance Volume (MWh) - green=long, red=short")
    ax_niv.set_ylabel("MWh")
    ax_niv.axhline(0, color="black", linewidth=0.5)
    ax_niv.grid(True, alpha=0.3)

    if "imbalance" in df.columns and df["imbalance"].notna().any():
        ax_niv.plot(
            x, df["imbalance"],
            linestyle=":", color=GREY, label="IIV",
        )
        ax_niv.legend(loc="upper right")

    ax_cash.plot(x, compute_imbalance_cost(df).cumsum(), label="Cumulative £")
    ax_cash.set_title("Cumulative Imbalance Cost (£)")
    ax_cash.set_ylabel("£")
    ax_cash.set_xlabel("Settlement Period")
    ax_cash.grid(True, alpha=0.3)

    if "is_interpolated" in df.columns:
        for sp in df.index[df["is_interpolated"]]:
            for ax in axes:
                ax.axvspan(sp - 0.5, sp + 0.5, color="lightgrey", alpha=0.3, zorder=0)

    fig.suptitle(f"Daily Report — {metrics['settlement_date']}", fontsize=14)
    return fig

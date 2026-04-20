from typing import Any

import pandas as pd
from datetime import date


def compute_imbalance_cost(df: pd.DataFrame) -> pd.Series:
    """
    Computes the per-period imbalance cost in accordance with BSC Section T 4.7.

    Main assumption: the netImbalanceVolume is aggregated for all accounts.
     - CAEIaj = -QAEIaj * SSPj
     - TCEIj = ΣaCAEIaj

    Sign convention: positive = aggregate parties net receive, negative = net pay.
    """
    return -df["netImbalanceVolume"] * df["systemSellPrice"]


def compute_daily_metrics(df: pd. DataFrame, settlement_date: date) -> dict[str, Any]:
    """
    Returns basic metrics for the day.
    """
    cost = compute_imbalance_cost(df)
    turnover = (df["netImbalanceVolume"].abs() * df["systemSellPrice"]).sum()
    total_niv = df["netImbalanceVolume"].abs().sum()
    unit_rate = (float("nan") if total_niv == 0 else turnover / total_niv)

    system_long = df["netImbalanceVolume"] < 0
    system_short = df["netImbalanceVolume"] > 0

    interpolated = []
    if "is_interpolated" in df.columns:
        interpolated = df.index[df["is_interpolated"]].to_list()

    return {
        "settlement_date": settlement_date,
        "total_periods": len(df),
        "total_imbalance_cost": float(cost.sum()),
        "total_turnover": float(turnover),
        "unit_rate_gbp_per_mwh": unit_rate,
        "pct_periods_long": float(system_long.mean()*100),
        "pct_periods_short": float(system_short.mean()*100),
        "periods_interpolated": interpolated
    }
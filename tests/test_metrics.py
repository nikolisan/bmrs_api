from datetime import date

import pandas as pd
import pytest

from src.data.metrics import compute_daily_metrics, compute_imbalance_cost


def _make_df(niv: list[float], ssp: list[float], sbp: list[float] | None = None) -> pd.DataFrame:
    n = len(niv)
    sbp = sbp or ssp
    data = {
        "netImbalanceVolume": niv,
        "systemSellPrice": ssp,
        "systemBuyPrice": sbp,
    }
    return pd.DataFrame(data, index=pd.RangeIndex(1, n + 1, name="settlementPeriod"))


def test_compute_imbalance_cost_sign_convention():
    # System long (NIV<0): cost = -(-10)*50 = +500 (aggregate parties receive)
    # System short (NIV>0): cost = -(10)*50 = -500 (aggregate parties pay)
    df = _make_df(niv=[-10.0, 10.0], ssp=[50.0, 50.0])
    cost = compute_imbalance_cost(df)
    assert cost.iloc[0] == 500.0
    assert cost.iloc[1] == -500.0


def test_compute_imbalance_cost_returns_series_length():
    df = _make_df(niv=[-10.0, 5.0, 0.0], ssp=[50.0, 100.0, 75.0])
    cost = compute_imbalance_cost(df)
    assert len(cost) == 3
    assert cost.iloc[2] == 0.0


def test_daily_metrics_totals():
    df = _make_df(niv=[-10.0, 10.0, -20.0], ssp=[50.0, 50.0, 100.0])
    m = compute_daily_metrics(df, date(2026, 2, 1))
    # cost: 500, -500, 2000 -> sum = 2000
    assert m["total_imbalance_cost"] == 2000.0
    # turnover: 10*50 + 10*50 + 20*100 = 3000
    assert m["total_turnover"] == 3000.0
    # unit rate: 3000 / 40 = 75
    assert m["unit_rate_gbp_per_mwh"] == 75.0
    assert m["total_periods"] == 3


def test_daily_metrics_unit_rate_nan_when_no_niv():
    df = _make_df(niv=[0.0, 0.0], ssp=[50.0, 50.0])
    m = compute_daily_metrics(df, date(2026, 2, 1))
    assert pd.isna(m["unit_rate_gbp_per_mwh"])

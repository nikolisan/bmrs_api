from datetime import date, time, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

import pandas as pd
from loguru import logger

from src.api.models import SystemPriceRecord

logger.add("data_clean.log", rotation="10 MB", level="WARNING")


def _expected_periods(settlement_date: datetime) -> int:
    """
    Helper function to calculate the expected number of 30min periods in a day.
    Returns 48 for normal days, 46 for March and 48 October BST shift.
    """

    start = datetime.combine(settlement_date, time.min, tzinfo=ZoneInfo.no_cache("Europe/London"))
    end = datetime.combine(settlement_date + timedelta(days=1), time.min, tzinfo=ZoneInfo.no_cache("Europe/London"))
    return int((end - start).total_seconds() // 1800)


def create_system_price_dataframe(settlement_periods: list[SystemPriceRecord]) -> pd.DataFrame:

    if not settlement_periods:
        raise ValueError(f"No settlement periods provided.")
    
    rows: list[dict[str, Any]] = [sp.model_dump() for sp in settlement_periods]

    df = pd.DataFrame(rows)
    
    df = df.sort_values("createdDateTime").drop_duplicates("settlementPeriod", keep="last")
    df = df.set_index("settlementPeriod")
    df = df.sort_index()

    # FIXED: Why some days have 48 and other 50 SPs? It has to do with the BST. Last Sunday of March has 46, last Sunday Oct has 50
    _date = df.iloc[0]["settlementDate"]
    _expected = _expected_periods(_date)
    
    if len(df) > _expected:
        raise ValueError(f"{_date}: Expected {_expected} SP, got {len(df)}.")
    
    # Fill missing price values
    df["is_interpolated"] = df[["systemSellPrice", "systemBuyPrice", "netImbalanceVolume"]].isna().any(axis=1)
    df["systemSellPrice"] = df["systemSellPrice"].ffill().bfill()
    df["systemBuyPrice"] = df["systemBuyPrice"].ffill().bfill()
    df["netImbalanceVolume"] = df["systemBuyPrice"].ffill().bfill()

    return df
from typing import Any

import pandas as pd
from loguru import logger

from src.api.models import SystemPriceRecord

logger.add("data_clean.log", rotation="10 MB", level="WARNING")


def create_system_price_dataframe(settlement_periods: list[SystemPriceRecord]) -> pd.DataFrame:

    if not settlement_periods:
        raise ValueError(f"No settlement periods provided.")
    
    rows: list[dict[str, Any]] = [sp.model_dump() for sp in settlement_periods]

    df = pd.DataFrame(rows)
    
    df = df.sort_values("createdDateTime").drop_duplicates("settlementPeriod", keep="last")
    df = df.set_index("settlementPeriod")
    df = df.sort_index()

    # TODO: Why some days have 48 and other 50 SPs?
    if len(df) != 48:
        raise ValueError(f"{df.iloc[0]["settlementDate"]}: Expected 48 SP, got {len(df)}.")
    
    # Fill missing price values
    df["is_interpolated"] = df[["systemSellPrice", "systemBuyPrice", "netImbalanceVolume"]].isna().any(axis=1)
    df["systemSellPrice"] = df["systemSellPrice"].ffill().bfill()
    df["systemBuyPrice"] = df["systemBuyPrice"].ffill().bfill()
    df["netImbalanceVolume"] = df["systemBuyPrice"].ffill().bfill()

    return df
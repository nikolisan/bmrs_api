from datetime import date, time, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

import pandas as pd
from loguru import logger

from src.api.models import SystemPriceRecord, ImbalanceRecord


def _expected_periods(settlement_date: datetime) -> int:
    """
    Helper function to calculate the expected number of 30min periods in a day.
    Returns 48 for normal days, 46 for March and 48 October BST shift.
    """
    if isinstance(settlement_date, str):
        settlement_date = datetime.strptime(settlement_date, "%Y-%m-%d")
        
    start = datetime.combine(settlement_date, time.min, tzinfo=ZoneInfo.no_cache("Europe/London"))
    end = datetime.combine(settlement_date + timedelta(days=1), time.min, tzinfo=ZoneInfo.no_cache("Europe/London"))
    return int((end - start).total_seconds() // 1800)


def create_system_price_dataframe(settlement_periods: list[SystemPriceRecord]) -> pd.DataFrame:
    """
    Cleans, aligns, and interpolates API system price data.

    Transforms raw API records into a continuous daily time series.
    It performs reindexing to handle missing periods and adjusts the expected row count for BST clock changes (46, 48, or 50 periods).

    Args:
        settlement_periods: A list of SystemPriceRecord objects containing price and volume data for a specific date.

    Returns:
        pd.DataFrame: A DataFrame indexed by 'settlementPeriod' with missing values filled via linear interpolation and an 'is_interpolated' flag.
    
    Raises:
        ValueError: Input list is empty or the len of the list is more than the expected.
    """
    
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
    
    if len(df) < _expected:
        index_periods = pd.RangeIndex(1, _expected + 1, name="settlementPeriod")
        missing = sorted(set(index_periods) -  set(df.index))
        df = df.reindex(index_periods)
        for missing_sp in missing:
            logger.warning(f"{_date}: SP{missing_sp} is missing. Dataset will be interpolated.")
    
    # Fill missing price and volume values
    cols_to_fill = ["systemSellPrice", "systemBuyPrice", "netImbalanceVolume"]
    df["is_interpolated"] = df[cols_to_fill].isna().any(axis=1)
    
    num_missing = df["is_interpolated"].sum()
    if num_missing > 0:
        logger.warning(f"{_date}: Interpolating {num_missing}/{_expected} periods.")

    df[cols_to_fill] = df[cols_to_fill].interpolate(method='linear')
    df[cols_to_fill] = df[cols_to_fill].bfill().ffill()

    return df


def create_IIV_dataframe(records: list[ImbalanceRecord], target_date: str) -> pd.DataFrame:
    """
    Cleans and aligns API Indicated Imbalance Volume (IIV) data from the IMBALNGC dataset.

    Transforms raw API records into a continuous daily time series.
    Filters to the target settlement date, deduplicates by keeping the latest record per settlement period (by publishTime),
    drops the 'dataset' and 'boundary' columns, and reindexes to the expected period count for the day (46, 48, or 50 for BST shifts).
    Missing periods are left as NaN (not interpolated).

    Args:
        records: A list of ImbalanceRecord objects containing IIV data.
        target_date: The settlement date to filter records by, in 'YYYY-MM-DD' format.

    Returns:
        pd.DataFrame: A DataFrame indexed by 'settlementPeriod' with one row per expected period for the day.

    Raises:
        ValueError: Input list is empty or the number of records for the target date exceeds the expected period count.
    """
    if not records:
        raise ValueError(f"No Imbalance Records provided.")

    rows = [ImbalanceRecord.model_validate(item).model_dump() for item in records]
    
    df = pd.DataFrame(rows)

    df = df[df['settlementDate'].astype(str) == target_date]
    df = df.sort_values(by="publishTime", ascending=True)
    df = df.drop_duplicates(subset=["settlementPeriod"], keep="last")
    df = df.set_index("settlementPeriod")
    df = df.sort_index()
    df = df.drop(columns=["dataset", "boundary"], errors="ignore")

    _expected = _expected_periods(target_date)

    if len(df) > _expected:
        raise ValueError(f"{target_date}: Expected {_expected} SP, got {len(df)}.")
    
    if len(df) < _expected:
        index_periods = pd.RangeIndex(1, _expected + 1, name="settlementPeriod")
        missing = sorted(set(index_periods) -  set(df.index))
        df = df.reindex(index_periods)
        for missing_sp in missing:
            logger.warning(f"{target_date}: SP{missing_sp} is missing.")

    return df


def merge_dataframes(prices_df: pd.DataFrame, iiv_df: pd.DataFrame) -> pd.DataFrame:
    merged_df = pd.merge(
        prices_df, iiv_df,
        left_index=True, right_index=True,
        how="left", suffixes=("", "_iiv"),
    )
    return merged_df

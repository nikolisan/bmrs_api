import json
from datetime import date, datetime, timezone
from pathlib import Path

import pandas as pd
import pytest

from src.api.models import SystemPriceRecord, ImbalanceRecord
from src.data.clean import (_expected_periods, create_IIV_dataframe, create_system_price_dataframe, merge_dataframes)

FIXTURES = Path(__file__).parent


# Helper function to load local json response
def _load_records(filename: str) -> list[SystemPriceRecord]:
    data = json.loads((FIXTURES / filename).read_text())
    return [SystemPriceRecord.model_validate(r) for r in data["data"]]


def _make_record(**overrides) -> SystemPriceRecord:
    base = {
        "settlementDate": date(2026, 2, 1),
        "settlementPeriod": 1,
        "startTime": datetime(2026, 2, 1, 0, 0, tzinfo=timezone.utc),
        "systemSellPrice": 50.0,
        "systemBuyPrice": 50.0,
        "netImbalanceVolume": -10.0,
        "createdDateTime": datetime(2026, 2, 1, 0, 15, tzinfo=timezone.utc),
    }
    base.update(overrides)
    return SystemPriceRecord.model_validate(base)


def _make_iiv_record(**overrides) -> ImbalanceRecord:
    base = {
        "settlementDate": date(2026, 2, 1),
        "settlementPeriod": 1,
        "startTime": datetime(2026, 2, 1, 0, 0, tzinfo=timezone.utc),
        "publishTime": datetime(2026, 2, 1, 0, 15, tzinfo=timezone.utc),
        "imbalance": 500.0,
        "boundary": "N",
    }
    base.update(overrides)
    return ImbalanceRecord.model_validate(base)


# Test period count

def test_expected_period_count_normal():
    assert _expected_periods(date(2026, 3, 30)) == 48
    assert _expected_periods(date(2025, 10, 27)) == 48


def test_expected_period_count_march_dst():
    assert _expected_periods(date(2026, 3, 29)) == 46


def test_expected_period_count_october_dst():
    assert _expected_periods(date(2025, 10, 26)) == 50


# create_system_price_dataframe tests

def test_deduplication_keeps_latest():
    records = [_make_record(settlementPeriod=sp) for sp in range(1, 49)]
    records.append(_make_record(
        settlementPeriod=1,
        systemSellPrice=99.0,
        systemBuyPrice=99.0,
        createdDateTime=datetime(2026, 2, 1, 3, 0, tzinfo=timezone.utc),
    ))
    df = create_system_price_dataframe(records)
    assert df.loc[1, "systemSellPrice"] == 99.0


def test_missing_periods_interpolated():
    records = [_make_record(settlementPeriod=sp) for sp in range(1, 48)]  # 47 of 48, SP 48 missing
    df = create_system_price_dataframe(records)
    assert len(df) == 48
    assert df.loc[48, "is_interpolated"] == True


def test_too_many_periods_raises():
    records = [_make_record(settlementPeriod=sp) for sp in range(1, 50)]  # 49 > 48
    with pytest.raises(ValueError):
        create_system_price_dataframe(records)


def test_march_bst_46_periods():
    records = _load_records("march_bst.json")
    df = create_system_price_dataframe(records)
    assert len(df) == 46


def test_october_bst_50_periods():
    records = _load_records("october_bst.json")
    df = create_system_price_dataframe(records)
    assert len(df) == 50


# IIV Testing

def test_iiv_empty_raises():
    with pytest.raises(ValueError):
        create_IIV_dataframe([], "2026-02-01")


def test_iiv_deduplication_keeps_latest():
    records = [_make_iiv_record(settlementPeriod=sp) for sp in range(1, 49)]
    records.append(_make_iiv_record(
        settlementPeriod=1,
        imbalance=999.0,
        publishTime=datetime(2026, 2, 1, 3, 0, tzinfo=timezone.utc),
    ))
    df = create_IIV_dataframe(records, "2026-02-01")
    assert df.loc[1, "imbalance"] == 999.0


def test_iiv_drop_non_target_date():
    records = [_make_iiv_record(settlementPeriod=sp) for sp in range(1, 49)]
    records.append(_make_iiv_record(
        settlementDate=date(2026, 2, 2),
        settlementPeriod=1,
        imbalance=123.0,
    ))
    df = create_IIV_dataframe(records, "2026-02-01")
    assert len(df) == 48
    assert df.loc[1, "imbalance"] == 500.0


def test_iiv_missing_periods_reindexed():
    records = [_make_iiv_record(settlementPeriod=sp) for sp in range(1, 48)]  # SP 48 missing
    df = create_IIV_dataframe(records, "2026-02-01")
    assert len(df) == 48
    assert pd.isna(df.loc[48, "imbalance"])


# merge_dataframes tests

def test_merge_adds_imbalance_column():
    sp_records = [_make_record(settlementPeriod=sp) for sp in range(1, 49)]
    iiv_records = [_make_iiv_record(settlementPeriod=sp, imbalance=float(sp)) for sp in range(1, 49)]
    prices_df = create_system_price_dataframe(sp_records)
    iiv_df = create_IIV_dataframe(iiv_records, "2026-02-01")
    merged = merge_dataframes(prices_df, iiv_df)
    assert len(merged) == 48
    assert "imbalance" in merged.columns
    assert "systemSellPrice" in merged.columns
    assert merged.loc[5, "imbalance"] == 5.0
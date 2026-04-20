import pytest
from pydantic import ValidationError

from src.api.models import SystemPriceRecord


VALID_RESPONSE = {
    "settlementDate": "2024-02-01",
    "settlementPeriod": 1,
    "startTime": "2024-02-01T00:00:00Z",
    "createdDateTime": "2024-02-02T00:44:42Z",
    "systemSellPrice": 39.23,
    "systemBuyPrice": 39.23,
    "bsadDefaulted": False,
    "priceDerivationCode": "N",
    "reserveScarcityPrice": 0,
    "netImbalanceVolume": -65.67288375,
    "sellPriceAdjustment": 0,
    "buyPriceAdjustment": 0,
    "replacementPrice": None,
    "replacementPriceReferenceVolume": None,
    "totalAcceptedOfferVolume": 1152.90211625,
    "totalAcceptedBidVolume": -1248.5666987152779,
    "totalAdjustmentSellVolume": -150,
    "totalAdjustmentBuyVolume": 180,
    "totalSystemTaggedAcceptedOfferVolume": 1152.90211625,
    "totalSystemTaggedAcceptedBidVolume": -1248.5666987152779,
    "totalSystemTaggedAdjustmentSellVolume": -149,
    "totalSystemTaggedAdjustmentBuyVolume": 180
}


def test_system_price_record_accepts_valid():
    rec = SystemPriceRecord.model_validate(VALID_RESPONSE)
    assert rec.settlementPeriod == 1
    assert rec.netImbalanceVolume == -65.67288375

def test_system_price_record_reject_invalid():
    wrong_period = VALID_RESPONSE | {"settlementPeriod": 51}
    missing_field = {k: v for k, v in VALID_RESPONSE.items() if k != "settlementPeriod"}
    with pytest.raises(ValidationError):
        rec_1 = SystemPriceRecord.model_validate(wrong_period)
        rec_2 = SystemPriceRecord.model_validate(missing_field)

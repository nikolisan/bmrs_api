from datetime import date, datetime
from pydantic import BaseModel, ConfigDict, Field


class SystemPriceRecord(BaseModel):
    """Minimal validation model for DISEBSP. Only interesting fields are typed, the rest pass through."""
    model_config = ConfigDict(extra="allow")

    settlementDate: date
    settlementPeriod: int = Field(ge=1, le=50)
    startTime: datetime
    systemSellPrice: float
    systemBuyPrice: float
    netImbalanceVolume: float
    createdDateTime: datetime
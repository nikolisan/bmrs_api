import httpx
from loguru import logger

from src.api.models import SystemPriceRecord


logger.add("api_errors.log", rotation="10 MB", level="WARNING")

class ApiClient:
    """Async BMRS API client"""
    def __init__(
            self,
            client:httpx.AsyncClient,
            timeout_sec: float = 30.0,
            max_attempts: int = 5,
            retry_base: float = 1.0,
            retry_cap: float = 30.0
    ) -> None :
        self.BASE_URL = "https://data.elexon.co.uk/bmrs/api/v1"
        self.RETRY_STATUS = {429, 500, 502, 503, 504}
        self._client: httpx.AsyncClient = client
        self._timeout: float = timeout_sec
        self._max_attempts: int = max_attempts
        self._base: float = retry_base
        self._cap: float = retry_cap
    

    async def fetch_system_prices(self, date: str) -> list[SystemPriceRecord]:
        endpoint = f"/balancing/settlement/system-prices/{date}"
        resp_json = await self._get_with_retry(endpoint, {"format": "json"})
        return [SystemPriceRecord.model_validate(sp) for sp in resp_json.get("data", [])]
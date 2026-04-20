from typing import Any

import httpx
import asyncio
import random
from json import JSONDecodeError
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
    

    async def _get_with_retry(self, endpoint: str, params: dict) -> dict[str, Any]:
        """
        Performs an asynchronous GET request with exponential backoff and rate-limiting retrying.

        Args:
            endpoint: API endpoint to append to the base URL.
            params: Dictionary of query parameters.

        Returns:
            The parsed JSON response body as a dictionary.

        Raises:
            httpx.RequestError: For network-level failures.
            httpx.HTTPStatusError: For non-retryable HTTP error codes.
            RuntimeError: If the maximum number of retry attempts is exceeded.
        """
        url = f"{self.BASE_URL}{endpoint}"
        
        for attempt in range(self._max_attempts):
            delay: float = min(self._cap, self._base * (2 ** (attempt))) + random.random()
            try:
                resp = await self._client.get(url, params=params, timeout=self._timeout)

                if resp.status_code in self.RETRY_STATUS:
                    if resp.status_code == 429:
                        rate_limit_delay = resp.json().get("error", {}).get("retryAfter")
                        if rate_limit_delay:
                            delay = float(rate_limit_delay) + 1

                    logger.warning(f"{endpoint} attempt: {attempt+1}/{self._max_attempts}: Status code: {resp.status_code}, retry in: {delay:.1f} seconds")

                    await asyncio.sleep(delay)
                    continue

                resp.raise_for_status()
                return resp.json()
            
            except httpx.RequestError as err:
                logger.error(f"{endpoint} attempt {attempt+1}/{self._max_attempts}: {type(err).__name__}")
                if attempt < self._max_attempts - 1:
                    await asyncio.sleep(delay)

        raise RuntimeError(
            f"{endpoint}: exhausted {self._max_attempts} attempts"
        )


    async def fetch_system_prices(self, date: str) -> list[SystemPriceRecord]:
        endpoint = f"/balancing/settlement/system-prices/{date}"
        resp_json = await self._get_with_retry(endpoint, {"format": "json"})
        return [SystemPriceRecord.model_validate(sp) for sp in resp_json.get("data", [])]
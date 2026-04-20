import httpx
import pytest
import time
from pydantic import ValidationError
from src.api.client import ApiClient

BASE = "https://data.elexon.co.uk/bmrs/api/v1"


@pytest.fixture
async def client():
    async with httpx.AsyncClient() as client:
        yield ApiClient(client, max_attempts=3, timeout_sec=1.0, retry_base=0.0)


async def test_fetch_system_prices_valid(httpx_mock, client):
    httpx_mock.add_response(
        url=f"{BASE}/balancing/settlement/system-prices/2024-02-01?format=json",
        json={"data": [{
            "settlementDate": "2024-02-01",
            "settlementPeriod": 1,
            "startTime": "2024-02-01T00:00:00Z",
            "systemSellPrice": 50.0,
            "systemBuyPrice": 50.0,
            "netImbalanceVolume": -10.0,
            "createdDateTime": "2024-02-01T00:05:00Z",
        }]},
    )
    response = await client.fetch_system_prices("2024-02-01")
    assert len(response) == 1


# Pydantic validation testing

async def test_fetch_invalid_record_raises_validation_error(httpx_mock, client):
    httpx_mock.add_response(
        url=f"{BASE}/balancing/settlement/system-prices/2024-02-01?format=json",
        json={"data": [{
            "settlementDate": "2024-02-01",
            "settlementPeriod": 99,  # violates ge=1, le=50
            "startTime": "2024-02-01T00:00:00Z",
            "systemSellPrice": 50.0,
            "systemBuyPrice": 50.0,
            "netImbalanceVolume": -10.0,
            "createdDateTime": "2024-02-01T00:05:00Z",
        }]},
    )
    with pytest.raises(ValidationError):
        await client.fetch_system_prices("2024-02-01")


async def test_fetch_invalid_json_raises(httpx_mock, client):
    httpx_mock.add_response(
        url=f"{BASE}/balancing/settlement/system-prices/2024-02-01?format=json",
        content=b"not json",
    )
    with pytest.raises(ValueError):
        await client.fetch_system_prices("2024-02-01")


# Retry testing

async def test_fetch_retries_on_5xx(httpx_mock, client):
    url = f"{BASE}/balancing/settlement/system-prices/2024-02-01?format=json"
    httpx_mock.add_response(url=url, status_code=500)
    httpx_mock.add_response(url=url, status_code=502)
    httpx_mock.add_response(url=url, json={"data": []})
    response = await client.fetch_system_prices("2024-02-01")
    assert response == []


async def test_fetch_exhausts_retries(httpx_mock, client):
    url = f"{BASE}/balancing/settlement/system-prices/2024-02-01?format=json"
    for _ in range(3):
        httpx_mock.add_response(url=url, status_code=503)
    with pytest.raises(RuntimeError):
        await client.fetch_system_prices("2024-02-01")


async def test_fetch_no_retry_on_404(httpx_mock, client):
    httpx_mock.add_response(
        url=f"{BASE}/balancing/settlement/system-prices/2024-02-01?format=json",
        status_code=404,
    )
    with pytest.raises(httpx.HTTPStatusError):
        await client.fetch_system_prices("2024-02-01")

# Rate limiting retry

async def test_fetch_retry_429(httpx_mock, client):
    url = f"{BASE}/balancing/settlement/system-prices/2024-02-01?format=json"
    httpx_mock.add_response(
        url=f"{BASE}/balancing/settlement/system-prices/2024-02-01?format=json",
        status_code=429,
        json = {"error": {"retryAfter": 1}}
    )
    httpx_mock.add_response(url=url, status_code=200, json={"data": []})

    start_time = time.perf_counter()
    response = await client.fetch_system_prices("2024-02-01")
    end_time = time.perf_counter()

    assert (end_time - start_time) >= 2
    assert len(httpx_mock.get_requests()) == 2

# BMRS Daily Imbalance Report

CLI tool that pulls UK electricity balancing data from Elexon BMRS API and produces a per-day imbalance report (metrics + charts).

## Run
Clone the git repository
```bash
git clone https://github.com/nikolisan/bmrs_api.git && cd bmrs_api
```
### Option A — uv

```bash
uv sync
uv run python main.py               # yesterday (Europe/London)
uv run python main.py 2026-02-01    # specific date
uv run python main.py 2026-02-01 --output-dir reports --log-level DEBUG
uv run python main.py --help        # help
```

### Option B — venv + pip

1. Create virtual environment
> Tested with Python >= 3.12
```bash
python -m venv .venv
source .venv/bin/activate
```
2. Install necessary libraries
```bash
pip install .                                   # runtime deps from pyproject.toml
pip install pytest pytest-asyncio pytest-httpx     # for tests
```
3. CLI options to run (ensure venv is activated)
```bash
python main.py                      # yesterday (Europe/London)
python main.py 2026-02-01           # specific date
python main.py 2026-02-01 --output-dir reports --log-level DEBUG
python main.py --help               # help
```

**Outputs go to `reports/<date>/`**:
- `daily_summary.png` — stacked: price, NIV, cumulative cashflow
- `price_correlation.png` — NIV vs System Price scatter

## Tests

```bash
uv run pytest       # uv
pytest              # venv (activated)
```

## Approach

1. **Fetch** — async `httpx` client pulls two endpoints in parallel:
   - `DISEBSP` (system prices / NIV) via `/balancing/settlement/system-prices/{date}`
   - `IMBALNGC` (Indicated Imbalance Volume, IIV) via `/datasets/IMBALNGC`
   Client handles retries (exponential backoff on 5xx, `retryAfter` on 429) and wraps non-JSON responses in `ValueError`.
2. **Validate** — Pydantic v2 models (`SystemPriceRecord`, `ImbalanceRecord`) type the fields that matter. `extra="allow"` lets unknown fields pass through.
3. **Clean / align** — both datasets are deduplicated (keep latest by `createdDateTime` / `publishTime`), indexed by `settlementPeriod`, and reindexed to the expected period count for the day. Missing system-price periods are linearly interpolated and flagged.
4. **Merge** — prices + IIV merged on the `settlementPeriod` index; price columns stay intact, IIV conflicts suffixed `_iiv`.
5. **Metrics** — daily cashflow (BSC Section T 4.7: `CAEIaj = -NIV * SSP`), gross turnover, unit rate, long/short ratios.
6. **Render** — matplotlib figures saved as PNGs.

## Assumptions

- **Total Cashflow sign convention**: BSC Section T 4.7 with NIV assumed aggregated across all accounts.
- **DST days** handled by `zoneinfo` with `ZoneInfo.no_cache`: returns 46 periods on last Sunday of March, 50 on last Sunday of October, 48 otherwise.
- **IIV boundary**: uses records as returned by IMBALNGC; `dataset` and `boundary` columns dropped before merge. National-level boundary assumed `N` in the API response. The aggregated IIV identification from the endpoint is taken on trust without cross-validation against transmission-zone aggregation.
- **Price for cashflow**: uses `systemSellPrice` only. BSC uses SSP for aggregate settlement under the single-price regime.
- **Missing periods**: interpolated linearly for price/NIV; IIV missing left as `NaN` (not interpolated).
- **Too many periods**: raises `ValueError` — treated as data integrity failure rather than silent truncation.
- **Timezone**: default date is "yesterday" in `Europe/London`.

## Project Structure

| Path | Description |
|------|-------------|
| `main.py` | CLI entrypoint. Argparse, logging setup, dispatches `run_daily_report`. |
| `src/report.py` | Orchestrator. Calls seperate modules to: Fetch both endpoints in parallel, cleaning, merging, outputing. |
| `src/api/client.py` | Async BMRS client. Retry/backoff, 429 `retryAfter` handling. Exposes `fetch_system_prices`, `fetch_historical_imbalance`. |
| `src/api/models.py` | Pydantic v2 validation models: `SystemPriceRecord` (DISEBSP), `ImbalanceRecord` (IMBALNGC). |
| `src/data/clean.py` | Response cleaning and storing: `_expected_periods` (DST-aware period count), `create_system_price_dataframe` (dedup + interpolate), `create_IIV_dataframe` (dedup + reindex), `merge_dataframes` (index-only merge). |
| `src/data/metrics.py` | `compute_cashflow` (BSC T 4.7), `compute_daily_metrics` (turnover, unit rate, long/short share, interpolated periods). |
| `src/viz/charts.py` | matplotlib figures |
| `tests/test_client.py` | ApiClient tests |
| `tests/test_clean.py` | Response cleaning and storing tests |
| `tests/test_models.py` | Pydantic model validation tests. |
| `tests/march_bst.json` | Fixture: real API response for March BST day (46 periods). |
| `tests/october_bst.json` | Fixture: real API response for October BST day (50 periods). |
| `pyproject.toml` | uv-managed deps, pytest config (`pythonpath`, async mode). |

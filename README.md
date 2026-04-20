# BMRS Daily Imbalance Report

CLI tool that pulls UK electricity balancing data from Elexon BMRS API and produces a per-day imbalance report (metrics + charts).

## Run
Clone the git repository
```bash
git clone https://github.com/nikolisan/bmrs_api.git && cd bmrs_api
```
### Option A -- uv

```bash
uv sync
uv run python main.py               # yesterday (Europe/London)
uv run python main.py 2026-02-01    # specific date
uv run python main.py 2026-02-01 --output-dir reports --log-level DEBUG
uv run python main.py --help        # help
```

### Option B -- venv + pip

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
`daily_summary.png`
   - 3-panel stack: System Price, NIV with IIV overlay, cumulative imbalance cost
   - Comparison of Price, Volume and Cost on common axis.
   - **Key**: Long/Short system color-coding & price response

`price_correlation.png`: NIV vs System Price scatter
   - Correlation chart of NIV and Price


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
5. **Metrics** — daily imbalance cost (BSC Section T 4.7: `CAEIaj = -NIV * SSP`, summed over all SPs), gross turnover, unit rate (`turnover / Σ|NIV|`), long/short ratios.
6. **Render** — matplotlib figures saved as PNGs.

## Assumptions

- **Total imbalance cost**: defined per BSC Section T 4.7, `CAEIaj = -NIV * SSP` summed across SPs, with NIV assumed aggregated across all accounts. Positive = aggregate parties net receive, negative = net pay.
- **Unit rate**: `Σ(|NIV| * SSP) / Σ|NIV|` — absolute-volume-weighted average price. Reported as NaN when `Σ|NIV| = 0`.
- **DST days** handled by `zoneinfo` with `ZoneInfo.no_cache`: returns 46 periods on last Sunday of March, 50 on last Sunday of October, 48 otherwise.
- **IIV boundary**: IMBALNGC is a **day-ahead forecast** — records with settlementDate D are published on D-1. Client queries the `publishDateTime` window of D-1 and filters on `settlementDate == D` downstream. Boundary hardcoded to `N` (national); `dataset` and `boundary` columns dropped pre-merge. National identification trusted, not cross-validated against zone aggregation.
- **Price for imbalance cost**: uses `systemSellPrice` only (single-price BSC regime).
- **Missing periods**: interpolated linearly for price/NIV and flagged via `is_interpolated`; IIV missing left as `NaN` (no interpolation).
- **Too many periods**: raises `ValueError` — data integrity failure, not silently truncated.
- **Timezone**: default date is "yesterday" in `Europe/London`.

## Scalability

The codebase is structured so each of the four layers can grow independently without rewrites:

- **More data sources** - `ApiClient` concentrates HTTP concerns (retry, backoff, validation); adding a new dataset is one method returning a validated Pydantic list. Parallel fetches in `run_daily_report` use `asyncio.gather` and scale to N endpoints by adding tasks.

- **More metrics** - `src/data/metrics.py` is a module of pure functions over a `DataFrame`. New metrics plug into `compute_daily_metrics`. More metric functions can be introduced.

- **More visualisations** - `src/viz/charts.py` returns `Figure` objects decoupled from IO.

- **Multi-day** - `run_daily_report` takes a single date. A multi-day runner can wrap it in `asyncio.gather` over a date range.

- **Storage** - currently writes PNGs to disk. Metrics return a plain dict → easy swap to Parquet/CSV append or a DB table for historical analytics.

- **Reporting** - currently handled by producing graphs and `stdout` messages. The module can be extended to an interactive dashboard or automatic pdf report generation.

## Project Structure

| Path | Description |
|------|-------------|
| `main.py` | CLI entrypoint. Argparse, logging setup, dispatches `run_daily_report`. |
| `src/report.py` | Orchestrator. Calls seperate modules to: Fetch both endpoints in parallel, cleaning, merging, outputing. |
| `src/api/client.py` | Async BMRS client. Retry/backoff, 429 `retryAfter` handling. Exposes `fetch_system_prices`, `fetch_historical_imbalance`. |
| `src/api/models.py` | Pydantic v2 validation models: `SystemPriceRecord` (DISEBSP), `ImbalanceRecord` (IMBALNGC). |
| `src/data/clean.py` | Response cleaning and storing: `_expected_periods` (DST-aware period count), `create_system_price_dataframe` (dedup + interpolate), `create_IIV_dataframe` (dedup + reindex), `merge_dataframes` (index-only merge). |
| `src/data/metrics.py` | `compute_imbalance_cost` (BSC T 4.7), `compute_daily_metrics` (turnover, unit rate, long/short share, interpolated periods). |
| `src/viz/charts.py` | matplotlib figures |
| `tests/test_client.py` | ApiClient tests |
| `tests/test_clean.py` | Response cleaning and storing tests |
| `tests/test_metrics.py` | Imbalance cost / unit rate / long-short calculation tests. |
| `tests/test_models.py` | Pydantic model validation tests. |
| `tests/march_bst.json` | Fixture: real API response for March BST day (46 periods). |
| `tests/october_bst.json` | Fixture: real API response for October BST day (50 periods). |
| `pyproject.toml` | uv-managed deps, pytest config (`pythonpath`, async mode). |

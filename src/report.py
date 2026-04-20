import asyncio
from datetime import date
from pathlib import Path
from typing import Any

import httpx
import matplotlib.pyplot as plt
from loguru import logger

from src.api.client import ApiClient
from src.data.clean import create_system_price_dataframe, create_IIV_dataframe, merge_dataframes
from src.data.metrics import compute_daily_metrics
from src.viz.charts import build_report_figure, build_price_scatter


def print_stdout_summary(metrics: dict[str, Any], out_path: Path) -> None:
    print(f"=== Imbalance Report — {metrics['settlement_date']} ===")
    print(f"Imbalance cost       : £{metrics['total_imbalance_cost']:,.2f}")
    print(f"Absolute turnover    : £{metrics['total_turnover']:,.2f}")
    print(f"Unit rate            : £{metrics['unit_rate_gbp_per_mwh']:,.2f}/MWh")
    print(f"Periods long / short : {metrics['pct_periods_long']:.1f}% / {metrics['pct_periods_short']:.1f}%")
    print(f"Settlement periods   : {metrics['total_periods']}")
    print(f"Periods interpolated : {metrics['periods_interpolated']}")
    print(f"Wrote                : {out_path}")



async def run_daily_report(settlement_date: str, output_dir: Path = Path("reports")) -> Path:
    """
    Fetches, cleans, merges, and renders the daily imbalance report for a settlement date.

    Args:
        settlement_date: Target day in 'YYYY-MM-DD' format.
        output_dir: Root directory for report outputs. PNGs written to '<output_dir>/<settlement_date>/'.

    Returns:
        Path to the output directory containing the generated PNGs.
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    async with httpx.AsyncClient() as http:
        client = ApiClient(http)
        sp_task = asyncio.create_task(client.fetch_system_prices(settlement_date))
        iiv_task = asyncio.create_task(client.fetch_historical_imbalance(settlement_date))
        sp_records, iiv_records = await asyncio.gather(sp_task, iiv_task)

    prices_df = create_system_price_dataframe(sp_records)
    iiv_df = create_IIV_dataframe(iiv_records, settlement_date)
    df = merge_dataframes(prices_df, iiv_df)

    metrics = compute_daily_metrics(df, settlement_date)

    main_fig = build_report_figure(df, metrics)
    scatter_fig = build_price_scatter(df)

    out = output_dir / settlement_date
    out.mkdir(parents=True, exist_ok=True)

    # Exporting as PNG
    main_png_path = out / "daily_summary.png"
    scatter_png_path = out /  "price_correlation.png"

    main_fig.savefig(main_png_path, dpi=150, bbox_inches="tight")
    scatter_fig.savefig(scatter_png_path, dpi=150, bbox_inches="tight")
    plt.close(main_fig)
    plt.close(scatter_fig)

    print_stdout_summary(metrics, out)
    return out
import argparse
import asyncio
import sys
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from loguru import logger

from src.report import run_daily_report


def main(argv: list[str] | None = None) -> int:
    default_date = (
        datetime.now(ZoneInfo("Europe/London")) - timedelta(days=1)
    ).date().isoformat()
    p = argparse.ArgumentParser(prog="exercise", description="BMRS daily imbalance report")

    p.add_argument("date", nargs="?", default=default_date, help="Settlement date YYYY-MM-DD (default: yesterday)")
    p.add_argument("--output-dir", type=Path, default=Path("reports"))
    p.add_argument("--log-level", default="INFO", choices=["DEBUG", "INFO", "WARNING", "ERROR"])

    args = p.parse_args(argv)

    logger.remove()
    logger.add("api_errors.log", rotation="10 MB", level=args.log_level)
    logger.add(sys.stderr, level=args.log_level)

    try:
        asyncio.run(run_daily_report(args.date, args.output_dir))
        return 0
    except Exception as e:
        logger.exception(f"report failed: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
"""Step 1 - Download ~5 years of daily OHLCV data for Nifty 50 stocks and the index.

Output: data/raw/prices_raw.csv and data/raw/nifty50_index_raw.csv
Run:    python src/01_download_data.py
"""
import logging
from datetime import date, timedelta

import pandas as pd
import yfinance as yf

from config import INDEX_TICKER, RAW_DIR, STOCKS, YEARS_OF_HISTORY

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
log = logging.getLogger(__name__)


def fetch(ticker: str, start: date, end: date, retries: int = 2):
    """Download one ticker (split/dividend adjusted). Returns None if no data."""
    for attempt in range(1, retries + 1):
        try:
            df = yf.download(ticker, start=start, end=end, auto_adjust=True, progress=False)
        except Exception as exc:  # network / API hiccup
            log.warning("%s attempt %d failed: %s", ticker, attempt, exc)
            continue
        if df is not None and not df.empty:
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)
            df = df.reset_index()
            df.columns = [str(c).lower() for c in df.columns]
            df["ticker"] = ticker
            return df[["date", "ticker", "open", "high", "low", "close", "volume"]]
    return None


def main():
    end = date.today() + timedelta(days=1)
    start = end - timedelta(days=int(365.25 * YEARS_OF_HISTORY))
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    log.info("Downloading %d stocks from %s to %s", len(STOCKS), start, end)

    frames, failed = [], []
    for ticker in STOCKS:
        df = fetch(ticker, start, end)
        if df is None:
            failed.append(ticker)
            log.warning("No data for %s - skipped", ticker)
        else:
            frames.append(df)
            log.info("%-14s %5d rows", ticker, len(df))

    if not frames:
        raise SystemExit("No data downloaded. Check your internet connection.")

    prices = pd.concat(frames, ignore_index=True)
    prices.to_csv(RAW_DIR / "prices_raw.csv", index=False)

    index = fetch(INDEX_TICKER, start, end)
    if index is not None:
        index.to_csv(RAW_DIR / "nifty50_index_raw.csv", index=False)
    else:
        log.warning("Could not download the Nifty 50 index; beta will be skipped")

    log.info("Saved %d rows for %d stocks", len(prices), prices["ticker"].nunique())
    if failed:
        log.warning("Tickers with no data (check symbol / delisting / rename): %s", failed)


if __name__ == "__main__":
    main()

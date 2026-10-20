"""Step 2 - Clean the raw prices, run data-quality checks and load them into MySQL.

Output: tables in the nifty50_analysis database + data/processed/data_quality_report.csv
Run:    python src/02_clean_and_load.py

Set DB_URL to use another database. SQLite works for a quick trial:
    DB_URL=sqlite:///nifty.sqlite python src/02_clean_and_load.py
"""
import logging

import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

from config import DB_NAME, DB_URL, MANUAL_ADJUSTMENTS, PROCESSED_DIR, RAW_DIR, SQL_DIR, STOCKS

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
log = logging.getLogger(__name__)

PRICE_COLS = ["open", "high", "low", "close"]


def clean_prices(df: pd.DataFrame, report: list, label: str) -> pd.DataFrame:
    """Apply cleaning rules and record how many rows each rule touched."""
    df = df.copy()
    df["date"] = pd.to_datetime(df["date"], utc=True, errors="coerce").dt.tz_localize(None).dt.normalize()
    start_rows = len(df)

    def record(check, n, action):
        report.append({"dataset": label, "check": check, "rows_affected": int(n), "action": action})

    n = df["date"].isna().sum()
    record("unparseable dates", n, "dropped")
    df = df.dropna(subset=["date"])

    n = df[PRICE_COLS].isna().any(axis=1).sum()
    record("missing OHLC values", n, "dropped")
    df = df.dropna(subset=PRICE_COLS)

    n = (df[PRICE_COLS] <= 0).any(axis=1).sum()
    record("non-positive prices", n, "dropped")
    df = df[(df[PRICE_COLS] > 0).all(axis=1)]

    n = (df["high"] < df["low"]).sum()
    record("high < low (inconsistent candle)", n, "dropped")
    df = df[df["high"] >= df["low"]]

    key = ["date", "ticker"] if "ticker" in df.columns else ["date"]
    n = df.duplicated(subset=key).sum()
    record("duplicate date/ticker rows", n, "dropped (kept first)")
    df = df.drop_duplicates(subset=key, keep="first")

    if label == "stocks":  # an index has no traded volume, so skip this check for it
        n = (df["volume"].fillna(0) == 0).sum()
        record("zero-volume rows", n, "kept, flagged only")
    df["volume"] = df["volume"].fillna(0).astype("int64")

    df = df.sort_values(key).reset_index(drop=True)
    if label == "stocks":
        for tkr, (event_date, factor, note) in MANUAL_ADJUSTMENTS.items():
            mask = (df["ticker"] == tkr) & (df["date"] < pd.Timestamp(event_date))
            df.loc[mask, PRICE_COLS] = df.loc[mask, PRICE_COLS] * factor
            record(f"manual adjustment {tkr}: {note}", mask.sum(), f"prices before {event_date} x {factor:.4f}")    
    grp = df.groupby("ticker")["close"] if "ticker" in df.columns else df["close"]
    df["daily_return"] = grp.pct_change()

    n = (df["daily_return"].abs() > 0.25).sum()
    record("daily move > 25% (possible corporate action)", n, "kept, flagged only")
    record("rows in -> rows out", start_rows, f"{len(df)} rows loaded")
    return df


def build_dimensions():
    sectors = sorted({s for _, s in STOCKS.values()})
    dim_sector = pd.DataFrame({"sector_id": range(1, len(sectors) + 1), "sector_name": sectors})
    sector_id = dict(zip(dim_sector["sector_name"], dim_sector["sector_id"]))
    dim_stock = pd.DataFrame(
        [(t, name, sector_id[sec]) for t, (name, sec) in STOCKS.items()],
        columns=["ticker", "company_name", "sector_id"],
    )
    return dim_sector, dim_stock


def get_engine():
    url = make_url(DB_URL)
    if url.get_backend_name() == "sqlite":
        return create_engine(url), False
    # Create the database first if it doesn't exist yet (MySQL/MariaDB)
    server_engine = create_engine(url.set(database="mysql"))  # built-in system DB
    with server_engine.begin() as conn:
        conn.execute(text(f"CREATE DATABASE IF NOT EXISTS {DB_NAME}"))
    return create_engine(url), True


def run_schema(engine):
    """Execute sql/schema.sql statement by statement."""
    script = (SQL_DIR / "schema.sql").read_text()
    script = "\n".join(l for l in script.splitlines() if not l.strip().startswith("--"))
    with engine.begin() as conn:
        for stmt in filter(None, (s.strip() for s in script.split(";"))):
            if stmt.upper().startswith(("CREATE DATABASE", "USE ")):
                continue
            conn.execute(text(stmt))


def main():
    raw_path = RAW_DIR / "prices_raw.csv"
    if not raw_path.exists():
        raise SystemExit("data/raw/prices_raw.csv not found. Run src/01_download_data.py first.")

    report: list = []
    prices = clean_prices(pd.read_csv(raw_path), report, "stocks")
    prices = prices[prices["ticker"].isin(STOCKS)]

    index_path = RAW_DIR / "nifty50_index_raw.csv"
    index = None
    if index_path.exists():
        index = clean_prices(pd.read_csv(index_path).assign(ticker="^NSEI"), report, "nifty50 index")

    dim_sector, dim_stock = build_dimensions()
    dim_stock = dim_stock[dim_stock["ticker"].isin(prices["ticker"].unique())]

    fact = prices.rename(columns={
        "date": "trade_date", "open": "open_price", "high": "high_price",
        "low": "low_price", "close": "close_price"})[
        ["trade_date", "ticker", "open_price", "high_price", "low_price", "close_price", "volume", "daily_return"]]

    engine, is_server = get_engine()
    if is_server:
        run_schema(engine)
        mode = "append"
    else:
        mode = "replace"

    kw = dict(if_exists=mode, index=False, chunksize=5000)
    if is_server:
        kw["method"] = "multi"
    dim_sector.to_sql("dim_sector", engine, **kw)
    dim_stock.to_sql("dim_stock", engine, **kw)
    fact.to_sql("fact_daily_prices", engine, **kw)
    if index is not None:
        idx = index.rename(columns={"date": "trade_date", "close": "close_price"})[
            ["trade_date", "close_price", "daily_return"]]
        idx.to_sql("fact_index_prices", engine, **kw)

    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(report).to_csv(PROCESSED_DIR / "data_quality_report.csv", index=False)
    log.info("Loaded %d price rows for %d stocks. Quality report saved.", len(fact), fact["ticker"].nunique())
    print(pd.DataFrame(report).to_string(index=False))


if __name__ == "__main__":
    main()

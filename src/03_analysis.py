"""Step 3 - Risk/return analytics, charts, Power BI exports and auto-generated findings.

Reads the tables created by 02_clean_and_load.py and produces:
  data/processed/*.csv          (feed these to Power BI)
  dashboard/charts/*.png        (charts for the README)
  docs/key_findings.md          (numbers pulled from the data - never typed by hand)
Run: python src/03_analysis.py
"""
import logging

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sqlalchemy import create_engine

from config import (CHART_DIR, DB_URL, DOCS_DIR, MIN_OBSERVATIONS, PROCESSED_DIR,
                    RISK_FREE_RATE, TRADING_DAYS)

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
log = logging.getLogger(__name__)
plt.rcParams.update({"figure.dpi": 130, "axes.spines.top": False, "axes.spines.right": False})


def load_data(engine):
    meta = pd.read_sql(
        "SELECT s.ticker, s.company_name, sec.sector_name "
        "FROM dim_stock s JOIN dim_sector sec ON sec.sector_id = s.sector_id", engine)
    px = pd.read_sql("SELECT trade_date, ticker, close_price, daily_return FROM fact_daily_prices",
                     engine, parse_dates=["trade_date"])
    try:
        idx = pd.read_sql("SELECT trade_date, daily_return FROM fact_index_prices", engine,
                          parse_dates=["trade_date"]).set_index("trade_date")["daily_return"].astype(float)
    except Exception:
        idx = None
    px["close_price"] = px["close_price"].astype(float)
    px["daily_return"] = px["daily_return"].astype(float)
    return meta, px, idx


def stock_metrics(meta, close, rets, idx):
    rows = []
    for t in rets.columns:
        r = rets[t].dropna()
        if len(r) < MIN_OBSERVATIONS:
            log.info("Skipping %s (only %d return observations)", t, len(r))
            continue
        c = close[t].dropna()
        years = (c.index[-1] - c.index[0]).days / 365.25
        total = c.iloc[-1] / c.iloc[0] - 1
        vol = r.std() * np.sqrt(TRADING_DAYS)
        ann_ret = r.mean() * TRADING_DAYS
        beta = np.nan
        if idx is not None:
            both = pd.concat([r, idx], axis=1, join="inner").dropna()
            both.columns = ["s", "m"]
            if len(both) > 60 and both["m"].var() > 0:
                beta = both["s"].cov(both["m"]) / both["m"].var()
        rows.append({
            "ticker": t, "total_return_pct": total * 100,
            "cagr_pct": ((1 + total) ** (1 / years) - 1) * 100,
            "ann_volatility_pct": vol * 100,
            "sharpe_ratio": (ann_ret - RISK_FREE_RATE) / vol,
            "max_drawdown_pct": (c / c.cummax() - 1).min() * 100,
            "beta_vs_nifty": beta,
        })
    return meta.merge(pd.DataFrame(rows), on="ticker")


def monthly_compound(df):
    return df.groupby(df.index.to_period("M")).apply(lambda x: (1 + x.fillna(0)).prod() - 1)


def save_charts(sm, sector_ret, sector_stats, corr):
    CHART_DIR.mkdir(parents=True, exist_ok=True)
    cmap = plt.get_cmap("tab20")
    sectors = sorted(sm["sector_name"].unique())
    order = list(range(0, 20, 2)) + list(range(1, 20, 2))  # strong colours first
    colors = {s: cmap(order[i % 20]) for i, s in enumerate(sectors)}

    # 1. Sector cumulative performance rebased to 100
    cum = (1 + sector_ret.fillna(0)).cumprod() * 100
    fig, ax = plt.subplots(figsize=(10, 5.5))
    for s in cum.columns:
        ax.plot(cum.index, cum[s], label=s, color=colors[s], lw=1.6)
    ax.set_title("Sector performance (equal-weighted, rebased to 100)", loc="left", fontweight="bold")
    ax.legend(ncol=2, fontsize=7, frameon=False, loc="upper left")
    ax.grid(alpha=0.2)
    fig.tight_layout(); fig.savefig(CHART_DIR / "01_sector_performance.png"); plt.close(fig)

    # 2. Risk vs return scatter
    fig, ax = plt.subplots(figsize=(10, 6))
    for s in sectors:
        d = sm[sm["sector_name"] == s]
        ax.scatter(d["ann_volatility_pct"], d["cagr_pct"], s=40, alpha=0.8, color=colors[s], label=s)
    for _, r in sm.nlargest(3, "cagr_pct").iterrows():
        ax.annotate(r["company_name"], (r["ann_volatility_pct"], r["cagr_pct"]), fontsize=7, xytext=(4, 4),
                    textcoords="offset points")
    for _, r in sm.nsmallest(3, "cagr_pct").iterrows():
        ax.annotate(r["company_name"], (r["ann_volatility_pct"], r["cagr_pct"]), fontsize=7, xytext=(4, -9),
                    textcoords="offset points")
    ax.axhline(0, color="grey", lw=0.8)
    ax.set_xlabel("Annualised volatility (%)"); ax.set_ylabel("CAGR (%)")
    ax.set_title("Risk vs return: Nifty 50 stocks", loc="left", fontweight="bold")
    ax.legend(fontsize=7, ncol=2, frameon=False)
    ax.grid(alpha=0.2)
    fig.tight_layout(); fig.savefig(CHART_DIR / "02_risk_return_scatter.png"); plt.close(fig)

    # 3. Sector correlation heatmap
    fig, ax = plt.subplots(figsize=(8, 6.5))
    im = ax.imshow(corr.values, cmap="RdYlGn_r", vmin=0, vmax=1)
    ax.set_xticks(range(len(corr))); ax.set_xticklabels(corr.columns, rotation=60, ha="right", fontsize=8)
    ax.set_yticks(range(len(corr))); ax.set_yticklabels(corr.index, fontsize=8)
    for i in range(len(corr)):
        for j in range(len(corr)):
            ax.text(j, i, f"{corr.values[i, j]:.2f}", ha="center", va="center", fontsize=6.5)
    ax.set_title("Sector return correlation (daily)", loc="left", fontweight="bold")
    fig.colorbar(im, shrink=0.8)
    fig.tight_layout(); fig.savefig(CHART_DIR / "03_sector_correlation.png"); plt.close(fig)

    # 4. Sector Sharpe ratio ranking
    fig, ax = plt.subplots(figsize=(8, 5))
    d = sector_stats.sort_values("avg_sharpe")
    ax.barh(d["sector_name"], d["avg_sharpe"], color=[colors[s] for s in d["sector_name"]])
    ax.axvline(0, color="grey", lw=0.8)
    ax.set_title("Average Sharpe ratio by sector", loc="left", fontweight="bold")
    ax.grid(axis="x", alpha=0.2)
    fig.tight_layout(); fig.savefig(CHART_DIR / "04_sector_sharpe.png"); plt.close(fig)


def write_findings(sm, sector_stats, corr, period):
    robust = sector_stats[sector_stats["stocks"] >= 3]   # avoid headlines based on 1-2 stocks
    best_cagr = robust.loc[robust["avg_cagr_pct"].idxmax()]
    low_vol = robust.loc[robust["avg_volatility_pct"].idxmin()]
    high_vol = robust.loc[robust["avg_volatility_pct"].idxmax()]
    best_sharpe = robust.loc[robust["avg_sharpe"].idxmax()]
    worst_sharpe = robust.loc[robust["avg_sharpe"].idxmin()]

    pairs = corr.where(np.triu(np.ones(corr.shape), k=1).astype(bool)).stack().dropna().sort_values()
    lo, hi = pairs.index[0], pairs.index[-1]
    top = sm.nlargest(3, "sharpe_ratio")
    dd = sm.nsmallest(1, "max_drawdown_pct").iloc[0]
    hb = sm.dropna(subset=["beta_vs_nifty"]).nlargest(3, "beta_vs_nifty")
    lb = sm.dropna(subset=["beta_vs_nifty"]).nsmallest(3, "beta_vs_nifty")

    lines = [
        "# Key findings (auto-generated from the data)", "",
        f"Period analysed: **{period}** | Stocks analysed: **{len(sm)}** | "
        f"Sectors: **{sector_stats.shape[0]}** | Risk-free rate: {RISK_FREE_RATE:.1%}", "",
        "> Sector figures are simple averages of the stocks in each sector. "
        "Treat sectors with 1-2 stocks with caution.", "",
        "## Sector highlights (sectors with 3+ stocks)",
        f"- **Highest average CAGR:** {best_cagr['sector_name']} ({best_cagr['avg_cagr_pct']:.1f}% p.a.)",
        f"- **Best risk-adjusted return (Sharpe):** {best_sharpe['sector_name']} ({best_sharpe['avg_sharpe']:.2f})",
        f"- **Weakest risk-adjusted return:** {worst_sharpe['sector_name']} ({worst_sharpe['avg_sharpe']:.2f})",
        f"- **Least volatile sector:** {low_vol['sector_name']} ({low_vol['avg_volatility_pct']:.1f}% annualised)",
        f"- **Most volatile sector:** {high_vol['sector_name']} ({high_vol['avg_volatility_pct']:.1f}% annualised)",
        f"- **Most correlated sector pair:** {hi[0]} & {hi[1]} ({pairs.iloc[-1]:.2f})",
        f"- **Best diversifying pair (lowest correlation):** {lo[0]} & {lo[1]} ({pairs.iloc[0]:.2f})", "",
        "## Stock highlights",
        "- **Top 3 by Sharpe ratio:** " + ", ".join(f"{r.company_name} ({r.sharpe_ratio:.2f})" for r in top.itertuples()),
        f"- **Deepest drawdown:** {dd['company_name']} ({dd['max_drawdown_pct']:.1f}%)",
    ]
    if len(hb):
        lines += [
            "- **Highest beta (amplify Nifty moves):** " + ", ".join(f"{r.company_name} ({r.beta_vs_nifty:.2f})" for r in hb.itertuples()),
            "- **Lowest beta (defensive):** " + ", ".join(f"{r.company_name} ({r.beta_vs_nifty:.2f})" for r in lb.itertuples()),
        ]
    lines += ["", "## Sector scorecard", "", sector_stats.round(2).to_markdown(index=False), ""]
    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    (DOCS_DIR / "key_findings.md").write_text("\n".join(lines), encoding="utf-8")


def main():
    engine = create_engine(DB_URL)
    meta, px, idx = load_data(engine)
    close = px.pivot(index="trade_date", columns="ticker", values="close_price").sort_index()
    rets = px.pivot(index="trade_date", columns="ticker", values="daily_return").sort_index()

    sm = stock_metrics(meta, close, rets, idx)
    sector_of = meta.set_index("ticker")["sector_name"].to_dict()
    kept = sm["ticker"].tolist()

    sector_ret = rets[kept].T.groupby(lambda t: sector_of[t]).mean().T
    corr = sector_ret.corr()
    sector_stats = (sm.groupby("sector_name")
                    .agg(stocks=("ticker", "count"),
                         avg_cagr_pct=("cagr_pct", "mean"),
                         avg_volatility_pct=("ann_volatility_pct", "mean"),
                         avg_sharpe=("sharpe_ratio", "mean"),
                         avg_max_drawdown_pct=("max_drawdown_pct", "mean"),
                         avg_beta=("beta_vs_nifty", "mean"))
                    .reset_index().sort_values("avg_sharpe", ascending=False))

    # Exports for Power BI
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    sm.round(4).to_csv(PROCESSED_DIR / "stock_metrics.csv", index=False)
    sector_stats.round(4).to_csv(PROCESSED_DIR / "sector_metrics.csv", index=False)
    corr.round(4).reset_index().rename(columns={"index": "sector"}).to_csv(
        PROCESSED_DIR / "sector_correlation.csv", index=False)
    monthly = monthly_compound(sector_ret)
    monthly.index = monthly.index.astype(str)
    (monthly.reset_index().rename(columns={"trade_date": "month", "index": "month"})
        .melt(id_vars="month", var_name="sector_name", value_name="monthly_return")
        .round(6).to_csv(PROCESSED_DIR / "sector_monthly_returns.csv", index=False))
    cum = (1 + sector_ret.fillna(0)).cumprod() * 100
    (cum.reset_index().melt(id_vars="trade_date", var_name="sector_name", value_name="index_value")
        .round({"index_value": 4}).to_csv(PROCESSED_DIR / "sector_cumulative.csv", index=False))
    roll = sector_ret.rolling(30).std() * np.sqrt(TRADING_DAYS) * 100
    (roll.dropna(how="all").reset_index().melt(id_vars="trade_date", var_name="sector_name",
                                                value_name="rolling_vol_30d_pct")
        .dropna().round({"rolling_vol_30d_pct": 4}).to_csv(PROCESSED_DIR / "sector_rolling_volatility.csv", index=False))

    save_charts(sm, sector_ret, sector_stats, corr)
    period = f"{close.index.min():%d %b %Y} to {close.index.max():%d %b %Y}"
    write_findings(sm, sector_stats, corr, period)
    log.info("Done. Outputs in data/processed, dashboard/charts, docs/key_findings.md")


if __name__ == "__main__":
    main()

# Nifty 50 Sector Performance & Risk Analysis

An end-to-end analytics project on five years of NSE data: **Python** for ingestion, cleaning and validation, **MySQL** for storage and analysis (window functions, CTEs), and **Power BI** for an interactive dashboard.

**The question:** Which sectors of the Indian market delivered the best returns *for the risk taken*, and how can an investor diversify across them?

## Dashboard
![Market overview](dashboard/screenshots/page1_overview.png)
![Risk vs return](dashboard/screenshots/page2_risk_return.png)
![Sector deep dive](dashboard/screenshots/page3_sector_deep_dive.png)

## Highlights
- Analysed **50 Nifty 50 stocks across 16 sectors** over **~5 years (Oct 2021 - Oct 2026)**, about 61,000 daily price records.
- Built a **star-schema MySQL database** and **8 analytical SQL queries** (rolling volatility, drawdown, ranking, month-wise seasonality).
- Computed **CAGR, annualised volatility, Sharpe ratio, maximum drawdown and beta** for every stock and sector.
- Found and fixed **real data-quality problems**, including a corporate-action distortion and a data-feed error (see [Data issues found](#data-issues-found-and-how-they-were-handled)).
- Delivered a Power BI dashboard on risk vs. return, sector correlation and rolling volatility.

## Key findings
*(Oct 2021 - Oct 2026; sector rankings use sectors with 3 or more stocks. Full scorecard in [`docs/key_findings.md`](docs/key_findings.md).)*

1. **Infrastructure led on both return and risk-adjusted return** (24.9% average CAGR, Sharpe 0.67), helped by Bharat Electronics, the highest-Sharpe stock in the index (1.07). It also carried above-market risk (beta 1.30, volatility 30.8%).
2. **IT and FMCG failed to compensate investors for risk.** IT averaged -1.3% CAGR (Sharpe -0.20) and FMCG 2.2% (Sharpe -0.11), both below the 6.5% risk-free rate used.
3. **Banking lagged:** 8.2% average CAGR and Sharpe 0.17, against 24.9% for Infrastructure, despite being one of the Nifty's heaviest sectors.
4. **Pharma was the most defensive sector:** beta 0.51 and the shallowest average drawdown (-23.9%) among sectors with 3+ stocks. Cipla (beta 0.43) was the least market-sensitive stock.
5. **Diversification:** Banking and Financial Services moved together (correlation 0.69), so holding both adds little diversification. IT and Power & Energy had the lowest correlation (0.19).
6. **Tail risk is concentrated in a few names:** Adani Enterprises (volatility 48%, beta 1.72, drawdown -71%) and Eternal (drawdown -74%).

### Charts
| | |
|---|---|
| ![Sector performance](dashboard/charts/01_sector_performance.png) | ![Risk vs return](dashboard/charts/02_risk_return_scatter.png) |
| ![Sector correlation](dashboard/charts/03_sector_correlation.png) | ![Sector Sharpe](dashboard/charts/04_sector_sharpe.png) |

## Tech stack
| Layer | Tools |
|---|---|
| Ingestion | Python, `yfinance` (NSE daily prices, split/dividend adjusted) |
| Cleaning & validation | pandas (data-quality report on every run) |
| Storage & analysis | MySQL 8, star-schema design, window functions |
| Analytics | pandas, NumPy (Sharpe, beta, drawdown, correlation) |
| Visualisation | Power BI, matplotlib |

## Pipeline
```
yfinance  ->  01_download_data.py  ->  data/raw/*.csv
                                         |
                       02_clean_and_load.py  (validation, corporate-action
                                         |    adjustments, quality report)
                                MySQL: dim_sector, dim_stock,
                                       fact_daily_prices, fact_index_prices
                                         |
              sql/analysis_queries.sql   +   03_analysis.py
                                         |
              data/processed/*.csv  ->  Power BI dashboard
              dashboard/charts/*.png, docs/key_findings.md
```

## Database design
| Table | Grain | Key columns |
|---|---|---|
| `dim_sector` | one row per sector | `sector_id`, `sector_name` |
| `dim_stock` | one row per stock | `ticker`, `company_name`, `sector_id` |
| `fact_daily_prices` | stock x trading day | OHLC, `volume`, `daily_return` |
| `fact_index_prices` | trading day | Nifty 50 close, `daily_return` |

## SQL analysis ([`sql/analysis_queries.sql`](sql/analysis_queries.sql))
| # | Question answered | Techniques |
|---|---|---|
| Q1 | Data coverage per stock | aggregation, joins |
| Q2 | Total return since start | `ROW_NUMBER`, conditional aggregation |
| Q3 | Sector risk-adjusted ranking | `STDDEV_SAMP`, `RANK` |
| Q4 | Monthly returns per stock | CTEs, `LAG` |
| Q5 | Top 10 / bottom 10 over 12 months | date filtering, dual `RANK` |
| Q6 | 30-day rolling volatility | rolling window frame |
| Q7 | Maximum drawdown | running `MAX` window |
| Q8 | Best/worst calendar month per sector | multi-CTE pivot |

## Metrics
| Metric | Definition |
|---|---|
| CAGR | `(last close / first close)^(1/years) - 1` |
| Annualised volatility | `std(daily returns) x sqrt(252)` |
| Sharpe ratio | `(mean daily return x 252 - risk-free rate) / annualised volatility` (risk-free = 6.5%, editable in `src/config.py`) |
| Max drawdown | largest peak-to-trough fall of the closing price |
| Beta | `cov(stock, Nifty 50) / var(Nifty 50)` on daily returns |
| Sector figures | equal-weighted average of the sector's stocks |

## Data quality
Every run writes `data/processed/data_quality_report.csv` with the number of rows affected by each rule: missing OHLC values, non-positive prices, `high < low`, duplicate rows, zero-volume days, daily moves above 25% (possible corporate actions) and any manual price adjustments.

### Data issues found and how they were handled
| Issue | Treatment |
|---|---|
| **TMPV (Tata Motors Passenger Vehicles):** the Oct 2025 demerger of the commercial-vehicle business shows as a false -40% one-day drop | Prices before 14 Oct 2025 scaled by 400 / 660.75 (NSE reference price vs prior close) |
| **TRENT:** the Yahoo feed shows a permanent ~-33% level shift on 1 Jan 2026 that is absent from exchange-reported prices (₹4,417 close on 5 Jan, ₹4,055 on 6 Jan) | Prices before 1 Jan 2026 scaled by 2/3 after cross-checking against reported closes; day-to-day returns after the shift matched reported moves |
| **ADANIENT / ADANIPORTS, Jan-Feb 2023:** daily moves of -16% to -28% | Genuine (Hindenburg report); kept as real tail-risk events |
| **19 daily moves above 15% reviewed** | Clusters across related stocks tie to market events (the 2023 Adani selloff, the 4 Jun 2024 election-result day). Isolated moves were checked against news and kept as genuine: Eternal -19.6% on 24 Jan 2022 (global sell-off in loss-making new-age stocks), Eternal +20% on 2 Aug 2022 (upper-circuit rally after Q1 FY23 loss narrowed), Trent +~19% on 7 Feb 2024 (Q3 FY24 profit more than doubled) |

All adjustments are declared in `MANUAL_ADJUSTMENTS` in `src/config.py` and logged in the quality report. If the data source later corrects the Trent feed, remove its entry.

## How to run
**Requirements:** Python 3.9+, MySQL 8 running locally, Power BI Desktop (optional, for the dashboard).
To open the dashboard, update the data source path in Power BI (Transform data > Data source settings) to your local `data/processed/` folder.

```bash
git clone https://github.com/<your-username>/nifty50-sector-analysis.git
cd nifty50-sector-analysis
pip install -r requirements.txt

# Point the project at your MySQL server (see .env.example)
# Windows PowerShell:  $env:DB_URL="mysql+pymysql://root:YOUR_PASSWORD@localhost:3306/nifty50_analysis"
# macOS/Linux:         export DB_URL="mysql+pymysql://root:YOUR_PASSWORD@localhost:3306/nifty50_analysis"
# Note: write special characters in the password URL-encoded (e.g. @ as %40)

python src/01_download_data.py     # ~1-3 minutes
python src/02_clean_and_load.py    # creates the database and tables
python src/03_analysis.py          # metrics, charts, CSVs for Power BI
```
Then run `sql/analysis_queries.sql` in MySQL Workbench and follow [`dashboard/POWERBI_GUIDE.md`](dashboard/POWERBI_GUIDE.md).

## Project structure
```
nifty50-sector-analysis/
├── src/            config, download, clean+load, analysis
├── sql/            schema.sql, analysis_queries.sql
├── data/           raw/ (git-ignored) and processed/ (Power BI inputs)
├── dashboard/      charts/, screenshots/, POWERBI_GUIDE.md
├── docs/           key_findings.md (auto-generated)
└── requirements.txt
```

## Limitations
- **Survivorship bias:** the current index constituents are analysed over the whole period, so stocks that left the index are not included.
- **Start-date sensitivity:** results depend on the window chosen. Oct 2021 was near a market peak for some sectors, and a different start date would change the ranking.
- **Sector averages are not sector portfolios:** sector metrics are simple averages of individual stock metrics, which overstates sector risk because diversification inside a sector is ignored. Sectors with only 1-2 stocks (Telecom, Conglomerate) are excluded from the headline rankings.
- **Sector tags are subjective** (see `src/config.py`). For example, Bharat Electronics (defence electronics) is grouped under Infrastructure and lifts that sector's result.
- Returns are price returns adjusted for splits and dividends by Yahoo Finance. Data quality of free sources is not guaranteed, as the issues above show.
- This is an analytical project, not investment advice.

## Possible extensions
Market-cap weighted sector indices, sector-portfolio volatility, Fama-French style factor analysis, a Streamlit app, scheduled daily refresh with GitHub Actions.


## Author

**Harsh Trivedi**  
**MBA (Computer Management) | Data Analytics & Financial Markets**

**Certifications:** NISM Research Analyst (Series XV) · NISM Equity Derivatives (Series VIII)

<!-- TODO: [LinkedIn](https://linkedin.com/in/...) | [Portfolio](https://...) -->
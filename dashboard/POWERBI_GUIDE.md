# Power BI dashboard build guide

Build time: about 60-90 minutes. Power BI Desktop is free (Windows).
Save the file as `dashboard/nifty50_sector_dashboard.pbix` and export screenshots to `dashboard/screenshots/`.

## 1. Load the data
**Home > Get data > Text/CSV** and load all of these from `data/processed/`:

| File | Use |
|---|---|
| `stock_metrics.csv` | one row per stock: CAGR, volatility, Sharpe, drawdown, beta |
| `sector_metrics.csv` | one row per sector (averages) |
| `sector_cumulative.csv` | daily sector index (base 100) for the line chart |
| `sector_monthly_returns.csv` | month x sector returns for the heatmap |
| `sector_rolling_volatility.csv` | 30-day rolling volatility by sector |
| `sector_correlation.csv` | sector-to-sector correlation matrix |

(Optional) You can connect to MySQL directly instead: **Get data > MySQL database**.

## 2. Model
- In Power Query, set `trade_date`/`month` to Date type and check decimal columns are numeric.
- Create a `DimSector` table: `DimSector = DISTINCT(sector_metrics[sector_name])`.
- Relate `DimSector[sector_name]` (one) to `stock_metrics`, `sector_cumulative`, `sector_monthly_returns` and `sector_rolling_volatility` on `sector_name` (many, single direction).
- Use `DimSector[sector_name]` for the slicer so one slicer filters every page.

## 3. DAX measures
```DAX
Avg CAGR %        = AVERAGE ( stock_metrics[cagr_pct] )
Avg Volatility %  = AVERAGE ( stock_metrics[ann_volatility_pct] )
Avg Sharpe        = AVERAGE ( stock_metrics[sharpe_ratio] )
Worst Drawdown %  = MIN ( stock_metrics[max_drawdown_pct] )
Avg Beta          = AVERAGE ( stock_metrics[beta_vs_nifty] )
Stock Count       = DISTINCTCOUNT ( stock_metrics[ticker] )

Best Stock (Sharpe) =
VAR top1 = TOPN ( 1, stock_metrics, stock_metrics[sharpe_ratio], DESC )
RETURN MAXX ( top1, stock_metrics[company_name] )

Risk Bucket =
SWITCH (
    TRUE (),
    [Avg Beta] >= 1.2, "High beta",
    [Avg Beta] >= 0.9, "Market-like",
    "Defensive"
)
```

## 4. Page layout

**Page 1 - Market overview**
- KPI cards: Stock Count, Avg CAGR %, Avg Volatility %, Avg Sharpe, Worst Drawdown %
- Line chart: `sector_cumulative` (x = trade_date, y = index_value, legend = sector_name)
- Bar chart: Avg Sharpe by sector (sorted descending)
- Slicer: sector_name

**Page 2 - Risk vs return**
- Scatter: x = ann_volatility_pct, y = cagr_pct, size = abs(total_return_pct) or fixed, details = company_name, legend = sector_name
- Table: company, sector, CAGR, volatility, Sharpe, beta (conditional formatting on Sharpe)
- Top N filter visual: Top 10 by Sharpe

**Page 3 - Sector deep dive**
- Matrix heatmap: rows = sector_name, columns = month, values = monthly_return (conditional formatting: red-white-green)
- Line chart: 30-day rolling volatility by sector
- Matrix of `sector_correlation` with colour scale

**Page 4 - Insights (text only)**
- 4-5 text boxes with your findings from `docs/key_findings.md`.

## 5. Design tips
- One accent colour plus greys; the same sector colour on every page.
- Titles say the finding: "Banking lagged on a risk-adjusted basis", not "Sharpe by sector".
- Hide gridlines, align visuals to the grid, keep fonts to Segoe UI.
- Export each page: **File > Export > Export to PDF**, and screenshot into `dashboard/screenshots/`.

-- ============================================================================
-- Nifty 50 Sector Analysis - SQL queries (MySQL 8+)
-- Run after: python src/02_clean_and_load.py
-- ============================================================================
USE nifty50_analysis;

-- ----------------------------------------------------------------------------
-- Q1. Data coverage check: history length and row count per stock
-- ----------------------------------------------------------------------------
SELECT  s.ticker,
        s.company_name,
        MIN(p.trade_date) AS first_date,
        MAX(p.trade_date) AS last_date,
        COUNT(*)          AS trading_days
FROM    fact_daily_prices p
JOIN    dim_stock s ON s.ticker = p.ticker
GROUP BY s.ticker, s.company_name
ORDER BY trading_days;

-- ----------------------------------------------------------------------------
-- Q2. Stock-level total return over the full period (first close -> last close)
-- ----------------------------------------------------------------------------
WITH ranked AS (
    SELECT  ticker, trade_date, close_price,
            ROW_NUMBER() OVER (PARTITION BY ticker ORDER BY trade_date ASC)  AS rn_first,
            ROW_NUMBER() OVER (PARTITION BY ticker ORDER BY trade_date DESC) AS rn_last
    FROM    fact_daily_prices
),
endpoints AS (
    SELECT  ticker,
            MAX(CASE WHEN rn_first = 1 THEN close_price END) AS first_close,
            MAX(CASE WHEN rn_last  = 1 THEN close_price END) AS last_close
    FROM    ranked
    GROUP BY ticker
)
SELECT  s.ticker, s.company_name, sec.sector_name,
        ROUND((e.last_close / e.first_close - 1) * 100, 2) AS total_return_pct
FROM    endpoints e
JOIN    dim_stock  s   ON s.ticker = e.ticker
JOIN    dim_sector sec ON sec.sector_id = s.sector_id
ORDER BY total_return_pct DESC;

-- ----------------------------------------------------------------------------
-- Q3. Sector ranking: average annualised volatility and daily return by sector
-- ----------------------------------------------------------------------------
WITH stock_stats AS (
    SELECT  ticker,
            AVG(daily_return) * 252             AS ann_return,
            STDDEV_SAMP(daily_return) * SQRT(252) AS ann_volatility
    FROM    fact_daily_prices
    GROUP BY ticker
    HAVING  COUNT(daily_return) >= 250
)
SELECT  sec.sector_name,
        COUNT(*)                                   AS stocks,
        ROUND(AVG(ss.ann_return) * 100, 2)         AS avg_ann_return_pct,
        ROUND(AVG(ss.ann_volatility) * 100, 2)     AS avg_ann_volatility_pct,
        ROUND(AVG(ss.ann_return) / AVG(ss.ann_volatility), 2) AS return_per_unit_risk,
        RANK() OVER (ORDER BY AVG(ss.ann_return) / AVG(ss.ann_volatility) DESC) AS risk_adj_rank
FROM    stock_stats ss
JOIN    dim_stock  s   ON s.ticker = ss.ticker
JOIN    dim_sector sec ON sec.sector_id = s.sector_id
GROUP BY sec.sector_name
ORDER BY risk_adj_rank;

-- ----------------------------------------------------------------------------
-- Q4. Monthly returns per stock (last close of the month vs previous month)
-- ----------------------------------------------------------------------------
WITH month_end AS (
    SELECT  ticker,
            DATE_FORMAT(trade_date, '%Y-%m') AS ym,
            close_price,
            ROW_NUMBER() OVER (PARTITION BY ticker, DATE_FORMAT(trade_date, '%Y-%m')
                               ORDER BY trade_date DESC) AS rn
    FROM    fact_daily_prices
),
monthly AS (
    SELECT ticker, ym, close_price FROM month_end WHERE rn = 1
)
SELECT  ticker, ym,
        ROUND((close_price / LAG(close_price) OVER (PARTITION BY ticker ORDER BY ym) - 1) * 100, 2)
            AS monthly_return_pct
FROM    monthly
ORDER BY ticker, ym;

-- ----------------------------------------------------------------------------
-- Q5. Top 10 gainers and bottom 10 losers over the last 12 months
-- ----------------------------------------------------------------------------
WITH window_prices AS (
    SELECT  ticker, trade_date, close_price,
            ROW_NUMBER() OVER (PARTITION BY ticker ORDER BY trade_date ASC)  AS rn_first,
            ROW_NUMBER() OVER (PARTITION BY ticker ORDER BY trade_date DESC) AS rn_last
    FROM    fact_daily_prices
    WHERE   trade_date >= DATE_SUB((SELECT MAX(trade_date) FROM fact_daily_prices), INTERVAL 12 MONTH)
),
perf AS (
    SELECT  ticker,
            (MAX(CASE WHEN rn_last  = 1 THEN close_price END) /
             MAX(CASE WHEN rn_first = 1 THEN close_price END) - 1) * 100 AS return_12m_pct
    FROM    window_prices
    GROUP BY ticker
),
ranked AS (
    SELECT  ticker, return_12m_pct,
            RANK() OVER (ORDER BY return_12m_pct DESC) AS best_rank,
            RANK() OVER (ORDER BY return_12m_pct ASC)  AS worst_rank
    FROM    perf
)
SELECT  CASE WHEN best_rank <= 10 THEN 'Top 10 gainer' ELSE 'Bottom 10 loser' END AS bucket,
        s.company_name, sec.sector_name, ROUND(r.return_12m_pct, 2) AS return_12m_pct
FROM    ranked r
JOIN    dim_stock  s   ON s.ticker = r.ticker
JOIN    dim_sector sec ON sec.sector_id = s.sector_id
WHERE   best_rank <= 10 OR worst_rank <= 10
ORDER BY r.return_12m_pct DESC;

-- ----------------------------------------------------------------------------
-- Q6. 30-day rolling annualised volatility (latest 10 days for every stock)
-- ----------------------------------------------------------------------------
WITH rolling AS (
    SELECT  ticker, trade_date,
            STDDEV_SAMP(daily_return) OVER (
                PARTITION BY ticker ORDER BY trade_date
                ROWS BETWEEN 29 PRECEDING AND CURRENT ROW) * SQRT(252) AS rolling_vol_30d,
            ROW_NUMBER() OVER (PARTITION BY ticker ORDER BY trade_date DESC) AS days_from_end
    FROM    fact_daily_prices
)
SELECT  ticker, trade_date, ROUND(rolling_vol_30d * 100, 2) AS rolling_vol_30d_pct
FROM    rolling
WHERE   days_from_end <= 10
ORDER BY ticker, trade_date;

-- ----------------------------------------------------------------------------
-- Q7. Maximum drawdown per stock (largest fall from a running peak)
-- ----------------------------------------------------------------------------
WITH peaks AS (
    SELECT  ticker, trade_date, close_price,
            MAX(close_price) OVER (PARTITION BY ticker ORDER BY trade_date
                                   ROWS UNBOUNDED PRECEDING) AS running_peak
    FROM    fact_daily_prices
),
drawdowns AS (
    SELECT ticker, trade_date, close_price / running_peak - 1 AS drawdown FROM peaks
)
SELECT  s.company_name, sec.sector_name,
        ROUND(MIN(d.drawdown) * 100, 2) AS max_drawdown_pct
FROM    drawdowns d
JOIN    dim_stock  s   ON s.ticker = d.ticker
JOIN    dim_sector sec ON sec.sector_id = s.sector_id
GROUP BY s.company_name, sec.sector_name
ORDER BY max_drawdown_pct;

-- ----------------------------------------------------------------------------
-- Q8. Best and worst calendar month for each sector (average sector return)
-- ----------------------------------------------------------------------------
WITH month_end AS (
    SELECT  ticker, DATE_FORMAT(trade_date, '%Y-%m') AS ym, close_price,
            ROW_NUMBER() OVER (PARTITION BY ticker, DATE_FORMAT(trade_date, '%Y-%m')
                               ORDER BY trade_date DESC) AS rn
    FROM    fact_daily_prices
),
monthly_ret AS (
    SELECT  ticker, ym,
            close_price / LAG(close_price) OVER (PARTITION BY ticker ORDER BY ym) - 1 AS ret
    FROM    month_end WHERE rn = 1
),
sector_month AS (
    SELECT  sec.sector_name,
            CAST(SUBSTRING(m.ym, 6, 2) AS UNSIGNED) AS cal_month,
            AVG(m.ret) * 100                          AS avg_ret_pct
    FROM    monthly_ret m
    JOIN    dim_stock  s   ON s.ticker = m.ticker
    JOIN    dim_sector sec ON sec.sector_id = s.sector_id
    WHERE   m.ret IS NOT NULL
    GROUP BY sec.sector_name, CAST(SUBSTRING(m.ym, 6, 2) AS UNSIGNED)
),
ranked AS (
    SELECT  *, RANK() OVER (PARTITION BY sector_name ORDER BY avg_ret_pct DESC) AS best_rk,
               RANK() OVER (PARTITION BY sector_name ORDER BY avg_ret_pct ASC)  AS worst_rk
    FROM    sector_month
)
SELECT  sector_name,
        MAX(CASE WHEN best_rk  = 1 THEN cal_month END) AS best_month_no,
        ROUND(MAX(CASE WHEN best_rk  = 1 THEN avg_ret_pct END), 2) AS best_month_avg_pct,
        MAX(CASE WHEN worst_rk = 1 THEN cal_month END) AS worst_month_no,
        ROUND(MAX(CASE WHEN worst_rk = 1 THEN avg_ret_pct END), 2) AS worst_month_avg_pct
FROM    ranked
GROUP BY sector_name
ORDER BY sector_name;

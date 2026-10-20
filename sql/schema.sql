-- Star-schema style design for Nifty 50 analysis (MySQL 8+)
-- Dimensions: sector, stock. Facts: daily stock prices, daily index prices.

CREATE DATABASE IF NOT EXISTS nifty50_analysis;
USE nifty50_analysis;

DROP TABLE IF EXISTS fact_daily_prices;
DROP TABLE IF EXISTS fact_index_prices;
DROP TABLE IF EXISTS dim_stock;
DROP TABLE IF EXISTS dim_sector;

CREATE TABLE dim_sector (
    sector_id   INT          NOT NULL PRIMARY KEY,
    sector_name VARCHAR(60)  NOT NULL UNIQUE
);

CREATE TABLE dim_stock (
    ticker       VARCHAR(20)  NOT NULL PRIMARY KEY,
    company_name VARCHAR(100) NOT NULL,
    sector_id    INT          NOT NULL,
    CONSTRAINT fk_stock_sector FOREIGN KEY (sector_id) REFERENCES dim_sector (sector_id)
);

CREATE TABLE fact_daily_prices (
    trade_date   DATE           NOT NULL,
    ticker       VARCHAR(20)    NOT NULL,
    open_price   DECIMAL(14,4)  NOT NULL,
    high_price   DECIMAL(14,4)  NOT NULL,
    low_price    DECIMAL(14,4)  NOT NULL,
    close_price  DECIMAL(14,4)  NOT NULL,
    volume       BIGINT         NOT NULL,
    daily_return DECIMAL(12,8)  NULL,
    PRIMARY KEY (trade_date, ticker),
    INDEX idx_ticker_date (ticker, trade_date),
    CONSTRAINT fk_price_stock FOREIGN KEY (ticker) REFERENCES dim_stock (ticker)
);

CREATE TABLE fact_index_prices (
    trade_date   DATE           NOT NULL PRIMARY KEY,
    close_price  DECIMAL(14,4)  NOT NULL,
    daily_return DECIMAL(12,8)  NULL
);

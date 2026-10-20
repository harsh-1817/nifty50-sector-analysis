"""Central configuration: tickers, sector mapping, paths and analysis constants."""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "data" / "raw"
PROCESSED_DIR = ROOT / "data" / "processed"
CHART_DIR = ROOT / "dashboard" / "charts"
DOCS_DIR = ROOT / "docs"
SQL_DIR = ROOT / "sql"

# Database connection. Override with the DB_URL environment variable (see .env.example)
DB_NAME = "nifty50_analysis"
DB_URL = os.getenv("DB_URL", f"mysql+pymysql://root:@localhost:3306/{DB_NAME}")

YEARS_OF_HISTORY = 5
TRADING_DAYS = 252
RISK_FREE_RATE = 0.065      # approx. India 10Y G-Sec yield, used for Sharpe ratio
MIN_OBSERVATIONS = 250      # stocks with less history (recent listings) are excluded from metrics
INDEX_TICKER = "^NSEI"      # Nifty 50 index (benchmark for beta)

# Yahoo Finance ticker -> (company name, sector)
# The Nifty 50 changes twice a year. Verify against niftyindices.com and edit as needed.
# Tickers that return no data are skipped and reported by the download script.
STOCKS = {
    "ADANIENT.NS":   ("Adani Enterprises", "Conglomerate"),
    "ADANIPORTS.NS": ("Adani Ports & SEZ", "Infrastructure"),
    "APOLLOHOSP.NS": ("Apollo Hospitals", "Healthcare"),
    "ASIANPAINT.NS": ("Asian Paints", "Consumer Goods"),
    "AXISBANK.NS":   ("Axis Bank", "Banking"),
    "BAJAJ-AUTO.NS": ("Bajaj Auto", "Automobile"),
    "BAJFINANCE.NS": ("Bajaj Finance", "Financial Services"),
    "BAJAJFINSV.NS": ("Bajaj Finserv", "Financial Services"),
    "BEL.NS":        ("Bharat Electronics", "Infrastructure"),
    "BHARTIARTL.NS": ("Bharti Airtel", "Telecom"),
    "CIPLA.NS":      ("Cipla", "Pharma"),
    "COALINDIA.NS":  ("Coal India", "Metals & Mining"),
    "DRREDDY.NS":    ("Dr. Reddy's Laboratories", "Pharma"),
    "EICHERMOT.NS":  ("Eicher Motors", "Automobile"),
    "ETERNAL.NS":    ("Eternal (Zomato)", "Consumer Services"),
    "GRASIM.NS":     ("Grasim Industries", "Cement & Materials"),
    "HCLTECH.NS":    ("HCL Technologies", "IT"),
    "HDFCBANK.NS":   ("HDFC Bank", "Banking"),
    "HDFCLIFE.NS":   ("HDFC Life Insurance", "Financial Services"),
    "HEROMOTOCO.NS": ("Hero MotoCorp", "Automobile"),
    "HINDALCO.NS":   ("Hindalco Industries", "Metals & Mining"),
    "HINDUNILVR.NS": ("Hindustan Unilever", "FMCG"),
    "ICICIBANK.NS":  ("ICICI Bank", "Banking"),
    "INDIGO.NS":     ("InterGlobe Aviation (IndiGo)", "Consumer Services"),
    "INFY.NS":       ("Infosys", "IT"),
    "ITC.NS":        ("ITC", "FMCG"),
    "JIOFIN.NS":     ("Jio Financial Services", "Financial Services"),
    "JSWSTEEL.NS":   ("JSW Steel", "Metals & Mining"),
    "KOTAKBANK.NS":  ("Kotak Mahindra Bank", "Banking"),
    "LT.NS":         ("Larsen & Toubro", "Infrastructure"),
    "M&M.NS":        ("Mahindra & Mahindra", "Automobile"),
    "MARUTI.NS":     ("Maruti Suzuki", "Automobile"),
    "MAXHEALTH.NS":  ("Max Healthcare", "Healthcare"),
    "NESTLEIND.NS":  ("Nestle India", "FMCG"),
    "NTPC.NS":       ("NTPC", "Power & Energy"),
    "ONGC.NS":       ("ONGC", "Oil & Gas"),
    "POWERGRID.NS":  ("Power Grid Corp", "Power & Energy"),
    "RELIANCE.NS":   ("Reliance Industries", "Oil & Gas"),
    "SBILIFE.NS":    ("SBI Life Insurance", "Financial Services"),
    "SBIN.NS":       ("State Bank of India", "Banking"),
    "SHRIRAMFIN.NS": ("Shriram Finance", "Financial Services"),
    "SUNPHARMA.NS":  ("Sun Pharmaceutical", "Pharma"),
    "TATASTEEL.NS":  ("Tata Steel", "Metals & Mining"),
    "TMPV.NS":       ("Tata Motors Passenger Vehicles", "Automobile"),
    "TCS.NS":        ("Tata Consultancy Services", "IT"),
    "TECHM.NS":      ("Tech Mahindra", "IT"),
    "TITAN.NS":      ("Titan Company", "Consumer Goods"),
    "TRENT.NS":      ("Trent", "Consumer Services"),
    "ULTRACEMCO.NS": ("UltraTech Cement", "Cement & Materials"),
    "WIPRO.NS":      ("Wipro", "IT"),
}

# Corporate actions that Yahoo does not adjust for.
# ticker -> (event date, factor applied to ALL prices before that date, note)
MANUAL_ADJUSTMENTS = {
    "TMPV.NS": ("2025-10-14", 400 / 660.75,
                "Demerger of CV business (NSE reference price 400 vs prior close 660.75)"),
    "TRENT.NS": ("2026-01-01", 2 / 3,
                 "Yahoo feed level shift (~2/3) from 1 Jan 2026; cross-checked vs reported closes of 4417 and 4055"),
}
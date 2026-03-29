# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Running the app

```bash
# Activate virtual environment (Windows)
.venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run locally (default port 5050)
python app.py
```

The app is available at `http://localhost:5050`. Login with credentials set via env vars `DASHBOARD_USER` / `DASHBOARD_PASS` (defaults: `admin` / `password`).

## Deployment (Railway)

```bash
# Railway uses gunicorn via Procfile / railway.toml
# Start command: gunicorn app:app --bind 0.0.0.0:$PORT --timeout 120 --workers 1
```

Required env vars on Railway: `SECRET_KEY`, `DASHBOARD_USER`, `DASHBOARD_PASS`, `PORT` (auto-set by Railway).

## Architecture

This is a single-file Flask app with a single-page frontend — no build step, no framework.

**`app.py`** — Flask backend only. Responsibilities:
- Session-based auth (SHA256 password hash, `flask-session`)
- Batch-fetches all tickers from Yahoo Finance via `yfinance.download()` with `group_by="column"` (MultiIndex DataFrame)
- Computes MA50, MA200, RSI(14), momentum scores (1M/3M/6M/12M), golden/death cross events per ticker
- Three endpoints: `/api/stocks/top` (tier 1, ~30 Large Cap), `/api/stocks` (all ~110 tickers in batches of 25), `/api/stock/<ticker>` (single)
- Streams `/api/stocks` response to avoid Railway's 120s timeout

**`dashboard.html`** — entire frontend as a static file served by Flask. Contains:
- All CSS (CSS custom properties in `:root`, no external CSS framework)
- All JS (vanilla, no bundler) — Chart.js + chartjs-plugin-annotation loaded from CDN
- `allData[]` is the in-memory store for all stock data fetched from the API
- Portfolio feature uses `localStorage` key `omxsgi_portfolio` — no backend required
- Two views: "Marknaden" (market table) and "Min Portfölj" (custom portfolio)

## Ticker tiers

Tickers in `TICKERS` dict have a tier value:
- `tier=1` — Large Cap top ~30 by market cap, loaded on page start via `/api/stocks/top`
- `tier=2` — rest of Large Cap + Mid Cap, loaded on demand via `/api/stocks`

## Portfolio logic

Portfolio is stored in `localStorage` as `{ created: "YYYY-MM-DD", stocks: [{ticker, name, initialPrice}] }`. Up to 10 stocks, equal 10% weight at creation. Returns are calculated buy-and-hold style (weights drift naturally over time). The portfolio chart uses the `dates`/`prices` arrays returned by the stock API, normalized to the creation date.

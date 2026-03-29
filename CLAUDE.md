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
# Start command: TZ=UTC gunicorn app:app --bind 0.0.0.0:$PORT --timeout 120 --workers 1
```

`TZ=UTC` is prepended to the start command (not set in code) to ensure UTC is active before Python loads — this prevents yfinance from generating naive datetimes that fall in a DST gap when localized to exchange timezones (e.g. `Europe/Stockholm`). Dates passed to `yf.download()` are always UTC date strings (`'YYYY-MM-DD'`), never naive `datetime` objects, for the same reason.

Required env vars on Railway: `SECRET_KEY`, `DASHBOARD_USER`, `DASHBOARD_PASS`, `PORT` (auto-set by Railway).

## Architecture

This is a single-file Flask app with a single-page frontend — no build step, no framework.

**`app.py`** — Flask backend only. Responsibilities:
- Session-based auth (SHA256 password hash, `flask-session`)
- Batch-fetches all tickers from Yahoo Finance via `yfinance.download()` with `auto_adjust=True`. Column format detection handles both old `(field, ticker)` and new `(ticker, field)` MultiIndex layouts — swaps levels if needed.
- Computes MA50, MA200, RSI(14), momentum scores (1M/3M/6M/12M), golden/death cross events per ticker
- Three endpoints: `/api/stocks/top` (tier 1, ~30 Large Cap), `/api/stocks` (all ~110 tickers in batches of 25), `/api/stock/<ticker>` (single)
- Streams `/api/stocks` response to avoid Railway's 120s timeout

**`dashboard.html`** — entire frontend as a static file served by Flask. Contains:
- All CSS (CSS custom properties in `:root`, no external CSS framework)
- All JS (vanilla, no bundler) — Chart.js + chartjs-plugin-annotation loaded from CDN
- `allData[]` is the in-memory store for all stock data fetched from the API
- Portfolio feature uses `localStorage` key `omxsgi_portfolio` — no backend required
- Two views: "Marknaden" (market table) and "Min Portfölj" (custom portfolio)

**Login page** — inline HTML string in `app.py` (`login_page()` route, GET `/login`). Same theme as dashboard — edit the f-string directly. Note: CSS braces must be doubled (`{{`, `}}`) inside f-strings.

## Ticker tiers

Tickers in `TICKERS` dict have a tier value:
- `tier=1` — Large Cap top ~30 by market cap, loaded on page start via `/api/stocks/top`
- `tier=2` — rest of Large Cap + Mid Cap, loaded on demand via `/api/stocks`

## Design system (Nordic Night theme)

Both `dashboard.html` and the login page in `app.py` share the same visual theme. Key tokens:

| Variable | Value | Usage |
|---|---|---|
| `--bg` | `#0b0f1a` | Page background |
| `--surface` | `#121827` | Cards, panels |
| `--surface2` | `#1a2335` | Table headers, section headers |
| `--border` | `#263348` | All borders |
| `--accent` | `#5a9fd4` | Primary blue (buttons, active states) |
| `--accent2` | `#7dbde8` | Lighter blue (hover, chart price line) |
| `--green` | `#4ade80` | Positive returns, Golden Cross |
| `--red` / `--danger` | `#f87171` | Negative returns, Death Cross |
| `--warn` | `#fbbf24` | MA200 line, neutral momentum |
| `--text` | `#dce8f5` | Primary text |
| `--muted` | `#64748b` | Secondary/label text |
| `--muted2` | `#8fa3bf` | Tertiary text |

**Fonts:** `Outfit` (UI, headers, names) + `Fira Code` (prices, tickers, monospace data). Loaded from Google Fonts.

**Border-radius scale:** `--radius-lg: 16px` (panels), `--radius: 12px` (cards), `--radius-sm: 8px` (buttons/inputs), `--radius-xs: 6px` (badges/metrics).

No glows, no scanlines, no grid background. Hover states use subtle background fills, not box-shadows.

**Chart.js colors:** Price line `#7dbde8`, MA50 `#5a9fd4`, MA200 `#fbbf24`. All chart fonts use `Fira Code`.

**App name:** "OMX Momentum" (not "OMXSGI Momentum") — used in `<title>`, `<h1>`, and login page.

## Portfolio logic

Portfolio is stored in `localStorage` as `{ created: "YYYY-MM-DD", stocks: [{ticker, name, initialPrice}] }`. Up to 10 stocks, equal 10% weight at creation. Returns are calculated buy-and-hold style (weights drift naturally over time). The portfolio chart uses the `dates`/`prices` arrays returned by the stock API, normalized to the creation date.

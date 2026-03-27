from flask import Flask, jsonify, request, session, redirect, url_for, send_from_directory
from flask_cors import CORS
from functools import wraps
import os
import hashlib
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import time

app = Flask(__name__, static_folder=".", static_url_path="")
app.secret_key = os.environ.get("SECRET_KEY", "omxsgi-momentum-secret-2024")
CORS(app)

# ── Inloggning ──────────────────────────────────────────────────────────
USERNAME = os.environ.get("DASHBOARD_USER", "admin")
# Lösenord hashas med SHA256 — aldrig plain text i minnet
PASSWORD_HASH = hashlib.sha256(
    os.environ.get("DASHBOARD_PASS", "password").encode()
).hexdigest()

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("logged_in"):
            return redirect(url_for("login_page"))
        return f(*args, **kwargs)
    return decorated

# -----------------------------------------------------------------------
# Large Cap + Mid Cap på Stockholmsbörsen
# tier=1 → Large Cap (approx top 30 efter börsvärde, visas vid start)
# tier=2 → resten av Large Cap + Mid Cap (laddas vid "Visa alla")
# -----------------------------------------------------------------------
TICKERS = {
    # ── LARGE CAP tier 1 (top ~30 börsvärde) ──────────────────────────
    "INVE-B.ST":   ("Investor B",          1),
    "AZN.ST":      ("AstraZeneca",         1),
    "ATCO-A.ST":   ("Atlas Copco A",       1),
    "ATCO-B.ST":   ("Atlas Copco B",       1),
    "ABB.ST":      ("ABB",                 1),
    "VOLV-B.ST":   ("Volvo B",             1),
    "VOLV-A.ST":   ("Volvo A",             1),
    "SHB-A.ST":    ("Handelsbanken A",     1),
    "SEB-A.ST":    ("SEB A",               1),
    "SWED-A.ST":   ("Swedbank A",          1),
    "ERIC-B.ST":   ("Ericsson B",          1),
    "HEXA-B.ST":   ("Hexagon B",           1),
    "EQT.ST":      ("EQT",                 1),
    "SAND.ST":     ("Sandvik",             1),
    "ASSA-B.ST":   ("Assa Abloy B",        1),
    "NDA-SE.ST":   ("Nordea",              1),
    "EPIR-B.ST":   ("Epiroc B",            1),
    "EPIR-A.ST":   ("Epiroc A",            1),
    "EVO.ST":      ("Evolution",           1),
    "ALFA.ST":     ("Alfa Laval",          1),
    "HM-B.ST":     ("H&M B",              1),
    "LIFCO-B.ST":  ("Lifco B",             1),
    "ADDT-B.ST":   ("Addtech B",           1),
    "LATO-B.ST":   ("Latour B",            1),
    "SKA-B.ST":    ("Skanska B",           1),
    "ESSITY-B.ST": ("Essity B",            1),
    "NIBE-B.ST":   ("NIBE B",              1),
    "TREL-B.ST":   ("Trelleborg B",        1),
    "INDU-A.ST":   ("Industrivärden A",    1),
    "INDU-C.ST":   ("Industrivärden C",    1),

    # ── LARGE CAP tier 2 ───────────────────────────────────────────────
    "BOL.ST":      ("Boliden",             2),
    "ELUX-B.ST":   ("Electrolux B",        2),
    "GETI-B.ST":   ("Getinge B",           2),
    "HUSQ-B.ST":   ("Husqvarna B",         2),
    "HUSQ-A.ST":   ("Husqvarna A",         2),
    "KINV-B.ST":   ("Kinnevik B",          2),
    "LUND-B.ST":   ("Lundbergföretagen B", 2),
    "SCA-B.ST":    ("SCA B",               2),
    "SEB-C.ST":    ("SEB C",               2),
    "SECU-B.ST":   ("Securitas B",         2),
    "SHB-B.ST":    ("Handelsbanken B",     2),
    "SKF-B.ST":    ("SKF B",               2),
    "SSAB-A.ST":   ("SSAB A",              2),
    "SSAB-B.ST":   ("SSAB B",              2),
    "STE-R.ST":    ("Stora Enso R",        2),
    "TELE2-B.ST":  ("Tele2 B",             2),
    "TELIA.ST":    ("Telia",               2),
    "VOLCAR-B.ST": ("Volvo Cars B",        2),
    "EKTA-B.ST":   ("Elekta B",            2),

    # ── MID CAP ────────────────────────────────────────────────────────
    "AAK.ST":      ("AAK",                 2),
    "ALIV-SDB.ST": ("Autoliv SDB",         2),
    "AMBEA.ST":    ("Ambea",               2),
    "AXFO.ST":     ("Axfood",              2),
    "BALD-B.ST":   ("Balder B",            2),
    "BETS-B.ST":   ("Betsson B",           2),
    "BIOG-B.ST":   ("BioGaia B",           2),
    "BUFAB.ST":    ("Bufab",               2),
    "CAMX.ST":     ("Camurus",             2),
    "CAST.ST":     ("Castellum",           2),
    "CATE.ST":     ("Catena",              2),
    "CLAS-B.ST":   ("Clas Ohlson B",       2),
    "DIOS.ST":     ("Diös Fastigheter",    2),
    "DOM.ST":      ("Dometic",             2),
    "DUST-B.ST":   ("Dustin B",            2),
    "FABG.ST":     ("Fabege",              2),
    "FNOX.ST":     ("Fortnox",             2),
    "GARO.ST":     ("Garo",                2),
    "HEIM-B.ST":   ("Heimstaden B",        2),
    "HEXP.ST":     ("Hexatronic",          2),
    "HMS.ST":      ("HMS Networks",        2),
    "HOLM-B.ST":   ("Holmen B",            2),
    "HUFV-A.ST":   ("Hufvudstaden A",      2),
    "ICA.ST":      ("ICA Gruppen",         2),
    "INDT.ST":     ("Indutrade",           2),
    "INSTAL.ST":   ("Instalco",            2),
    "INTRUM.ST":   ("Intrum",              2),
    "INWI.ST":     ("Inwido",              2),
    "ITAB.ST":     ("ITAB Shop Concept",   2),
    "IVSO.ST":     ("Invisio",             2),
    "JM.ST":       ("JM",                  2),
    "LAGR-B.ST":   ("Lagercrantz B",       2),
    "LOOMIS.ST":   ("Loomis",              2),
    "MEDI.ST":     ("Medicover",           2),
    "MEKO.ST":     ("Mekonomen",           2),
    "NENT-B.ST":   ("NENT B",              2),
    "NOBI.ST":     ("Nobina",              2),
    "NOLA-B.ST":   ("Nolato B",            2),
    "NOTE.ST":     ("Note",                2),
    "NP3.ST":      ("NP3 Fastigheter",     2),
    "NYFOSA.ST":   ("Nyfosa",              2),
    "PEAB-B.ST":   ("Peab B",              2),
    "PFAB.ST":     ("Platzer Fastigheter", 2),
    "PIRC.ST":     ("Pierce Group",        2),
    "PNDX-B.ST":   ("Pandox B",            2),
    "RECI.ST":     ("Recipharm",           2),
    "REJL-B.ST":   ("Rejlers B",           2),
    "RESURS.ST":   ("Resurs Holding",      2),
    "RVRC.ST":     ("RVRC Holding",        2),
    "SAGA-B.ST":   ("Sagax B",             2),
    "SGRY.ST":     ("Surgical Science",    2),
    "SINCH.ST":    ("Sinch",               2),
    "SKIT-B.ST":   ("Skistar B",           2),
    "SOBI.ST":     ("Sobi",                2),
    "SWEC-B.ST":   ("Sweco B",             2),
    "SYSR.ST":     ("Systemair",           2),
    "THULE.ST":    ("Thule Group",         2),
    "TOBII.ST":    ("Tobii",               2),
    "TROAX.ST":    ("Troax",               2),
    "VITR.ST":     ("Vitrolife",           2),
    "WALL-B.ST":   ("Wallenstam B",        2),
    "WIHL.ST":     ("Wihlborgs",           2),
    "XANO-B.ST":   ("Xano Industri B",     2),
    "YUBICO.ST":   ("Yubico",              2),
}


def compute_rsi(series, period=14):
    delta = series.diff()
    gain  = delta.clip(lower=0)
    loss  = -delta.clip(upper=0)
    avg_gain = gain.ewm(com=period - 1, min_periods=period).mean()
    avg_loss = loss.ewm(com=period - 1, min_periods=period).mean()
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


def process_ticker(ticker, name, tier, df_all):
    """
    Extraherar data för en enskild ticker ur en batch-DataFrame.
    df_all har alltid MultiIndex kolumner: (field, ticker)
    """
    try:
        if ("Close", ticker) not in df_all.columns:
            return None

        close = df_all[("Close", ticker)].dropna().astype(float)
        if len(close) < 50:
            return None

        vol_col = ("Volume", ticker)
        vol = df_all[vol_col].fillna(0).astype(float) if vol_col in df_all.columns else None

        # ── SMA ─────────────────────────────────────────────────────────
        ma50  = close.rolling(50).mean()
        ma200 = close.rolling(200).mean()
        rsi   = compute_rsi(close)

        price     = float(close.iloc[-1])
        ma50_val  = float(ma50.iloc[-1])
        ma200_val = float(ma200.iloc[-1])
        rsi_val   = float(rsi.iloc[-1])

        def pct(days):
            if len(close) > days:
                return float((close.iloc[-1] / close.iloc[-days] - 1) * 100)
            return None

        mom_1m  = pct(21)
        mom_3m  = pct(63)
        mom_6m  = pct(126)
        mom_12m = pct(252)

        above_ma200  = price > ma200_val
        golden_cross = ma50_val > ma200_val

        vol_ratio = 1.0
        if vol is not None and len(vol) >= 20:
            avg20     = float(vol.rolling(20).mean().iloc[-1])
            vol_today = float(vol.iloc[-1])
            vol_ratio = round(vol_today / avg20, 2) if avg20 > 0 else 1.0

        scores = []
        if mom_1m  is not None: scores.append(min(max(mom_1m  / 10, -1), 1))
        if mom_3m  is not None: scores.append(min(max(mom_3m  / 20, -1), 1))
        if mom_6m  is not None: scores.append(min(max(mom_6m  / 30, -1), 1))
        if mom_12m is not None: scores.append(min(max(mom_12m / 40, -1), 1))
        if above_ma200:  scores.append(0.5)
        if golden_cross: scores.append(0.5)
        momentum_score = round((sum(scores) / len(scores)) * 100, 1) if scores else 0

        cross_events = []
        valid = ma50.dropna().index.intersection(ma200.dropna().index)
        if len(valid) > 1:
            above   = (ma50.loc[valid] > ma200.loc[valid])
            changes = above.astype(int).diff()
            for dt, val in changes.items():
                if val == 1:
                    cross_events.append({"date": dt.strftime("%Y-%m-%d"), "type": "golden"})
                elif val == -1:
                    cross_events.append({"date": dt.strftime("%Y-%m-%d"), "type": "death"})

        last_golden_date = next((e["date"] for e in reversed(cross_events) if e["type"] == "golden"), None)
        last_death_date  = next((e["date"] for e in reversed(cross_events) if e["type"] == "death"),  None)
        last_cross_date  = cross_events[-1]["date"] if cross_events else None
        last_cross_type  = cross_events[-1]["type"] if cross_events else None

        n         = min(252, len(close))
        dates     = [d.strftime("%Y-%m-%d") for d in close.index[-n:]]
        prices    = [round(float(v), 2) for v in close.values[-n:]]
        ma50_arr  = [None if np.isnan(v) else round(float(v), 2) for v in ma50.values[-n:]]
        ma200_arr = [None if np.isnan(v) else round(float(v), 2) for v in ma200.values[-n:]]

        return {
            "ticker":           ticker,
            "name":             name,
            "tier":             tier,
            "price":            round(price, 2),
            "ma50":             round(ma50_val, 2),
            "ma200":            round(ma200_val, 2),
            "rsi":              round(rsi_val, 1),
            "mom_1m":           round(mom_1m,  1) if mom_1m  is not None else None,
            "mom_3m":           round(mom_3m,  1) if mom_3m  is not None else None,
            "mom_6m":           round(mom_6m,  1) if mom_6m  is not None else None,
            "mom_12m":          round(mom_12m, 1) if mom_12m is not None else None,
            "above_ma200":      above_ma200,
            "golden_cross":     golden_cross,
            "vol_ratio":        vol_ratio,
            "momentum_score":   momentum_score,
            "cross_events":     cross_events,
            "last_cross_date":  last_cross_date,
            "last_cross_type":  last_cross_type,
            "last_golden_date": last_golden_date,
            "last_death_date":  last_death_date,
            "dates":            dates,
            "prices":           prices,
            "ma50_arr":         ma50_arr,
            "ma200_arr":        ma200_arr,
        }
    except Exception as e:
        print(f"  [skip] {ticker}: {e}")
        return None


def fetch_tickers(ticker_dict):
    """
    Hämtar alla tickers i ett enda yfinance-anrop (korrekt batch-metod).
    Returnerar lista med stock-dicts.
    """
    end   = datetime.now()
    start = end - timedelta(days=365 * 2)
    tickers_list = list(ticker_dict.keys())

    print(f"  Hämtar {len(tickers_list)} tickers från Yahoo Finance...")
    df = yf.download(
        tickers_list,
        start=start,
        end=end,
        progress=False,
        auto_adjust=True,
        group_by="column",   # ger MultiIndex (field, ticker) — korrekt för batch
        threads=True,
    )

    if df.empty:
        print("  [fel] Tom DataFrame från yfinance")
        return []

    # Säkerställ MultiIndex även om bara en ticker returnerades
    if not isinstance(df.columns, pd.MultiIndex):
        # Wrap single-ticker result
        df.columns = pd.MultiIndex.from_tuples(
            [(col, tickers_list[0]) for col in df.columns]
        )

    results = []
    for ticker, (name, tier) in ticker_dict.items():
        data = process_ticker(ticker, name, tier, df)
        if data:
            results.append(data)
        else:
            print(f"  [saknas] {ticker}")

    return results


@app.route("/")
def index():
    if not session.get("logged_in"):
        return redirect(url_for("login_page"))
    return send_from_directory(".", "dashboard.html")


@app.route("/login", methods=["GET"])
def login_page():
    error = request.args.get("error")
    return f"""<!DOCTYPE html>
<html lang="sv">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>OMXSGI Momentum — Logga in</title>
<link href="https://fonts.googleapis.com/css2?family=Syne:wght@700;800&family=DM+Mono:wght@400;500&display=swap" rel="stylesheet">
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{
    background: #0a0c0f;
    color: #e8ecf0;
    font-family: 'DM Mono', monospace;
    min-height: 100vh;
    display: flex;
    align-items: center;
    justify-content: center;
  }}
  body::before {{
    content: '';
    position: fixed;
    inset: 0;
    background-image: linear-gradient(#1e2530 1px, transparent 1px), linear-gradient(90deg, #1e2530 1px, transparent 1px);
    background-size: 40px 40px;
    opacity: 0.3;
    pointer-events: none;
  }}
  .box {{
    position: relative;
    background: #111418;
    border: 1px solid #1e2530;
    padding: 48px 40px;
    width: 360px;
  }}
  h1 {{
    font-family: 'Syne', sans-serif;
    font-size: 1.6rem;
    font-weight: 800;
    letter-spacing: -0.03em;
    margin-bottom: 4px;
  }}
  h1 span {{ color: #00e5a0; }}
  .sub {{
    font-size: 0.65rem;
    color: #5a6370;
    text-transform: uppercase;
    letter-spacing: 0.1em;
    margin-bottom: 32px;
  }}
  label {{
    font-size: 0.62rem;
    color: #5a6370;
    text-transform: uppercase;
    letter-spacing: 0.1em;
    display: block;
    margin-bottom: 6px;
  }}
  input {{
    width: 100%;
    background: #171b21;
    border: 1px solid #1e2530;
    color: #e8ecf0;
    font-family: 'DM Mono', monospace;
    font-size: 0.85rem;
    padding: 10px 12px;
    margin-bottom: 20px;
    outline: none;
    transition: border-color 0.15s;
  }}
  input:focus {{ border-color: #00e5a0; }}
  button {{
    width: 100%;
    background: transparent;
    border: 1px solid #00e5a0;
    color: #00e5a0;
    font-family: 'DM Mono', monospace;
    font-size: 0.72rem;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    padding: 12px;
    cursor: pointer;
    transition: all 0.15s;
  }}
  button:hover {{ background: #00e5a0; color: #0a0c0f; }}
  .error {{ color: #ff4560; font-size: 0.68rem; margin-bottom: 16px; }}
</style>
</head>
<body>
<div class="box">
  <h1>OMXSGI <span>Momentum</span></h1>
  <p class="sub">Stockholmsbörsen Dashboard</p>
  {"<p class='error'>⚠ Fel användarnamn eller lösenord</p>" if error else ""}
  <form method="POST" action="/login">
    <label>Användarnamn</label>
    <input type="text" name="username" autofocus autocomplete="username">
    <label>Lösenord</label>
    <input type="password" name="password" autocomplete="current-password">
    <button type="submit">Logga in →</button>
  </form>
</div>
</body>
</html>"""


@app.route("/login", methods=["POST"])
def login():
    username = request.form.get("username", "")
    password = request.form.get("password", "")
    pw_hash  = hashlib.sha256(password.encode()).hexdigest()
    if username == USERNAME and pw_hash == PASSWORD_HASH:
        session["logged_in"] = True
        return redirect(url_for("index"))
    return redirect(url_for("login_page") + "?error=1")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login_page"))


@app.route("/api/stocks")

def stocks():
    """Returnerar alla tier 1 + tier 2."""
    results = fetch_tickers(TICKERS)
    results.sort(key=lambda x: x["momentum_score"], reverse=True)
    return jsonify(results)


@app.route("/api/stocks/top")
@login_required
def stocks_top():
    """Returnerar bara tier 1 (top 30 Large Cap)."""
    top_tickers = {t: v for t, v in TICKERS.items() if v[1] == 1}
    results = fetch_tickers(top_tickers)
    results.sort(key=lambda x: x["momentum_score"], reverse=True)
    return jsonify(results)


@app.route("/api/stock/<path:ticker>")
@login_required
def single_stock(ticker):
    if ticker not in TICKERS:
        return jsonify({"error": "Not found"}), 404
    result = fetch_tickers({ticker: TICKERS[ticker]})
    if result:
        return jsonify(result[0])
    return jsonify({"error": "Kunde inte hämta data"}), 500


if __name__ == "__main__":
    total = len(TICKERS)
    tier1 = sum(1 for v in TICKERS.values() if v[1] == 1)
    port  = int(os.environ.get("PORT", 5050))
    print(f"Startar — {total} aktier ({tier1} Large Cap tier 1, {total-tier1} tier 2) på port {port}")
    app.run(host="0.0.0.0", port=port, debug=False)

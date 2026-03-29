from flask import Flask, jsonify, request, session, redirect, url_for, Response
from flask_cors import CORS
from functools import wraps
from dotenv import load_dotenv
import os
import hashlib
import requests as req_lib

load_dotenv()
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

app = Flask(__name__, static_folder=".", static_url_path="")
app.secret_key = os.environ.get("SECRET_KEY", "omxsgi-momentum-secret-2024")
CORS(app)

# ── Supabase ─────────────────────────────────────────────────────────────
_SB_URL = os.environ.get("SUPABASE_URL", "https://rdmubjbwfzxukacfbrqs.supabase.co")
_SB_KEY = os.environ.get("SUPABASE_SERVICE_KEY", "")

def _sb_headers():
    return {
        "apikey": _SB_KEY,
        "Authorization": f"Bearer {_SB_KEY}",
        "Content-Type": "application/json",
    }

def sb_get_user(username):
    r = req_lib.get(
        f"{_SB_URL}/rest/v1/users",
        headers=_sb_headers(),
        params={"username": f"eq.{username}", "select": "username,password_hash"},
        timeout=5,
    )
    data = r.json() if r.ok else []
    return data[0] if data else None

def sb_create_user(username, password_hash):
    r = req_lib.post(
        f"{_SB_URL}/rest/v1/users",
        headers={**_sb_headers(), "Prefer": "return=minimal"},
        json={"username": username, "password_hash": password_hash},
        timeout=5,
    )
    return r.status_code in (200, 201)

# ── Auth ─────────────────────────────────────────────────────────────────
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
    # Use date strings (not datetime objects) so yfinance parses them as midnight,
    # which avoids DST nonexistent-time errors when the current time falls in a gap.
    end   = datetime.utcnow().strftime('%Y-%m-%d')
    start = (datetime.utcnow() - timedelta(days=365 * 2)).strftime('%Y-%m-%d')
    tickers_list = list(ticker_dict.keys())

    print(f"  Hämtar {len(tickers_list)} tickers från Yahoo Finance...")
    df = yf.download(
        tickers_list,
        start=start,
        end=end,
        progress=False,
        auto_adjust=True,
    )

    if df.empty:
        print("  [fel] Tom DataFrame från yfinance")
        return []

    FIELD_NAMES = {'Open', 'High', 'Low', 'Close', 'Volume', 'Adj Close', 'Dividends', 'Stock Splits'}

    # Normalisera till (field, ticker) MultiIndex oavsett yfinance-version
    if not isinstance(df.columns, pd.MultiIndex):
        # Enstaka ticker — wrap till MultiIndex
        df.columns = pd.MultiIndex.from_tuples(
            [(col, tickers_list[0]) for col in df.columns]
        )
    elif df.columns.get_level_values(0)[0] not in FIELD_NAMES:
        # Ny yfinance-format: (ticker, field) → byt till (field, ticker)
        print("  [info] Ny yfinance-kolumnordning detekterad — byter nivåer")
        df = df.swaplevel(axis=1).sort_index(axis=1)

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
    username = session.get("username", "default")
    html_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "dashboard.html")
    with open(html_path, "r", encoding="utf-8") as f:
        html = f.read()
    html = html.replace("</head>", f'<script>window.__PF_USER__="{username}";</script></head>', 1)
    return Response(html, mimetype="text/html")


@app.route("/login", methods=["GET"])
def login_page():
    error = request.args.get("error")
    return f"""<!DOCTYPE html>
<html lang="sv">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>OMX Momentum — Logga in</title>
<link href="https://fonts.googleapis.com/css2?family=Outfit:wght@400;500;600;700&family=Fira+Code:wght@400;500&display=swap" rel="stylesheet">
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{
    background: #0b0f1a;
    color: #dce8f5;
    font-family: 'Outfit', sans-serif;
    min-height: 100vh;
    display: flex;
    align-items: center;
    justify-content: center;
  }}
  .box {{
    background: #121827;
    border: 1px solid #263348;
    border-radius: 16px;
    padding: 48px 40px;
    width: 380px;
    box-shadow: 0 8px 32px rgba(0,0,0,0.4);
  }}
  .logo {{
    display: flex;
    align-items: center;
    gap: 10px;
    margin-bottom: 6px;
  }}
  .logo-dot {{
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background: #5a9fd4;
    flex-shrink: 0;
  }}
  h1 {{
    font-family: 'Outfit', sans-serif;
    font-size: 1.6rem;
    font-weight: 700;
    letter-spacing: -0.02em;
    color: #dce8f5;
  }}
  h1 span {{ color: #5a9fd4; }}
  .sub {{
    font-size: 0.76rem;
    color: #64748b;
    font-weight: 400;
    margin-bottom: 36px;
    margin-left: 18px;
  }}
  label {{
    font-size: 0.72rem;
    color: #8fa3bf;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    display: block;
    margin-bottom: 6px;
  }}
  input {{
    width: 100%;
    background: #1a2335;
    border: 1px solid #263348;
    border-radius: 8px;
    color: #dce8f5;
    font-family: 'Fira Code', monospace;
    font-size: 0.88rem;
    padding: 11px 14px;
    margin-bottom: 20px;
    outline: none;
    transition: border-color 0.15s, box-shadow 0.15s;
  }}
  input:focus {{
    border-color: #5a9fd4;
    box-shadow: 0 0 0 3px rgba(90,159,212,0.12);
  }}
  button {{
    width: 100%;
    background: #5a9fd4;
    border: none;
    border-radius: 8px;
    color: #0b0f1a;
    font-family: 'Outfit', sans-serif;
    font-size: 0.88rem;
    font-weight: 600;
    padding: 12px;
    cursor: pointer;
    transition: background 0.15s, transform 0.1s;
    margin-top: 4px;
  }}
  button:hover {{ background: #7dbde8; }}
  button:active {{ transform: scale(0.99); }}
  .error {{
    color: #f87171;
    font-size: 0.76rem;
    margin-bottom: 18px;
    padding: 10px 14px;
    background: rgba(248,113,113,0.08);
    border: 1px solid rgba(248,113,113,0.2);
    border-radius: 8px;
  }}
</style>
</head>
<body>
<div class="box">
  <div class="logo"><div class="logo-dot"></div><h1>OMX <span>Momentum</span></h1></div>
  <p class="sub">Stockholmsbörsen Dashboard</p>
  {"<p class='error'>⚠ Fel användarnamn eller lösenord</p>" if error else ""}
  <form method="POST" action="/login">
    <label>Användarnamn</label>
    <input type="text" name="username" autofocus autocomplete="username">
    <label>Lösenord</label>
    <input type="password" name="password" autocomplete="current-password">
    <button type="submit">Logga in</button>
  </form>
  <p style="text-align:center;margin-top:20px;font-size:0.78rem;color:#64748b;">
    Inget konto? <a href="/register" style="color:#5a9fd4;text-decoration:none;font-weight:600;">Skapa konto</a>
  </p>
</div>
</body>
</html>"""


def _register_page(error_msg=""):
    err_html = f"<p class='error'>⚠ {error_msg}</p>" if error_msg else ""
    return f"""<!DOCTYPE html>
<html lang="sv">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>OMX Momentum — Skapa konto</title>
<link href="https://fonts.googleapis.com/css2?family=Outfit:wght@400;500;600;700&family=Fira+Code:wght@400;500&display=swap" rel="stylesheet">
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{
    background: #0b0f1a;
    color: #dce8f5;
    font-family: 'Outfit', sans-serif;
    min-height: 100vh;
    display: flex;
    align-items: center;
    justify-content: center;
  }}
  .box {{
    background: #121827;
    border: 1px solid #263348;
    border-radius: 16px;
    padding: 48px 40px;
    width: 380px;
    box-shadow: 0 8px 32px rgba(0,0,0,0.4);
  }}
  .logo {{
    display: flex;
    align-items: center;
    gap: 10px;
    margin-bottom: 6px;
  }}
  .logo-dot {{
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background: #5a9fd4;
    flex-shrink: 0;
  }}
  h1 {{
    font-family: 'Outfit', sans-serif;
    font-size: 1.6rem;
    font-weight: 700;
    letter-spacing: -0.02em;
    color: #dce8f5;
  }}
  h1 span {{ color: #5a9fd4; }}
  .sub {{
    font-size: 0.76rem;
    color: #64748b;
    font-weight: 400;
    margin-bottom: 36px;
    margin-left: 18px;
  }}
  label {{
    font-size: 0.72rem;
    color: #8fa3bf;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    display: block;
    margin-bottom: 6px;
  }}
  input {{
    width: 100%;
    background: #1a2335;
    border: 1px solid #263348;
    border-radius: 8px;
    color: #dce8f5;
    font-family: 'Fira Code', monospace;
    font-size: 0.88rem;
    padding: 11px 14px;
    margin-bottom: 20px;
    outline: none;
    transition: border-color 0.15s, box-shadow 0.15s;
  }}
  input:focus {{
    border-color: #5a9fd4;
    box-shadow: 0 0 0 3px rgba(90,159,212,0.12);
  }}
  button {{
    width: 100%;
    background: #5a9fd4;
    border: none;
    border-radius: 8px;
    color: #0b0f1a;
    font-family: 'Outfit', sans-serif;
    font-size: 0.88rem;
    font-weight: 600;
    padding: 12px;
    cursor: pointer;
    transition: background 0.15s, transform 0.1s;
    margin-top: 4px;
  }}
  button:hover {{ background: #7dbde8; }}
  button:active {{ transform: scale(0.99); }}
  .error {{
    color: #f87171;
    font-size: 0.76rem;
    margin-bottom: 18px;
    padding: 10px 14px;
    background: rgba(248,113,113,0.08);
    border: 1px solid rgba(248,113,113,0.2);
    border-radius: 8px;
  }}
</style>
</head>
<body>
<div class="box">
  <div class="logo"><div class="logo-dot"></div><h1>OMX <span>Momentum</span></h1></div>
  <p class="sub">Skapa ett konto</p>
  {err_html}
  <form method="POST" action="/register">
    <label>Användarnamn</label>
    <input type="text" name="username" autofocus autocomplete="username" placeholder="minst 3 tecken">
    <label>Lösenord</label>
    <input type="password" name="password" autocomplete="new-password" placeholder="minst 6 tecken">
    <label>Bekräfta lösenord</label>
    <input type="password" name="confirm" autocomplete="new-password">
    <button type="submit">Skapa konto</button>
  </form>
  <p style="text-align:center;margin-top:20px;font-size:0.78rem;color:#64748b;">
    Har du redan ett konto? <a href="/login" style="color:#5a9fd4;text-decoration:none;font-weight:600;">Logga in</a>
  </p>
</div>
</body>
</html>"""


@app.route("/login", methods=["POST"])
def login():
    username = request.form.get("username", "").strip().lower()
    password = request.form.get("password", "")
    pw_hash  = hashlib.sha256(password.encode()).hexdigest()
    user = sb_get_user(username)
    if user and user["password_hash"] == pw_hash:
        session["logged_in"] = True
        session["username"] = username
        return redirect(url_for("index"))
    return redirect(url_for("login_page") + "?error=1")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form.get("username", "").strip().lower()
        password = request.form.get("password", "")
        confirm  = request.form.get("confirm", "")
        if len(username) < 3:
            return redirect(url_for("register") + "?error=short_username")
        if len(password) < 6:
            return redirect(url_for("register") + "?error=short_password")
        if password != confirm:
            return redirect(url_for("register") + "?error=mismatch")
        if sb_get_user(username):
            return redirect(url_for("register") + "?error=taken")
        pw_hash = hashlib.sha256(password.encode()).hexdigest()
        if sb_create_user(username, pw_hash):
            session["logged_in"] = True
            session["username"] = username
            return redirect(url_for("index"))
        return redirect(url_for("register") + "?error=failed")

    error = request.args.get("error")
    error_msgs = {
        "short_username": "Användarnamnet måste vara minst 3 tecken",
        "short_password": "Lösenordet måste vara minst 6 tecken",
        "mismatch":       "Lösenorden matchar inte",
        "taken":          "Användarnamnet är redan taget",
        "failed":         "Något gick fel, försök igen",
    }
    error_msg = error_msgs.get(error, "")
    return _register_page(error_msg)


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login_page"))


@app.route("/api/stocks")
@login_required
def stocks():
    """
    Returnerar alla tier 1+2 i omgångar om 25 tickers.
    Undviker Renders 30-sekunders timeout genom att dela upp yfinance-anropen.
    """
    import json
    from flask import Response, stream_with_context

    all_items = list(TICKERS.items())
    batch_size = 25
    batches = [dict(all_items[i:i+batch_size]) for i in range(0, len(all_items), batch_size)]

    def generate():
        all_results = []
        for batch in batches:
            results = fetch_tickers(batch)
            all_results.extend(results)
        all_results.sort(key=lambda x: x["momentum_score"], reverse=True)
        yield json.dumps(all_results)

    return Response(stream_with_context(generate()), mimetype="application/json")


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

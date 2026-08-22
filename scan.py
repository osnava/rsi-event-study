"""
RSI / StochRSI window scan on BTC & ETH, 1w / 1d / 4h candles.

Data: Binance public klines (fallback Bybit), cached to ./data/*.csv
Analysis:
  1. Information content: Spearman corr(indicator_t, next-bar return) per window.
     Negative corr = oversold bounces (mean reversion); positive = momentum.
  2. Extreme-decile forward returns (descriptive, full-sample percentiles).
  3. Tradable backtest, next-open fills, 0.1% cost per side:
       MR  style: long when RSI < rolling 10th pct of itself, exit when RSI > 50.
       MOM style: long while RSI > 50, flat while RSI < 50.
  4. Stability: split sample in half, compare best/worst windows each half.

Outputs: results_ic.csv, results_bt.csv, results_stochrsi.csv, heatmap.png
"""
import json
import os
import time
import urllib.request

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
os.makedirs(DATA, exist_ok=True)

SYMBOLS = ["BTCUSDT", "ETHUSDT"]
INTERVALS = ["1w", "1d", "4h"]
RSI_WINDOWS = [2, 3, 4, 5, 6, 7, 8, 9, 10, 12, 14, 16, 18, 21, 25, 30]
COST_PER_SIDE = 0.001  # 0.1% per side (taker fee + slippage)


# ---------------------------------------------------------------- data
def http_json(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 research"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read().decode())


def fetch_binance(symbol, interval, limit=1000):
    """Newest-first pagination. Returns oldest-first DataFrame."""
    rows, end_id = [], None
    while True:
        url = (f"https://api.binance.com/api/v3/klines?symbol={symbol}"
               f"&interval={interval}&limit={limit}")
        if end_id:
            url += f"&endTime={end_id - 1}"
        batch = http_json(url)
        if not batch:
            break
        rows = batch + rows
        end_id = batch[0][0]
        if len(batch) < limit:
            break
        time.sleep(0.15)
    df = pd.DataFrame(rows, columns=["ot", "o", "h", "l", "c", "v", "ct",
                                     "qv", "n", "tbb", "tbq", "ig"])
    return clean(df)


def fetch_bybit(symbol, interval):
    imap = {"1w": "W", "1d": "D", "4h": "240"}
    rows, end = [], None
    while True:
        url = (f"https://api.bybit.com/v5/market/kline?category=spot"
               f"&symbol={symbol}&interval={imap[interval]}&limit=1000")
        if end:
            url += f"&end={end}"
        batch = http_json(url)
        if batch["retCode"] != 0:
            raise RuntimeError(batch)
        k = batch["result"]["list"]
        if not k:
            break
        rows = k + rows  # bybit returns newest-first
        end = rows[0][0]
        if len(k) < 1000:
            break
        time.sleep(0.15)
    df = pd.DataFrame(rows, columns=["ot", "o", "h", "l", "c", "v", "ct"])
    return clean(df)


def clean(df):
    idx = pd.DatetimeIndex(pd.to_datetime(df["ot"].to_numpy(), unit="ms"))
    out = pd.DataFrame({
        "open": df["o"].astype(float).to_numpy(),
        "high": df["h"].astype(float).to_numpy(),
        "low": df["l"].astype(float).to_numpy(),
        "close": df["c"].astype(float).to_numpy(),
        "volume": df["v"].astype(float).to_numpy(),
    }, index=idx)
    return out[~out.index.duplicated(keep="first")].sort_index()


def load(symbol, interval):
    path = os.path.join(DATA, f"{symbol}_{interval}.csv")
    if os.path.exists(path):
        return pd.read_csv(path, index_col=0, parse_dates=True)
    try:
        df = fetch_binance(symbol, interval)
        src = "binance"
    except Exception:
        df = fetch_bybit(symbol, interval)
        src = "bybit"
    df.to_csv(path)
    print(f"fetched {symbol} {interval} from {src}: {len(df)} bars "
          f"{df.index[0].date()} -> {df.index[-1].date()}")
    return df


# ---------------------------------------------------------------- indicators
def wilder_rsi(close, n):
    delta = close.diff()
    gain = delta.clip(lower=0.0).to_numpy()
    loss = (-delta.clip(upper=0.0)).to_numpy()
    rsi = np.full(len(close), np.nan)
    if len(close) <= n:
        return pd.Series(rsi, index=close.index)
    ag = gain[1:n + 1].mean()
    al = loss[1:n + 1].mean()
    rsi[n] = 100.0 if al == 0 else 100.0 - 100.0 / (1.0 + ag / al)
    for i in range(n + 1, len(close)):
        ag = (ag * (n - 1) + gain[i]) / n
        al = (al * (n - 1) + loss[i]) / n
        rsi[i] = 100.0 if al == 0 else 100.0 - 100.0 / (1.0 + ag / al)
    return pd.Series(rsi, index=close.index)


def stoch_rsi(close, rsi_n, stoch_n, k_sma=3, d_sma=3):
    rsi = wilder_rsi(close, rsi_n)
    lo = rsi.rolling(stoch_n).min()
    hi = rsi.rolling(stoch_n).max()
    raw = (rsi - lo) / (hi - lo)
    k = raw.rolling(k_sma).mean()
    d = k.rolling(d_sma).mean()
    return raw * 100, k * 100, d * 100


def spearman(a, b):
    m = a.notna() & b.notna()
    if m.sum() < 50:
        return np.nan, np.nan
    ra = a[m].rank()
    rb = b[m].rank()
    r = np.corrcoef(ra, rb)[0, 1]
    t = r * np.sqrt((m.sum() - 2) / max(1e-12, 1 - r ** 2))
    return r, t


def tstat(x):
    x = np.asarray(x, dtype=float)
    x = x[~np.isnan(x)]
    if len(x) < 5 or x.std(ddof=1) == 0:
        return np.nan
    return x.mean() / (x.std(ddof=1) / np.sqrt(len(x)))


# ---------------------------------------------------------------- backtest
def backtest(df, sig, cost=COST_PER_SIDE):
    """sig: bool Series, signal known at close of t -> fill at open of t+1.
    Returns (total_return, n_trades, win_rate, exposure)."""
    o, c = df["open"].to_numpy(), df["close"].to_numpy()
    s = sig.fillna(False).to_numpy()
    total, trades, wins, bars_in = 0.0, 0, 0, 0
    i = 0
    n = len(df)
    while i < n - 1:
        if s[i]:
            entry = o[i + 1]
            j = i
            while j < n - 1 and s[j]:
                j += 1
            exit_px = o[j] if j < n else c[-1]
            ret = exit_px / entry - 1 - 2 * cost
            total += ret
            trades += 1
            wins += ret > 0
            bars_in += j - i
            i = j
        else:
            i += 1
    expo = bars_in / n
    return total, trades, (wins / trades if trades else np.nan), expo


def ann_factor(interval):
    return {"1w": 52, "1d": 365, "4h": 6 * 365}[interval]


# ---------------------------------------------------------------- scan
def main():
    ic_rows, bt_rows, st_rows, stability = [], [], [], []

    for symbol in SYMBOLS:
        for interval in INTERVALS:
            df = load(symbol, interval)
            ret1 = df["close"].pct_change(fill_method=None).shift(-1)          # next-bar return
            years = (df.index[-1] - df.index[0]).days / 365.25
            bh = df["close"].iloc[-1] / df["close"].iloc[0] - 1

            for n in RSI_WINDOWS:
                rsi = wilder_rsi(df["close"], n)
                r, t = spearman(rsi, ret1)
                lo_thr = rsi.quantile(0.10)
                hi_thr = rsi.quantile(0.90)
                m = rsi.notna() & ret1.notna()
                low_ret = ret1[m & (rsi <= lo_thr)]
                high_ret = ret1[m & (rsi >= hi_thr)]

                # MR: long when RSI below rolling 10th pct, exit when > 50
                roll_lo = rsi.rolling(500, min_periods=200).quantile(0.10)
                mr_sig = (rsi < roll_lo)
                mr = backtest(df, mr_sig)
                # MOM: long while RSI > 50
                mom_sig = rsi > 50
                mom = backtest(df, mom_sig)

                ic_rows.append(dict(symbol=symbol, tf=interval, window=n,
                                    spearman=r, t=t,
                                    low10_fwd=low_ret.mean(), low10_t=tstat(low_ret),
                                    high10_fwd=high_ret.mean(), high10_t=tstat(high_ret)))
                bt_rows.append(dict(symbol=symbol, tf=interval, window=n,
                                    mr_ret=mr[0], mr_trades=mr[1], mr_win=mr[2], mr_expo=mr[3],
                                    mom_ret=mom[0], mom_trades=mom[1], mom_win=mom[2], mom_expo=mom[3]))
                # stability on daily/4h: corr sign in each half
                if interval in ("1d", "4h") and n in (2, 4, 7, 14, 21):
                    half = len(rsi) // 2
                    r1, _ = spearman(rsi.iloc[:half], ret1.iloc[:half])
                    r2, _ = spearman(rsi.iloc[half:], ret1.iloc[half:])
                    stability.append(dict(symbol=symbol, tf=interval, window=n,
                                          rho_1st_half=r1, rho_2nd_half=r2))

            for rn in (7, 14, 21):
                raw, k, d = stoch_rsi(df["close"], rn, 14)
                r, t = spearman(k, ret1)
                lo_thr = k.quantile(0.10)
                hi_thr = k.quantile(0.90)
                m = k.notna() & ret1.notna()
                low_ret = ret1[m & (k <= lo_thr)]
                high_ret = ret1[m & (k >= hi_thr)]
                st_rows.append(dict(symbol=symbol, tf=interval, rsi_len=rn,
                                    stoch_len=14, spearman=r, t=t,
                                    low10_fwd=low_ret.mean(), low10_t=tstat(low_ret),
                                    high10_fwd=high_ret.mean(), high10_t=tstat(high_ret)))

            print(f"done {symbol} {interval}: {len(df)} bars, {years:.1f}y, B&H {bh:+.0%}")

    ic = pd.DataFrame(ic_rows)
    bt = pd.DataFrame(bt_rows)
    st = pd.DataFrame(st_rows)
    sb = pd.DataFrame(stability)
    res = os.path.join(HERE, "results")
    os.makedirs(res, exist_ok=True)
    ic.to_csv(os.path.join(res, "results_ic.csv"), index=False)
    bt.to_csv(os.path.join(res, "results_bt.csv"), index=False)
    st.to_csv(os.path.join(res, "results_stochrsi.csv"), index=False)
    sb.to_csv(os.path.join(res, "results_stability.csv"), index=False)

    pd.set_option("display.width", 200)
    print("\n=== Spearman corr(RSI_t, next-bar return), avg BTC+ETH, per tf ===")
    piv = ic.groupby(["tf", "window"])[["spearman", "t"]].mean().reset_index()
    print(piv.pivot(index="window", columns="tf", values="spearman").round(4).to_string())

    print("\n=== Net-of-cost backtest (avg BTC+ETH, total return over sample) ===")
    pb = bt.groupby(["tf", "window"])[["mr_ret", "mom_ret", "mr_trades",
                                       "mr_win", "mom_win"]].mean().reset_index()
    print(pb.pivot(index="window", columns="tf", values="mr_ret").round(3).to_string())
    print("--- momentum (long RSI>50) ---")
    print(pb.pivot(index="window", columns="tf", values="mom_ret").round(3).to_string())

    print("\n=== StochRSI(14,14,3,3 vs 7/21) Spearman + decile returns ===")
    print(st.groupby(["tf", "rsi_len"])[["spearman", "low10_fwd",
                                         "high10_fwd"]].mean().round(4).to_string())

    print("\n=== Stability: 1st vs 2nd half Spearman ===")
    print(sb.round(4).to_string(index=False))

    print(f"\nsaved results to {res}/ (figures: see paper_heatmap.py)")


if __name__ == "__main__":
    main()

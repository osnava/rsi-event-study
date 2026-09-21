"""ADX/DI event study — the RSI study's methodology (scan.py / hac_tstats.py)
applied to Wilder's other 1978 oscillator, the DMI (Pine's ta.dmi).

Questions (each mirrors a question the RSI study answered):
  1. Extreme-high ADX decile: continuation or exhaustion? The chart-forum
     belief is ADX>40 = "exhaustion cue"; the RSI study found the opposite
     pattern for RSI (strength follows strength). Split by DI dominance
     because ADX is non-directional.
  2. Extreme-low ADX decile: does "no trend" predict anything?
  3. DI dominance (DI+ > DI-) as a trend filter — the analog of RSI > 50 —
     backtested net of costs, alone and gated by ADX above its own rolling
     median / 90th percentile (the requireTrend idea, adaptive form).
  4. DI crosses filtered by ADX > fixed 20 vs ADX > rolling median: does the
     classic fixed filter beat the adaptive one?
  5. Where do ADX's own quantiles sit vs the fixed 20/40 thresholds?

Windows: diLen = adxLen scanned over the same RSI_WINDOWS list for continuity.
All t-statistics for decile events cluster by spell (hac_tstats.cluster_t);
~200 cells are tested, so the Bonferroni bar |t| >= 3.5 carries over.

Outputs: results/adx_events_clustered.csv, adx_bt.csv, adx_crosses.csv,
adx_thresholds.csv, adx_stability.csv
"""
import os
import sys

# this script lives in adx_study/; the rsi-event-study machinery it reuses
# (scan.py, hac_tstats.py) sits one level up
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
import pandas as pd

import scan
from hac_tstats import cluster_t

HERE = os.path.dirname(os.path.abspath(__file__))


# ---------------------------------------------------------------- indicator
def wilder_rma(s, n):
    """Pine ta.rma (SMA seed, then recursive alpha=1/n). Leading NaNs are
    skipped: seeding starts at the first run of n consecutive valid values."""
    x = s.to_numpy(dtype=float)
    out = np.full(len(x), np.nan)
    f, run = -1, 0
    for i in range(len(x)):
        run = run + 1 if not np.isnan(x[i]) else 0
        if run == n:
            f = i
            break
    if f < 0:
        return pd.Series(out, index=s.index)
    a = x[f - n + 1:f + 1].mean()
    out[f] = a
    for i in range(f + 1, len(x)):
        a = (a * (n - 1) + x[i]) / n
        out[i] = a
    return pd.Series(out, index=s.index)


def wilder_dmi(df, di_len, adx_len):
    """Wilder DMI matching Pine ta.dmi(di_len, adx_len):
    TR/+DM/-DM smoothed by Wilder RMA -> DI+/DI-; ADX = Wilder RMA of DX."""
    h, l, c = df["high"], df["low"], df["close"]
    up = h.diff()
    dn = -l.diff()
    plus_dm = pd.Series(np.where((up > dn) & (up > 0), up, 0.0), index=df.index)
    minus_dm = pd.Series(np.where((dn > up) & (dn > 0), dn, 0.0), index=df.index)
    plus_dm.iloc[0] = np.nan
    minus_dm.iloc[0] = np.nan
    tr = pd.concat([h - l, (h - c.shift()).abs(), (l - c.shift()).abs()], axis=1).max(axis=1)
    tr.iloc[0] = np.nan

    tr_s = wilder_rma(tr, di_len)
    denom = tr_s.replace(0.0, np.nan)
    pdi = 100 * wilder_rma(plus_dm, di_len) / denom
    mdi = 100 * wilder_rma(minus_dm, di_len) / denom
    dx = (100 * (pdi - mdi).abs() / (pdi + mdi).replace(0.0, np.nan)).ffill()
    adx = wilder_rma(dx, adx_len)
    return pdi, mdi, adx


def crossover(a, b):
    return (a > b) & (a.shift(1) <= b.shift(1))


# ---------------------------------------------------------------- scan
def main():
    ev_rows, bt_rows, cross_rows, thr_rows, stab_rows = [], [], [], [], []

    for symbol in scan.SYMBOLS:
        for tf in scan.INTERVALS:
            df = scan.load(symbol, tf)
            ret1 = df["close"].pct_change(fill_method=None).shift(-1)
            bh = df["close"].iloc[-1] / df["close"].iloc[0] - 1

            for n in scan.RSI_WINDOWS:
                pdi, mdi, adx = wilder_dmi(df, n, n)

                # --- 1/2: decile event notebooks, clustered by spell ---
                sides = {
                    "lo": adx <= adx.quantile(0.10),
                    "hi": adx >= adx.quantile(0.90),
                    "hi_bull": (adx >= adx.quantile(0.90)) & (pdi > mdi),
                    "hi_bear": (adx >= adx.quantile(0.90)) & (mdi > pdi),
                }
                for side, member in sides.items():
                    ne, ns, mean, t_iid, t_cl = cluster_t(ret1, member)
                    ev_rows.append(dict(symbol=symbol, tf=tf, window=n, side=side,
                                        n_events=ne, n_spells=ns,
                                        fwd=mean, t_iid=t_iid, t_cluster=t_cl))

                # --- 3: DI-dominance trend filter, net of costs ---
                roll_med = adx.rolling(500, min_periods=200).quantile(0.50)
                roll_p90 = adx.rolling(500, min_periods=200).quantile(0.90)
                dom = pdi > mdi
                rules = {
                    "dom": dom,
                    "dom_adx_med": dom & (adx > roll_med),
                    "dom_adx_p90": dom & (adx > roll_p90),
                }
                for name, sig in rules.items():
                    net = scan.backtest(df, sig, cost=scan.COST_PER_SIDE)
                    gross = scan.backtest(df, sig, cost=0.0)
                    bt_rows.append(dict(symbol=symbol, tf=tf, window=n, rule=name,
                                        ret_net=net[0], trades=net[1],
                                        win=net[2], expo=net[3],
                                        ret_gross=gross[0], bh=bh))

                # --- 4: DI crosses, unfiltered vs fixed-20 vs adaptive ---
                bull = crossover(pdi, mdi)
                bear = crossover(mdi, pdi)
                conds = {"all": pd.Series(True, index=df.index),
                         "fixed20": adx > 20,
                         "adx_gt_med": adx > roll_med}
                for kind, cross in (("bull", bull), ("bear", bear)):
                    for cname, c in conds.items():
                        m = cross & c & ret1.notna()
                        cross_rows.append(dict(symbol=symbol, tf=tf, window=n,
                                               kind=kind, filt=cname,
                                               n=int(m.sum()),
                                               fwd=ret1[m].mean(),
                                               t=scan.tstat(ret1[m])))

                # --- stability: split-half Spearman (ADX vs next return) ---
                if tf in ("1d", "4h") and n in (2, 4, 7, 14, 21):
                    half = len(adx) // 2
                    r1, _ = scan.spearman(adx.iloc[:half], ret1.iloc[:half])
                    r2, _ = scan.spearman(adx.iloc[half:], ret1.iloc[half:])
                    stab_rows.append(dict(symbol=symbol, tf=tf, window=n,
                                          rho_1st_half=r1, rho_2nd_half=r2))

            # --- 5: where ADX(14) quantiles sit vs fixed 20/40 ---
            _, _, adx14 = wilder_dmi(df, 14, 14)
            q = adx14.quantile([0.10, 0.25, 0.50, 0.75, 0.90])
            thr_rows.append(dict(symbol=symbol, tf=tf,
                                 q10=q[0.10], q25=q[0.25], q50=q[0.50],
                                 q75=q[0.75], q90=q[0.90],
                                 pct_above_20=(adx14 > 20).mean(),
                                 pct_above_40=(adx14 > 40).mean(),
                                 mean=adx14.mean()))
            print(f"done {symbol} {tf}")

    res = os.path.join(HERE, "results")
    pd.DataFrame(ev_rows).to_csv(os.path.join(res, "adx_events_clustered.csv"), index=False)
    pd.DataFrame(bt_rows).to_csv(os.path.join(res, "adx_bt.csv"), index=False)
    pd.DataFrame(cross_rows).to_csv(os.path.join(res, "adx_crosses.csv"), index=False)
    pd.DataFrame(thr_rows).to_csv(os.path.join(res, "adx_thresholds.csv"), index=False)
    pd.DataFrame(stab_rows).to_csv(os.path.join(res, "adx_stability.csv"), index=False)

    pd.set_option("display.width", 220)

    ev = pd.DataFrame(ev_rows)
    print("\n=== ADX decile notebooks, per asset: fwd ret % after decile ===")
    for sym in scan.SYMBOLS:  # individual studies: never average across assets
        print(f"### {sym}")
        for side in ("hi", "hi_bull", "hi_bear", "lo"):
            piv = ev[ev.symbol.eq(sym) & ev.side.eq(side)].pivot_table(
                index="window", columns="tf", values="fwd")
            print(f"--- fwd ret after ADX {side} decile ---")
            print((piv.reindex(columns=["1w", "1d", "4h"]) * 100).round(3).to_string())

    bt = pd.DataFrame(bt_rows)
    print("\n=== DI-dominance trend filter, per asset, net of 0.1%/side (summed trade returns) ===")
    for sym in scan.SYMBOLS:
        print(f"### {sym}")
        for rule in ("dom", "dom_adx_med", "dom_adx_p90"):
            piv = (bt[bt.symbol.eq(sym) & bt.rule.eq(rule)]
                   .pivot_table(index="window", columns="tf", values="ret_net"))
            print(f"--- {rule} ---")
            print(piv.reindex(columns=["1w", "1d", "4h"]).round(2).to_string())

    cr = pd.DataFrame(cross_rows)
    print("\n=== DI crosses: next-bar return % by filter (per asset, window 14) ===")
    for sym in scan.SYMBOLS:
        sub = (cr[cr.symbol.eq(sym) & cr.window.eq(14)]
               .groupby(["tf", "kind", "filt"])[["fwd"]].mean())
        print(f"### {sym}")
        print((sub.unstack("filt")["fwd"] * 100).round(3).to_string())

    thr = pd.DataFrame(thr_rows)
    print("\n=== ADX(14) full-sample quantiles vs fixed 20/40 ===")
    print(thr.round(1).to_string(index=False))

    sb = pd.DataFrame(stab_rows)
    print("\n=== Stability: 1st vs 2nd half Spearman(ADX, next ret) ===")
    print(sb.round(4).to_string(index=False))


if __name__ == "__main__":
    main()

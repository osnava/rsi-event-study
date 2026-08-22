"""Cluster-robust t-stats for the decile event study.

Issue being fixed: RSI stays in a decile for consecutive candles, so decile
"events" cluster in spells; i.i.d. t-stats overstate significance. Spells =
maximal runs of consecutive candles in the decile; SE is clustered by spell.
Writes results_ic_clustered.csv (one row per symbol/tf/window/side).
"""
import os

import numpy as np
import pandas as pd

import scan

HERE = os.path.dirname(os.path.abspath(__file__))


def cluster_t(ret1, member):
    """member: bool Series (in decile). ret1: forward return Series.
    Returns (n_events, n_spells, mean, t_iid, t_cluster)."""
    valid = member & ret1.notna()
    r = ret1[valid]
    n = len(r)
    if n < 5:
        return n, 0, np.nan, np.nan, np.nan
    m = member.fillna(False)
    new_spell = m & ~m.shift(1, fill_value=False)
    sid = new_spell.cumsum()[valid]
    mean = r.mean()
    sd = r.std(ddof=1)
    t_iid = mean / (sd / np.sqrt(n))
    dev = (r - mean).groupby(sid.values).sum()      # W_s per spell
    se_cl = np.sqrt((dev ** 2).sum()) / n
    t_cl = mean / se_cl if se_cl > 0 else np.nan
    return n, sid.nunique(), mean, t_iid, t_cl


def main():
    rows = []
    for symbol in scan.SYMBOLS:
        for tf in scan.INTERVALS:
            df = scan.load(symbol, tf)
            ret1 = df["close"].pct_change(fill_method=None).shift(-1)
            for n in scan.RSI_WINDOWS:
                rsi = scan.wilder_rsi(df["close"], n)
                for side, q, op in [("lo", 0.10, "le"), ("hi", 0.90, "ge")]:
                    thr = rsi.quantile(q)
                    member = (rsi <= thr) if op == "le" else (rsi >= thr)
                    ne, ns, mean, t_iid, t_cl = cluster_t(ret1, member)
                    rows.append(dict(symbol=symbol, tf=tf, window=n, side=side,
                                     n_events=ne, n_spells=ns,
                                     fwd=mean, t_iid=t_iid, t_cluster=t_cl))
    out = pd.DataFrame(rows)
    out.to_csv(os.path.join(HERE, "results", "results_ic_clustered.csv"), index=False)

    agg = out.groupby(["tf", "side", "window"])[["n_events", "n_spells",
                                                 "t_iid", "t_cluster"]].mean()
    print("=== avg BTC+ETH: iid vs cluster-robust t (lo=oversold, hi=overbought) ===")
    piv_iid = agg.reset_index().pivot_table(index=["side", "window"], columns="tf",
                                            values="t_iid")
    piv_cl = agg.reset_index().pivot_table(index=["side", "window"], columns="tf",
                                           values="t_cluster")
    for label, piv in [("t_iid", piv_iid), ("t_cluster", piv_cl)]:
        print(f"--- {label} ---")
        print(piv.reindex(columns=["1w", "1d", "4h"]).round(2).to_string())

    # how many cells clear |t|>=2 and Bonferroni (~200 cells -> |t|>=3.5)
    per = out[out.side.eq("hi")].groupby(["symbol", "tf"])["t_cluster"].apply(
        lambda s: ((s >= 2).sum(), (s >= 3.5).sum(), len(s)))
    print("\ncells overbusted |t_cl|>=2 / >=3.5 (of 16) per symbol-tf (overbounced):")
    print(per.to_string())


if __name__ == "__main__":
    main()

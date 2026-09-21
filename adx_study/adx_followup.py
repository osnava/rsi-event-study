"""Follow-up for the ADX/DI study: compounded DI-dominance vs B&H vs RSI>50,
cost sensitivity at 4h, and a spell-masked summary of the decile t-stats
(weekly cells with < 3 spells are degenerate: 1-event spells give se~0 and
t values like 1e15, so they are reported as n/a, mirroring how the RSI study
treats weekly as indicative only)."""
import os
import sys

# adx_study/ -> parent repo provides scan.py; this dir provides adx_scan.py
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
import pandas as pd

import scan
from adx_scan import wilder_dmi

HERE = os.path.dirname(os.path.abspath(__file__))


def compounded(df, sig):
    """Compounded net-of-cost equity of a long/flat rule, in position from the
    bar after the signal (next-open approximated by next-bar close-to-close,
    same convention as followup.py)."""
    ret = df["close"].pct_change(fill_method=None)
    pos = np.concatenate(([False], sig.to_numpy()[:-1]))
    gross = ret.to_numpy()[pos]
    switches = np.abs(np.diff(pos.astype(int), prepend=0))
    costs = switches.sum() * scan.COST_PER_SIDE
    return (1 + gross).prod() - 1 - costs, int(switches.sum() // 2), pos.mean()


def main():
    print("=== compounded: DI+>DI- (dom) vs RSI>50 vs B&H, net 0.1%/side ===")
    print("=== (individual studies: every number is a single asset, never an average) ===")
    for tf in scan.INTERVALS:
        for sym in scan.SYMBOLS:
            df = scan.load(sym, tf)
            bh = df["close"].iloc[-1] / df["close"].iloc[0] - 1
            rows = []
            for n in scan.RSI_WINDOWS:
                pdi, mdi, _ = wilder_dmi(df, n, n)
                rsi = scan.wilder_rsi(df["close"], n)
                dom_eq, dom_tr, dom_ex = compounded(df, pdi > mdi)
                rsi_eq, _, rsi_ex = compounded(df, rsi > 50)
                rows.append(dict(w=n, dom=dom_eq, rsi=rsi_eq, bh=bh,
                                 dom_tr=dom_tr, dom_ex=dom_ex, rsi_ex=rsi_ex))
            agg = pd.DataFrame(rows).set_index("w")
            best = agg.dom.idxmax()
            print(f"--- {tf} {sym} (best window {best}; B&H {bh:+.1%}) ---")
            for w, r in agg.iterrows():
                print(f"len {w:>2}: DI-dom {r.dom:+8.1%} ({r.dom_tr:5.0f} trades, expo {r.dom_ex:.0%})"
                      f"   RSI>50 {r.rsi:+8.1%} (expo {r.rsi_ex:.0%})")

    print("\n=== 4h cost sensitivity: DI-dom gross vs net ===")
    for sym in scan.SYMBOLS:
        df = scan.load(sym, "4h")
        for n in (2, 14, 30):
            pdi, mdi, _ = wilder_dmi(df, n, n)
            sig = pdi > mdi
            ret = df["close"].pct_change(fill_method=None)
            pos = np.concatenate(([False], sig.to_numpy()[:-1]))
            eq_gross = (1 + ret.to_numpy()[pos]).prod() - 1
            eq_net, trades, expo = compounded(df, sig)
            print(f"{sym.split('USDT')[0]} len {n:>2}: gross {eq_gross:+6.1%}  "
                  f"net {eq_net:+6.1%}  trades {trades}  expo {expo:.0%}")

    print("\n=== decile t summary (spells >= 3 only), per asset ===")
    ev = pd.read_csv(os.path.join(HERE, "results", "adx_events_clustered.csv"))
    ok = ev[ev.n_spells >= 3]
    for sym in scan.SYMBOLS:
        print(f"### {sym}")
        for side in ("hi", "hi_bull", "hi_bear", "lo"):
            sub = ok[ok.side.eq(side) & ok.symbol.eq(sym)]
            piv_t = sub.pivot_table(index="window", columns="tf", values="t_cluster")
            piv_f = sub.pivot_table(index="window", columns="tf", values="fwd")
            print(f"--- {side}: clustered t (spells>=3) ---")
            print(piv_t.reindex(columns=["1w", "1d", "4h"]).round(2).to_string())
            print(f"--- {side}: fwd % ---")
            print((piv_f.reindex(columns=["1w", "1d", "4h"]) * 100).round(3).to_string())

    print("\n=== cells clearing bars (per asset and side, daily+4h, spells>=3) ===")
    for sym in scan.SYMBOLS:
        for side in ("hi", "hi_bull", "hi_bear", "lo"):
            sub = ok[ok.side.eq(side) & ok.tf.isin(["1d", "4h"]) & ok.symbol.eq(sym)]
            t2 = (sub.t_cluster.abs() >= 2).sum()
            t37 = (sub.t_cluster.abs() >= 3.7).sum()
            print(f"{sym.split('USDT')[0]:4s} {side:8s}: |t|>=2 in {t2:2d}/{len(sub):2d} cells, |t|>=3.7 in {t37:2d}")


if __name__ == "__main__":
    main()

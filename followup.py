"""Follow-up: compounded MOM vs B&H; 4h MR cost sensitivity; decile t-stats."""
import os
import numpy as np
import pandas as pd

import scan  # reuses load/wilder_rsi (cached CSVs)

HERE = os.path.dirname(os.path.abspath(__file__))

print("=== MOM (long while RSI>50, close-to-close, cost 0.1%/side on switches) ===")
for sym in scan.SYMBOLS:
    for tf in scan.INTERVALS:
        df = scan.load(sym, tf)
        ret = df["close"].pct_change(fill_method=None)
        bh = df["close"].iloc[-1] / df["close"].iloc[0] - 1
        for n in (2, 6, 14):
            rsi = scan.wilder_rsi(df["close"], n)
            sig = (rsi > 50).to_numpy()
            pos = np.concatenate(([False], sig[:-1]))  # in position from next bar
            gross = ret.to_numpy()[pos]
            switches = np.diff(pos.astype(int), prepend=0)
            costs = abs(switches).sum() * scan.COST_PER_SIDE
            eq = (1 + gross).prod() - 1 - costs
            print(f"{sym} {tf} RSI{n:>2}: comp {eq:+8.1%}  B&H {bh:+8.1%}  "
                  f"expo {pos.mean():.0%}")
    print()

print("=== 4h mean reversion: raw edge vs cost (entry RSI<rolling p10, exit RSI>50) ===")
for sym in scan.SYMBOLS:
    df = scan.load(sym, "4h")
    ret1 = df["close"].pct_change(fill_method=None).shift(-1)
    for n in (2, 3, 4, 5, 7):
        rsi = scan.wilder_rsi(df["close"], n)
        roll_lo = rsi.rolling(500, min_periods=200).quantile(0.10)
        sig = rsi < roll_lo
        total, trades, win, expo = scan.backtest(df, sig, cost=0.0)
        tc, tt, tw, te = scan.backtest(df, sig, cost=0.001)
        tm, tmw, _, _ = scan.backtest(df, sig, cost=0.0001)
        per = total / trades if trades else np.nan
        print(f"{sym} RSI{n}: trades {trades:4d}  avg/trade gross {per:+.3%}  "
              f"net@2bps/side {tm:+.1%}  net@10bps/side {tc:+.1%}  win {tw:.0%}")

print()
print("=== Decile event study (avg BTC+ETH): t-stats from results_ic.csv ===")
ic = pd.read_csv(os.path.join(HERE, "results", "results_ic.csv"))
agg = ic.groupby(["tf", "window"])[["low10_fwd", "low10_t", "high10_fwd", "high10_t"]].mean()
for tf in ("1w", "1d", "4h"):
    sub = agg.loc[tf].loc[[2, 3, 4, 5, 7, 14, 21]]
    print(f"--- {tf} (per-bar fwd return, %; t-stat) ---")
    for w, row in sub.iterrows():
        print(f"RSI{w:>2}: low10 {row.low10_fwd*100:+.3f}% (t={row.low10_t:+.1f})   "
              f"high10 {row.high10_fwd*100:+.3f}% (t={row.high10_t:+.1f})")

print()
print("=== ETH 4h stability rows (cut off earlier) ===")
sb = pd.read_csv(os.path.join(HERE, "results", "results_stability.csv"))
print(sb[sb["symbol"].eq("ETHUSDT") & sb["tf"].eq("4h")].to_string(index=False))

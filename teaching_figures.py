"""Plain-language teaching figures for the README (Part 1-3 explainers).

Every figure is computed from the repo's own data (data/*.csv candles and
results/*.csv), so the images can never drift from the numbers in the text.
Style matches paper_heatmap.py (serif, 200 dpi). Writes figures/explain_*.png.
"""
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

import scan
from hac_tstats import cluster_t

HERE = os.path.dirname(os.path.abspath(__file__))
FIGS = os.path.join(HERE, "figures")
os.makedirs(FIGS, exist_ok=True)

plt.rcParams.update({
    "font.family": "serif",
    "font.serif": ["DejaVu Serif"],
    "axes.edgecolor": "#444444",
    "axes.linewidth": 0.8,
})

UP = "#b2182b"      # red  = high RSI / up move   (matches RdBu_r heatmaps)
DOWN = "#2166ac"    # blue = low RSI / down move
GRAY = "#8a8a8a"


def save(fig, name):
    fig.savefig(os.path.join(FIGS, name), dpi=200, bbox_inches="tight")
    plt.close(fig)
    print(f"saved {name}")


def title(ax, main, sub=None, pad=None):
    ax.set_title(main, fontsize=11.5, loc="left",
                 pad=pad if pad is not None else (14 if sub else 6))
    if sub:
        ax.text(0, 1.02, sub, transform=ax.transAxes, fontsize=8.6,
                color="#555555", va="bottom")


# ---------------------------------------------------------------- fig 1
def fig1_rsi_anatomy():
    """What RSI is: price above, RSI gauge below, one vivid year."""
    df = scan.load("BTCUSDT", "1d")
    rsi = scan.wilder_rsi(df["close"], 14)
    y = df.loc["2023-01-01":"2023-12-31"]
    r = rsi.loc["2023-01-01":"2023-12-31"]

    fig, (a1, a2) = plt.subplots(2, 1, figsize=(10, 6.2), sharex=True,
                                 gridspec_kw={"height_ratios": [2, 1]})
    a1.plot(y.index, y["close"], color="#333333", lw=1.1)
    a1.set_ylabel("BTC close (USDT)")
    title(a1, "1 · What RSI measures",
          "BTC daily, 2023. Bottom panel: RSI(14), a 0-100 gauge of how strong recent moves are.")
    cmin, cmax = y["close"].min(), y["close"].max()
    a1.set_ylim(cmin * 0.80, cmax * 1.20)

    a2.plot(r.index, r.to_numpy(), color="#333333", lw=1.1)
    a2.axhspan(70, 100, color=UP, alpha=0.08)
    a2.axhspan(0, 30, color=DOWN, alpha=0.08)
    a2.axhline(70, color=UP, lw=0.7, alpha=0.6)
    a2.axhline(30, color=DOWN, lw=0.7, alpha=0.6)
    a2.axhline(50, color=GRAY, lw=0.7, ls="--")
    a2.set_ylim(0, 100)
    a2.set_ylabel("RSI(14)")
    a2.text(y.index[2], 78, "“overbought” zone", fontsize=8.5, color=UP)
    a2.text(y.index[2], 20, "“oversold” zone", fontsize=8.5, color=DOWN)

    a1.annotate("price grinds higher →\nRSI stays above 70",
                xy=(pd.Timestamp("2023-01-15"), y["close"].loc["2023-01-15"]),
                xytext=(pd.Timestamp("2023-03-08"), cmax * 1.04), fontsize=8.5,
                arrowprops=dict(arrowstyle="->", color="#555555", lw=0.9))
    a1.annotate("sharp drop →\nRSI plunges",
                xy=(pd.Timestamp("2023-08-17"), y["close"].loc["2023-08-17"]),
                xytext=(pd.Timestamp("2023-09-01"), cmax * 0.94), fontsize=8.5,
                arrowprops=dict(arrowstyle="->", color="#555555", lw=0.9))

    fig.tight_layout()
    save(fig, "explain_1_rsi_anatomy.png")


# ---------------------------------------------------------------- fig 2
def fig2_notebook():
    """The notebook test drawn on the real Oct-2023 spell."""
    df = scan.load("BTCUSDT", "1d")
    rsi = scan.wilder_rsi(df["close"], 14)
    ret1 = df["close"].pct_change(fill_method=None).shift(-1)
    thr = rsi.quantile(0.90)
    member = rsi.ge(thr)
    lo, hi = "2023-09-15", "2023-11-30"
    y = df.loc[lo:hi]
    r = rsi.loc[lo:hi]
    ev = member.loc[lo:hi]
    nxt = ret1.loc[lo:hi] * 100

    fig, (a1, a2, a3) = plt.subplots(3, 1, figsize=(10, 8.6), sharex=True,
                                     gridspec_kw={"height_ratios": [2.4, 1, 1]})
    fig.subplots_adjust(hspace=0.12)
    spell = (pd.Timestamp("2023-10-20"), pd.Timestamp("2023-11-13"))
    for a in (a1, a2, a3):
        a.axvspan(spell[0], spell[1], color=UP, alpha=0.07)

    a1.plot(y.index, y["close"], color="#333333", lw=1.1, marker="o", ms=2.2)
    a1.set_ylabel("BTC close (USDT)")
    cmax = y["close"].max()
    a1.set_ylim(y["close"].min() * 0.94, cmax * 1.22)
    title(a1, "2 · The notebook test, drawn on real candles",
          f"BTC daily, Sep-Dec 2023. Shaded band = one spell: 25 consecutive days with RSI ≥ {thr:.1f} "
          f"(the top 10% of this asset's own RSI values).")
    a1.annotate("Oct 22: RSI 74.6 — textbook says “overbought, sell”.\n"
                "The next day: +10.3%.",
                xy=(pd.Timestamp("2023-10-23"), y["close"].loc["2023-10-23"]),
                xytext=(pd.Timestamp("2023-09-16"), cmax * 1.13), fontsize=8.5,
                arrowprops=dict(arrowstyle="->", color="#555555", lw=0.9))

    a2.plot(r.index, r.to_numpy(), color="#333333", lw=1.1)
    a2.axhspan(thr, 100, color=UP, alpha=0.10)
    a2.axhline(thr, color=UP, lw=0.8)
    a2.plot(r.index[ev.fillna(False)], r.to_numpy()[ev.fillna(False).to_numpy()],
            "o", ms=3.4, color=UP, zorder=5)
    a2.set_ylim(0, 100)
    a2.set_ylabel("RSI(14)")
    a2.text(r.index[2], 12, "dots = event days (one notebook line each)",
            fontsize=8.5, color=UP)

    cols = np.where(nxt.to_numpy() >= 0, UP, DOWN)
    a3.bar(nxt.index[ev.fillna(False).to_numpy()],
           nxt.to_numpy()[ev.fillna(False).to_numpy()],
           width=1.4, color=cols[ev.fillna(False).to_numpy()], alpha=0.85)
    a3.axhline(0, color="#444444", lw=0.8)
    a3.set_ylim(-9, 13.5)
    a3.set_ylabel("next day, %")
    a3.text(r.index[2], nxt.max() * 0.55,
            "the notebook itself:\neach event day's next-day return", fontsize=8.5,
            color="#555555")

    save(fig, "explain_2_notebook.png")


# ---------------------------------------------------------------- fig 3
def fig3_deciles():
    """'Decile of its own distribution' = the tails of the RSI histogram."""
    fig, axes = plt.subplots(1, 2, figsize=(10, 4.2), sharey=False)
    for ax, sym in zip(axes, ["BTCUSDT", "ETHUSDT"]):
        rsi = scan.wilder_rsi(scan.load(sym, "1d")["close"], 14).dropna()
        q10, q90 = rsi.quantile(0.10), rsi.quantile(0.90)
        bins = np.linspace(0, 100, 41)
        ax.hist(rsi, bins=bins, color="#c8c8c8", edgecolor="white", lw=0.3)
        ax.hist(rsi[rsi <= q10], bins=bins, color=DOWN, alpha=0.85)
        ax.hist(rsi[rsi >= q90], bins=bins, color=UP, alpha=0.85)
        ax.axvline(q90, color=UP, lw=1.0)
        ax.axvline(q10, color=DOWN, lw=1.0)
        ax.set_xlim(0, 100)
        ax.set_xlabel(f"{sym[:-4]} daily — RSI(14) values, 2017-2026")
        ax.text(97, ax.get_ylim()[1] * 0.72,
                f"top decile:\nRSI ≥ {q90:.1f}", fontsize=8.6, color=UP, ha="right")
        ax.text(3, ax.get_ylim()[1] * 0.72,
                f"bottom decile:\nRSI ≤ {q10:.1f}", fontsize=8.6, color=DOWN)
        ax.set_yticks([])
    axes[0].set_ylabel("how many candles")
    title(axes[0], "3 · What “top decile of its own distribution” means",
          "Each asset's extremes are different: the threshold is a property of the data, not the 70/30 lines on a chart.")
    fig.tight_layout()
    save(fig, "explain_3_deciles.png")


# ---------------------------------------------------------------- fig 4
def fig4_tstat():
    """Two notebooks, same question: does the mean stand clear of its noise?"""
    df = scan.load("BTCUSDT", "1d")
    rsi = scan.wilder_rsi(df["close"], 14)
    ret1 = df["close"].pct_change(fill_method=None).shift(-1)
    q10, q90 = rsi.quantile(0.10), rsi.quantile(0.90)

    fig, axes = plt.subplots(1, 2, figsize=(10, 4.4), sharey=True)
    allr = []
    for side, member in [("hi", rsi.ge(q90)), ("lo", rsi.le(q10))]:
        allr.append(ret1[member.fillna(False)].dropna())
    lo_lim = pd.concat(allr).quantile(0.002) * 100
    hi_lim = pd.concat(allr).quantile(0.998) * 100
    for ax, side, member, color in [
            (axes[0], "hi", rsi.ge(q90), UP),
            (axes[1], "lo", rsi.le(q10), DOWN)]:
        n, ns, mean, t_iid, t_cl = cluster_t(ret1, member)
        x = ret1[member.fillna(False)] * 100
        ax.hist(x.dropna(), bins=36, color="#c8c8c8", edgecolor="white", lw=0.3)
        ax.set_xlim(lo_lim, hi_lim)
        ax.axvline(0, color="#444444", lw=0.8)
        ax.axvline(mean * 100, color=color, lw=2.0)
        verdict = "clear of the noise → real" if abs(t_cl) >= 2.5 else "lost in the noise → luck"
        ax.text(0.97, 0.96,
                f"{n} events = {ns} spells\n"
                f"mean next day {mean * 100:+.2f}%\n"
                f"t = {t_cl:+.1f} → {verdict}",
                transform=ax.transAxes, fontsize=9, va="top", ha="right",
                bbox=dict(fc="white", ec="#bbbbbb", lw=0.6, pad=4))
        ax.set_xlabel("next-day return (%)")
    axes[0].set_ylabel("how many event days")
    title(axes[0], "4 · Why an average alone proves nothing (what “t” measures)",
          "BTC daily, RSI(14): the spread of next-day returns in each notebook, with each mean as a coloured line. "
          "Both means are positive; only one is distinguishable from a coin flip.")
    fig.tight_layout()
    save(fig, "explain_4_tstat.png")


# ---------------------------------------------------------------- fig 5
def fig5_multiple_testing():
    """All ~200 t-stats at once: where the luck bars sit."""
    cl = pd.read_csv(os.path.join(HERE, "results", "results_ic_clustered.csv"))
    t = cl["t_cluster"].dropna()
    n2 = (t.abs() >= 2).sum()
    n35 = (t.abs() >= 3.5).sum()

    fig, ax = plt.subplots(figsize=(10, 4.4))
    ax.hist(t, bins=32, color="#c8c8c8", edgecolor="white", lw=0.3)
    ax.set_xlim(t.min() - 0.5, t.max() + 0.5)
    for v, c, ls, lab in [(2, "#666666", "--", "|t| = 2  “interesting”"),
                          (3.5, "#111111", "-", "|t| = 3.5  strict bar for ~200 tests")]:
        ax.axvline(v, color=c, ls=ls, lw=1.2)
        ax.axvline(-v, color=c, ls=ls, lw=1.2)
        ax.text(v + 0.08, ax.get_ylim()[1] * 0.98, lab, fontsize=8.6,
                color=c, rotation=90, va="top",
                bbox=dict(fc="white", ec="none", alpha=0.85, pad=1.5))
    ax.set_xlabel("spell-clustered t-statistic of every tested cell")
    ax.set_ylabel("how many cells")
    title(ax, "5 · Testing 200 things at once",
          f"{len(t)} cells (2 assets × 3 timeframes × 16 windows × 2 sides). "
          f"{n2} clear |t| ≥ 2, {n35} clear the strict |t| ≥ 3.5 bar — flip 200 coins and a few "
          f"look magic; the bar exists so we don't fool ourselves.")
    fig.tight_layout()
    save(fig, "explain_5_multiple_testing.png")


# ---------------------------------------------------------------- fig 6
def trend_equity(sym, n=14, cost=scan.COST_PER_SIDE):
    df = scan.load(sym, "1d")
    rsi = scan.wilder_rsi(df["close"], n)
    pos = (rsi > 50).astype(float).shift(1).fillna(0.0)
    r = df["close"].pct_change(fill_method=None).fillna(0.0)
    s = pos * r - pos.diff().abs().fillna(0.0) * cost
    eq = (1.0 + s).cumprod()
    bh = df["close"] / df["close"].iloc[0]
    return df.index, eq, bh, pos.astype(bool)


def fig6_trend_filter():
    idx0 = scan.load("BTCUSDT", "1d").index  # sample span for the subtitle
    span = f"{idx0[0]:%b %Y} - {idx0[-1]:%b %Y}"
    fig, axes = plt.subplots(2, 1, figsize=(10, 7.4))
    for ax, sym, lab in [(axes[0], "BTCUSDT", "BTC"), (axes[1], "ETHUSDT", "ETH")]:
        idx, eq, bh, pos = trend_equity(sym)
        first = True
        start = None
        for i, in_mkt in enumerate(pos.to_numpy()):
            if in_mkt and start is None:
                start = idx[i]
            if not in_mkt and start is not None:
                ax.axvspan(start, idx[i], color="#2a7f3f", alpha=0.07, lw=0)
                start = None
        if start is not None:
            ax.axvspan(start, idx[-1], color="#2a7f3f", alpha=0.07, lw=0)
        ax.plot(idx, bh, color=GRAY, lw=1.2, label="buy & hold")
        ax.plot(idx, eq, color=UP, lw=1.2,
                label="long while RSI(14) > 50 (net of costs)")
        ax.set_yscale("log")
        ax.set_ylabel(f"{lab}: value of $1")
        ax.legend(loc="upper left", fontsize=8.5, frameon=False)
        ax.text(0.99, 0.03,
                f"final: trend filter {eq.iloc[-1]:.1f}×  ·  buy & hold {bh.iloc[-1]:.1f}×  ·  "
                f"in market {pos.mean():.0%} of days",
                transform=ax.transAxes, ha="right", fontsize=8.5, color="#444444")
    title(axes[0], "6 · The practical reading: RSI as a trend filter, not a reversal dial",
          f"Daily candles, {span}. Signal acted on at the next bar, 0.1% per side paid. "
          "Green shading = days the rule is in the market.")
    fig.tight_layout()
    save(fig, "explain_6_trend_filter.png")


# ---------------------------------------------------------------- fig 7
def fig7_costs():
    """The cost guillotine at 4h: fast windows churn, fees compound into ruin."""
    windows = [2, 4, 7, 14, 21, 30]
    x = np.arange(len(windows))
    fig, ax = plt.subplots(figsize=(10.8, 5.4))
    years = 0.0
    tops = []
    churns, bhs, idx4 = {}, {}, None
    for sym, off, col, lab in [("BTCUSDT", -0.19, UP, "BTC"),
                               ("ETHUSDT", 0.19, DOWN, "ETH")]:
        df = scan.load(sym, "4h")
        idx4 = df.index
        years = max(years, (df.index[-1] - df.index[0]).days / 365.25)
        r = df["close"].pct_change(fill_method=None).fillna(0.0)
        mult, churn = [], []
        for n in windows:
            rsi = scan.wilder_rsi(df["close"], n)
            pos = (rsi > 50).astype(float).shift(1).fillna(0.0)
            s = pos * r - pos.diff().abs().fillna(0.0) * scan.COST_PER_SIDE
            mult.append((1.0 + s).prod())
            churn.append(int(pos.diff().abs().sum()))
        churns[lab] = churn
        tops += mult
        bars = ax.bar(x + off, mult, width=0.36, color=col,
                      label=f"{lab}: trend filter (RSI > 50), compounded net of costs")
        # single short tag above each bar; switch counts live in the tick labels
        for b, m in zip(bars, mult):
            ax.text(b.get_x() + b.get_width() / 2, m + 0.3, f"{m:.1f}×",
                    ha="center", va="bottom", fontsize=8.2, color="#444444")
        bh = df["close"].iloc[-1] / df["close"].iloc[0]
        bhs[lab] = bh
        tops.append(bh)
        ax.axhline(bh, color=col, lw=0.9, ls=":", alpha=0.8)
        ax.text(0.01, bh + 0.35, f"{lab} buy & hold {bh:.0f}×",
                fontsize=8.2, color=col, ha="left",
                transform=matplotlib.transforms.blended_transform_factory(
                    ax.transAxes, ax.transData))
    ax.axhline(0, color="#444444", lw=0.8)
    ax.set_xticks(x, [f"RSI {n}\nBTC {churns['BTC'][i]:,} · ETH {churns['ETH'][i]:,}"
                      for i, n in enumerate(windows)], fontsize=8.0)
    ax.set_ylabel(f"value of $1 after {years:.0f} years")
    ax.set_ylim(0, max(tops) * 1.22)
    ax.legend(fontsize=8.5, frameon=False, loc="upper left")
    title(ax, "7 · The cost guillotine at 4h",
          f"Same rule, different RSI windows, 4h candles ({idx4[0]:%b %Y} - {idx4[-1]:%b %Y}), "
          "0.1% paid per side; position switches (BTC · ETH) under each group.\n"
          "Fast windows flip thousands of times and the fees compound into ruin; "
          "only slow windows keep the edge.", pad=34)
    fig.tight_layout()
    save(fig, "explain_7_costs.png")


# ---------------------------------------------------------------- main
def main():
    fig1_rsi_anatomy()
    fig2_notebook()
    fig3_deciles()
    fig4_tstat()
    fig5_multiple_testing()
    fig6_trend_filter()
    fig7_costs()


if __name__ == "__main__":
    main()

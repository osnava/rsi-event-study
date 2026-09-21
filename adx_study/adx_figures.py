"""Figures for the ADX/DI event study (adx_scan.py / adx_followup.py).

Mirrors the RSI study's two figure sets:
  * adx_heatmap_{btc,eth,sol}.png - paper-style decile event-study heatmaps,
    ONE PER ASSET (individual studies: assets are never averaged)
  * adx_explain_1..7_*.png       - plain-language teaching figures, one per
                                   finding of adx_and_di.md

Everything is computed from the repo's own data (data/*.csv, results/adx_*.csv),
so images cannot drift from the numbers. Style matches teaching_figures.py
(serif, 200 dpi). Cells resting on fewer than 3 independent spells are masked
n/a: with 1-2 spells the clustered SE collapses and t explodes (values like
1e15), so they carry no information. SOL history starts Aug 2020 (6.1y) vs
Aug 2017 for BTC/ETH.
"""
import os
import sys
import textwrap

# adx_study/ -> parent repo provides scan.py / paper_heatmap.py; this dir
# provides adx_scan.py
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.patches import Rectangle

import scan
from adx_scan import wilder_dmi
from paper_heatmap import sample_label

HERE = os.path.dirname(os.path.abspath(__file__))
FIGS = os.path.join(HERE, "figures")
os.makedirs(FIGS, exist_ok=True)

plt.rcParams.update({
    "font.family": "serif",
    "font.serif": ["DejaVu Serif"],
    "axes.edgecolor": "#444444",
    "axes.linewidth": 0.8,
})

UP = "#b2182b"      # red  = strong trend / up move (matches RdBu_r heatmaps)
DOWN = "#2166ac"    # blue = weak trend / down move
SOLC = "#0a9a6a"    # third categorical color (SOL)
GRAY = "#8a8a8a"
BULL_DARK = "#0a9a6a"   # readable versions of the Pine indicator's DI colors
BEAR_DARK = "#c40a5a"

TFS = ["1w", "1d", "4h"]
ASSETS = [("BTCUSDT", "BTC"), ("ETHUSDT", "ETH"), ("SOLUSDT", "SOL")]
MIN_SPELLS = 3


def save(fig, name):
    fig.savefig(os.path.join(FIGS, name), dpi=200, bbox_inches="tight")
    plt.close(fig)
    print(f"saved {name}")


def title(ax, main, sub=None, pad=None):
    n_lines = 1
    if sub:
        w_in = ax.get_position().width * ax.figure.get_figwidth()
        cols = max(20, int(w_in / 0.068))
        sub = "\n".join(textwrap.fill(part, cols) for part in sub.split("\n"))
        n_lines = sub.count("\n") + 1
    ax.set_title(main, fontsize=11.5, loc="left",
                 pad=pad if pad is not None else
                 (14 + 13 * (n_lines - 1) if sub else 6))
    if sub:
        ax.text(0, 1.02, sub, transform=ax.transAxes, fontsize=8.6,
                color="#555555", va="bottom")


def equity_curve(df, sig, cost=scan.COST_PER_SIDE):
    """Compounded net-of-cost equity of a long/flat rule, in position from the
    bar after the signal (same convention as followup.py)."""
    r = df["close"].pct_change(fill_method=None).fillna(0.0)
    pos = sig.astype(float).shift(1).fillna(0.0)
    s = pos * r - pos.diff().abs().fillna(0.0) * cost
    return (1.0 + s).cumprod(), df["close"] / df["close"].iloc[0], pos.astype(bool)


# ================================================================ heatmaps
PANELS = [
    ("A", "hi", "fwd", "Strong-trend decile (top 10% of ADX)\nmean next-candle return, %"),
    ("B", "lo", "fwd", "No-trend decile (bottom 10% of ADX)\nmean next-candle return, %"),
    ("C", "hi", "t", "Strong-trend decile\nt-statistic (spell-clustered)"),
    ("D", "lo", "t", "No-trend decile\nt-statistic (spell-clustered)"),
]

CAPTION = (
    "Figure A1.  Candles in which ADX fell in the top (panel A) or bottom (panel B) decile of its "
    "own distribution were sampled and the next candle's close-to-close return averaged; panels C "
    "and D report t-statistics with standard errors clustered by decile spell. Every figure is a "
    "single asset \u2014 assets are never averaged. Cells resting on fewer than 3 independent "
    "spells are n/a (with 1-2 spells the clustered standard error collapses and t carries no "
    "information). Black borders mark |t| \u2265 2; with 288 primary cells tested across the "
    "three assets (3 \u00d7 3 \u00d7 16 \u00d7 2 sides), the Bonferroni 5% bar is |t| \u2265 3.7. "
    "Decile thresholds use the full sample, so results describe this dataset rather than a "
    "tradable rule; costs and execution are not modelled. SOL history starts Aug 2020 (6.1y) vs "
    "Aug 2017 for BTC/ETH."
)


def build_heatmap(ev, asset_line, out_name):
    ok = ev[ev.n_spells >= MIN_SPELLS]
    agg = ok.groupby(["tf", "window", "side"])[["fwd", "t_cluster"]].mean()
    windows = sorted(ev["window"].unique())

    def mat(side, col, scale=1.0):
        return (agg.xs(side, level="side")[col].unstack(0)
                .reindex(index=windows, columns=TFS) * scale)

    # a cell is n/a iff this asset had too few spells to survive the filter
    fwd = {"hi": mat("hi", "fwd", 100), "lo": mat("lo", "fwd", 100)}
    tst = {"hi": mat("hi", "t_cluster"), "lo": mat("lo", "t_cluster")}

    fig, axes = plt.subplots(2, 2, figsize=(10.5, 13.8))
    for ax, (letter, side, kind, ptitle) in zip(axes.flat, PANELS):
        m = fwd[side] if kind == "fwd" else tst[side]
        vmax = np.nanmax(np.abs(m.to_numpy(float)))
        im = ax.imshow(m.to_numpy(float), cmap="RdBu_r", vmin=-vmax, vmax=vmax,
                       aspect="auto")
        ax.set_xticks(range(len(TFS)), TFS)
        ax.set_yticks(range(len(windows)), [str(w) for w in windows])
        ax.set_xlabel("Timeframe", fontsize=10)
        ax.set_ylabel("DI / ADX length", fontsize=10)
        ax.set_title(f"({letter})  {ptitle}", fontsize=10.5, loc="left", pad=8)
        ax.tick_params(length=0)
        ax.set_xticks(np.arange(-0.5, len(TFS), 1), minor=True)
        ax.set_yticks(np.arange(-0.5, len(windows), 1), minor=True)
        ax.grid(which="minor", color="white", linewidth=1.6)
        ax.tick_params(which="minor", length=0)

        for y in range(m.shape[0]):
            for x in range(m.shape[1]):
                v = m.iloc[y, x]
                if np.isnan(v):
                    ax.text(x, y, "n/a", ha="center", va="center", fontsize=7,
                            color="#999999")
                    continue
                fmt = "%+.2f" if kind == "fwd" else "%+.1f"
                rgba = im.cmap(im.norm(v))
                lum = 0.299 * rgba[0] + 0.587 * rgba[1] + 0.114 * rgba[2]
                ax.text(x, y, fmt % v, ha="center", va="center", fontsize=9,
                        color="white" if lum < 0.5 else "black")
                if kind == "fwd" and abs(tst[side].iloc[y, x]) >= 2:
                    ax.add_patch(Rectangle((x - 0.5, y - 0.5), 1, 1, fill=False,
                                           edgecolor="black", linewidth=1.6,
                                           zorder=3))
        cb = fig.colorbar(im, ax=ax, shrink=0.8)
        cb.ax.tick_params(labelsize=8)
        cb.set_label("next-candle return (%)" if kind == "fwd" else "t-statistic",
                     fontsize=8.5)
        cb.outline.set_edgecolor("#444444")

    fig.suptitle("When ADX was at an extreme, what did price do on the very next candle?",
                 fontsize=13.5, fontweight="bold", y=0.965)
    fig.text(0.5, 0.935, asset_line, ha="center", fontsize=9, style="italic")

    plt.subplots_adjust(top=0.90, bottom=0.19, hspace=0.34, wspace=0.35)
    fig.canvas.draw()
    r = fig.canvas.get_renderer()
    px_h = fig.get_size_inches()[1] * fig.dpi
    tight_y0 = min(a.get_tightbbox(r).y0 for a in (axes.flat[2], axes.flat[3]))
    cap_text = fig.text(0.07, tight_y0 / px_h - 0.014, textwrap.fill(CAPTION, 116),
                        ha="left", va="top", fontsize=8.2)
    fig.canvas.draw()
    cap_y0 = cap_text.get_window_extent(fig.canvas.get_renderer()).y0
    fig.text(0.93, max(0.018, cap_y0 / px_h - 0.012), "Made by Oscash",
             ha="right", va="bottom", fontsize=8.5, style="italic")

    fig.savefig(os.path.join(FIGS, out_name), dpi=200)
    plt.close(fig)
    print(f"saved {out_name}")


def heatmaps():
    ev = pd.read_csv(os.path.join(HERE, "results", "adx_events_clustered.csv"))
    # individual studies: one figure per asset, never a cross-asset average
    for sym, label in ASSETS:
        span, bars = sample_label(sym)
        build_heatmap(ev[ev["symbol"].eq(sym)],
                      f"ADX decile event study  \u00b7  {sym} ({label}), "
                      f"Binance spot, {span}  \u00b7  {bars}",
                      f"adx_heatmap_{label.lower()}.png")


# ---------------------------------------------------------------- fig 1
def fig1_anatomy():
    """What ADX/DI is: price above, DI+ / DI- / ADX below, one strong trend."""
    df = scan.load("BTCUSDT", "1d")
    pdi, mdi, adx = wilder_dmi(df, 14, 14)
    lo, hi = "2023-09-01", "2024-03-31"
    y = df.loc[lo:hi]
    p, m, a = pdi.loc[lo:hi], mdi.loc[lo:hi], adx.loc[lo:hi]
    med = adx.rolling(500, min_periods=100).quantile(0.50).loc[lo:hi]
    p90 = adx.rolling(500, min_periods=100).quantile(0.90).loc[lo:hi]

    fig, (a1, a2, a3) = plt.subplots(3, 1, figsize=(10, 8.2), sharex=True,
                                     gridspec_kw={"height_ratios": [2.2, 1, 1]})
    fig.subplots_adjust(hspace=0.10)
    a1.plot(y.index, y["close"], color="#333333", lw=1.1)
    a1.set_ylabel("BTC close (USDT)")
    cmax = y["close"].max()
    a1.set_ylim(y["close"].min() * 0.86, cmax * 1.18)
    title(a1, "1 \u00b7 What ADX & DI measure",
          "BTC daily, Sep 2023 - Mar 2024. Middle panel: DI+ (green) vs DI- (pink) - which side "
          "dominates. Bottom panel: ADX - how strong the trend is, 0-100.")

    a2.fill_between(y.index, p, m, where=(p >= m), color=BULL_DARK, alpha=0.30, lw=0)
    a2.fill_between(y.index, p, m, where=(p < m), color=BEAR_DARK, alpha=0.30, lw=0)
    a2.plot(y.index, p, color=BULL_DARK, lw=1.0, label="DI+")
    a2.plot(y.index, m, color=BEAR_DARK, lw=1.0, label="DI-")
    a2.set_ylabel("DI (14)")
    a2.legend(loc="upper right", fontsize=8, frameon=False, ncol=2)
    a2.text(0.02, 0.06, "green shading = DI+ above DI- \u2192 buyers dominate",
            fontsize=8.5, color="#0a6a4a", transform=a2.transAxes, zorder=6,
            bbox=dict(fc="white", ec="none", alpha=0.85, pad=1.5))

    a3.plot(y.index, a, color="#333333", lw=1.2, label="ADX")
    a3.plot(y.index, med, color=GRAY, lw=0.9, ls="--", label="rolling median")
    a3.plot(y.index, p90, color="#444444", lw=0.9, ls=":", label="rolling 90th pct")
    a3.set_ylabel("ADX (14)")
    a3.set_ylim(0, a.max() * 1.32)
    a3.legend(loc="upper right", fontsize=8, frameon=False, ncol=3)
    a3.annotate("ADX climbing = trend strengthening;\nabove its own p90 = strong regime",
                xy=(pd.Timestamp("2023-12-20"), a.loc["2023-12-20"]),
                xytext=(pd.Timestamp("2023-09-08"), a.max() * 0.16), fontsize=8.5,
                zorder=6,
                bbox=dict(fc="white", ec="none", alpha=0.85, pad=1.5),
                arrowprops=dict(arrowstyle="->", color="#555555", lw=0.9))

    fig.tight_layout()
    save(fig, "adx_explain_1_anatomy.png")


# ---------------------------------------------------------------- fig 2
def fig2_notebook():
    """The notebook test on the longest top-decile ADX spell (BTC daily)."""
    ev = pd.read_csv(os.path.join(HERE, "results", "adx_events_clustered.csv"))
    t_all = ev.query("symbol == 'BTCUSDT' and tf == '1d' and window == 14 and side == 'hi'")[
        "t_cluster"].iloc[0]

    df = scan.load("BTCUSDT", "1d")
    _, _, adx = wilder_dmi(df, 14, 14)
    ret1 = df["close"].pct_change(fill_method=None).shift(-1)
    thr = adx.quantile(0.90)
    member = adx.ge(thr)
    sid = (member & ~member.shift(1, fill_value=False)).cumsum()
    sizes = member.groupby(sid).sum()
    best = sizes.idxmax()
    spell_start = sid[sid.eq(best)].index.min()
    spell_end = sid[sid.eq(best)].index.max()
    lo = spell_start - pd.Timedelta(days=25)
    hi = spell_end + pd.Timedelta(days=25)

    y = df.loc[lo:hi]
    a = adx.loc[lo:hi]
    evm = member.loc[lo:hi]
    nxt = ret1.loc[lo:hi] * 100
    mu = ret1[member].mean() * 100

    fig, (a1, a2, a3) = plt.subplots(3, 1, figsize=(10, 8.6), sharex=True,
                                     gridspec_kw={"height_ratios": [2.4, 1, 1]})
    fig.subplots_adjust(hspace=0.12)
    for ax in (a1, a2, a3):
        ax.axvspan(spell_start, spell_end, color=UP, alpha=0.07)

    a1.plot(y.index, y["close"], color="#333333", lw=1.1, marker="o", ms=2.2)
    a1.set_ylabel("BTC close (USDT)")
    cmax = y["close"].max()
    a1.set_ylim(y["close"].min() * 0.94, cmax * 1.20)
    title(a1, "2 \u00b7 The notebook test, drawn on real candles",
          f"BTC daily. Shaded band = the longest spell with ADX in its top decile "
          f"(\u2265 {thr:.1f}): {int(sizes.max())} consecutive candles. The folk reading says "
          f"\u201cstrong trend \u2192 exhaustion\u201d; the study measures what actually happened next.")

    a2.plot(a.index, a.to_numpy(), color="#333333", lw=1.1)
    a2.axhspan(thr, max(100, a.max() * 1.06), color=UP, alpha=0.10)
    a2.axhline(thr, color=UP, lw=0.8)
    a2.plot(a.index[evm.fillna(False)], a.to_numpy()[evm.fillna(False).to_numpy()],
            "o", ms=3.4, color=UP, zorder=5)
    a2.set_ylim(0, 100)
    a2.set_ylabel("ADX(14)")
    a2.text(a.index[2], 4, "dots = event candles (one notebook line each)",
            fontsize=8.5, color=UP)
    a2.text(0.98, 0.96,
            f"average next-candle return across ALL top-decile BTC daily events: "
            f"{mu:+.2f}%  (spell-clustered t = {t_all:+.1f})",
            transform=a2.transAxes, fontsize=8.5, color="#444444", va="top", ha="right",
            bbox=dict(fc="white", ec="#bbbbbb", lw=0.6, pad=3))

    cols = np.where(nxt.to_numpy() >= 0, UP, DOWN)
    sel = evm.fillna(False).to_numpy()
    a3.bar(nxt.index[sel], nxt.to_numpy()[sel], width=1.4,
           color=cols[sel], alpha=0.85)
    a3.axhline(0, color="#444444", lw=0.8)
    a3.set_ylabel("next candle, %")

    save(fig, "adx_explain_2_notebook.png")


# ---------------------------------------------------------------- fig 3
def fig3_own_distribution():
    """ADX's own distribution vs the fixed 20/40 lines (finding 7), per asset."""
    fig, axes = plt.subplots(3, 3, figsize=(11.5, 9.6))
    for row, (sym, lab) in enumerate(ASSETS):
        for col, tf in enumerate(TFS):
            ax = axes[row, col]
            _, _, adx = wilder_dmi(scan.load(sym, tf), 14, 14)
            a = adx.dropna()
            q10, q50, q90 = a.quantile(0.10), a.quantile(0.50), a.quantile(0.90)
            bins = np.linspace(0, max(70, a.max() * 1.02), 46)
            ax.hist(a, bins=bins, color="#c8c8c8", edgecolor="white", lw=0.3)
            ax.hist(a[a <= q10], bins=bins, color=DOWN, alpha=0.85)
            ax.hist(a[a >= q90], bins=bins, color=UP, alpha=0.85)
            ax.axvline(20, color="#666666", ls="--", lw=1.1)
            ax.axvline(40, color="#222222", lw=1.1)
            ax.axvline(q50, color="#0a6a4a", lw=1.0, ls=":")
            ax.axvline(q90, color=UP, lw=1.0)
            ax.set_xlim(0, bins[-1])
            ax.set_yticks([])
            ax.text(0.98, 0.97,
                    f"20 \u2192 {100 * (a <= 20).mean():.0f}% of bars below\n"
                    f"40 \u2192 {100 * (a <= 40).mean():.0f}% below\n"
                    f"median {q50:.0f} \u00b7 p90 {q90:.0f}",
                    transform=ax.transAxes, fontsize=7.8, va="top", ha="right",
                    bbox=dict(fc="white", ec="#bbbbbb", lw=0.6, pad=3))
            if row == 2:
                ax.set_xlabel(f"{tf} \u2014 ADX(14)", fontsize=9)
            if col == 0:
                ax.set_ylabel(f"{lab}:\nhow many candles", fontsize=9)
    title(axes[0, 0], "3 \u00b7 The classic 20/40 lines are not the same place on any chart",
          "Distribution of ADX(14) per asset (rows) and timeframe (columns), 2017-2026 (SOL from "
          "2020). Dashed/solid black = the fixed 20/40 thresholds; dotted green = ADX's own "
          "median, red = its 90th percentile.")
    fig.tight_layout()
    save(fig, "adx_explain_3_own_distribution.png")


# ---------------------------------------------------------------- fig 4
def fig4_direction_split():
    """Top-decile ADX split by DI dominance vs the no-trend notebook, per asset."""
    ev = pd.read_csv(os.path.join(HERE, "results", "adx_events_clustered.csv"))
    ok = ev[ev.n_spells >= MIN_SPELLS]
    sub = (ok[ok.window.eq(14)]
           .groupby(["symbol", "tf", "side"])[["fwd", "t_cluster"]].mean())

    sides = [("hi_bull", "strong trend,\nDI+ on top", BULL_DARK),
             ("hi_bear", "strong trend,\nDI- on top", BEAR_DARK),
             ("lo", "no-trend decile\n(bottom 10%)", GRAY)]
    fig, axes = plt.subplots(3, 3, figsize=(11.5, 10.4))
    for r, (sym, lab) in enumerate(ASSETS):
        for c, tf in enumerate(TFS):
            ax = axes[r, c]
            vals, ts, cols = [], [], []
            for side, _, col in sides:
                if (sym, tf, side) in sub.index:
                    vals.append(sub.xs((sym, tf, side)).fwd * 100)
                    ts.append(sub.xs((sym, tf, side)).t_cluster)
                else:
                    vals.append(np.nan)
                    ts.append(np.nan)
                cols.append(col)
            finite = [v for v in vals if not np.isnan(v)] or [0.05]
            lo_v, hi_v = min(finite + [0.0]), max(finite + [0.0])
            rng = max(hi_v - lo_v, 0.12)
            bars = ax.bar(range(3), np.nan_to_num(vals), color=cols, alpha=0.9,
                          width=0.62)
            for b, v, t in zip(bars, vals, ts):
                if np.isnan(v):
                    ax.text(b.get_x() + b.get_width() / 2, lo_v + rng * 0.03, "n/a",
                            ha="center", fontsize=7.5, color="#999999", va="bottom")
                    continue
                off = rng * 0.06
                ax.text(b.get_x() + b.get_width() / 2, v + (off if v >= 0 else -off),
                        f"{v:+.2f}%\nt={t:+.1f}", ha="center",
                        va="bottom" if v >= 0 else "top", fontsize=7.4, color="#444444")
            ax.axhline(0, color="#444444", lw=0.8)
            ax.set_xticks(range(3), [s[1] for s in sides], fontsize=7.5)
            ax.set_ylim(lo_v - rng * 0.42, hi_v + rng * 0.42)
            if r == 0:
                ax.set_title(f"{tf} candles", fontsize=10)
            if c == 0:
                ax.set_ylabel(f"{lab}:\nnext-candle return (%)", fontsize=9)
    fig.suptitle("4 \u00b7 Strong trends continue; any bounce hides in strong downtrends",
                 fontsize=13, fontweight="bold", x=0.02, ha="left", y=0.985)
    fig.text(0.02, 0.965,
             textwrap.fill(
                 "One panel per asset (rows) and timeframe (columns) \u2014 individual studies, "
                 "assets never averaged. Event study on ADX's own deciles, length 14. High ADX "
                 "with DI+ dominant \u2192 price keeps rising; with DI- dominant any bounce "
                 "lives on the daily candles; at 4h \u2248 nothing. Low ADX \u2192 nothing.",
                 150),
             fontsize=8.6, color="#555555", va="top")
    fig.tight_layout(rect=(0, 0, 1, 0.90))
    save(fig, "adx_explain_4_direction_split.png")


# ---------------------------------------------------------------- fig 5
def fig5_gating_and_crosses():
    """Per asset: gating the DI rule by ADX hurts (top row); DI crosses carry
    no signal (bottom row)."""
    # precompute the DMI and rolling gates once per (symbol, timeframe)
    dmi_cache = {}
    for sym, _ in ASSETS:
        for tf in TFS:
            df = scan.load(sym, tf)
            pdi, mdi, adx = wilder_dmi(df, 14, 14)
            dom = pdi > mdi
            dmi_cache[(sym, tf)] = (
                df, dom, adx,
                adx.rolling(500, min_periods=200).quantile(0.50),
                adx.rolling(500, min_periods=200).quantile(0.90))

    rules = [("dom", "DI+ > DI- (no gate)", "#0a9a6a"),
             ("med", "+ gate: ADX > its median", "#e0a030"),
             ("p90", "+ gate: ADX > its p90", "#8a5a00")]
    cr = pd.read_csv(os.path.join(HERE, "results", "adx_crosses.csv"))
    cross_sub = (cr[cr.window.eq(14)]
                 .groupby(["symbol", "tf", "kind", "filt"])[["fwd"]].mean().reset_index())
    filts = [("all", "#8a8a8a", "no filter"),
             ("fixed20", "#e0a030", "ADX > 20 (classic)"),
             ("adx_gt_med", "#0a9a6a", "ADX > its median")]

    fig, axes = plt.subplots(2, 3, figsize=(14.6, 9.4))
    x = np.arange(len(TFS))
    w = 0.26
    for c, (sym, lab) in enumerate(ASSETS):
        # top row: gating costs return
        ax = axes[0, c]
        tops = []
        for i, (rule, rlab, col) in enumerate(rules):
            vals = []
            for tf in TFS:
                df, dom, adx, rmed, rp90 = dmi_cache[(sym, tf)]
                sig = {"dom": dom, "med": dom & (adx > rmed),
                       "p90": dom & (adx > rp90)}[rule]
                eq, _, _ = equity_curve(df, sig)
                vals.append(eq.iloc[-1])
            tops += vals
            ax.bar(x + (i - 1) * w, vals, width=w, color=col, alpha=0.92,
                   label=rlab if c == 0 else None)
            for xi, v in zip(x + (i - 1) * w, vals):
                ax.text(xi, v * 1.12, f"{v:.0f}\u00d7", ha="center", va="bottom",
                        fontsize=7.2, color="#444444")
        ax.set_yscale("log")
        ax.set_ylim(max(0.5, min(tops) * 0.4), max(tops) * 9)
        ax.set_xticks(x, TFS)
        ax.set_title(f"{lab} \u2014 gating the DI rule throws away return", fontsize=9.5)
        if c == 0:
            ax.set_ylabel("value of $1 after the sample, net (log)")
            ax.legend(fontsize=7.5, frameon=False, loc="upper right")

        # bottom row: DI crosses under three filters
        ax = axes[1, c]
        groups = [(tf, kind) for tf in TFS for kind in ("bull", "bear")]
        xg = np.arange(len(groups))
        vals_all = []
        for i, (f, col, flab) in enumerate(filts):
            vals = []
            for tf, kind in groups:
                row = cross_sub[(cross_sub.symbol.eq(sym)) & (cross_sub.tf.eq(tf))
                                & (cross_sub.kind.eq(kind)) & (cross_sub.filt.eq(f))]
                vals.append(row.fwd.iloc[0] * 100 if len(row) else np.nan)
            vals_all += [v for v in vals if not np.isnan(v)]
            ax.bar(xg + (i - 1) * 0.26, np.nan_to_num(vals), width=0.26, color=col,
                   alpha=0.92, label=flab if c == 0 else None)
            for xi, v in zip(xg + (i - 1) * 0.26, vals):
                if not np.isnan(v):
                    ax.text(xi, v + (0.08 if v >= 0 else -0.08), f"{v:+.1f}",
                            ha="center", va="bottom" if v >= 0 else "top",
                            fontsize=6.2, color="#444444", rotation=90)
        ax.axhline(0, color="#444444", lw=0.8)
        # headroom so the rotated labels of the extreme bars stay inside
        m = max((abs(v) for v in vals_all), default=1.0)
        ax.set_ylim(-m * 1.45, m * 1.45)
        ax.set_xticks(xg, [f"{tf}\n{kind}" for tf, kind in groups], fontsize=7.0)
        ax.set_title(f"{lab} \u2014 DI crosses are not a signal", fontsize=9.5)
        if c == 0:
            ax.set_ylabel("mean next-candle return after a DI cross (%)")
            ax.legend(fontsize=7.5, frameon=False, loc="upper right")

    fig.suptitle("5 \u00b7 Filters that do not help: ADX gating and DI crosses",
                 fontsize=13, fontweight="bold", x=0.02, ha="left", y=0.99)
    fig.text(0.02, 0.972,
             textwrap.fill(
                 "Individual studies, one column per asset, never averaged. Top: adding an ADX "
                 "gate to the DI+ > DI- rule lowers the compounded net-of-cost multiple \u2014 "
                 "the gate sits out exactly the early-trend bars where the move is made. Bottom: "
                 "next-candle returns after DI crosses are small and sign-unstable under every "
                 "filter choice. Length 14, 0.1% per side.", 155),
             fontsize=8.6, color="#555555", va="top")
    fig.tight_layout(rect=(0, 0, 1, 0.93))
    save(fig, "adx_explain_5_gating.png")


# ---------------------------------------------------------------- fig 6
def fig6_trend_filter():
    """DI+ > DI- vs RSI>50 vs buy & hold, per asset, daily and 4h."""
    fig, axes = plt.subplots(3, 2, figsize=(12.4, 11.2))
    for row, (sym, lab) in enumerate(ASSETS):
        for col, tf in enumerate(TFS[1:]):
            ax = axes[row, col]
            df = scan.load(sym, tf)
            pdi, mdi, _ = wilder_dmi(df, 14, 14)
            rsi = scan.wilder_rsi(df["close"], 14)
            eq, bh, pos = equity_curve(df, pdi > mdi)
            eq2, _, _ = equity_curve(df, rsi > 50)
            start = None
            for i, in_mkt in enumerate(pos.to_numpy()):
                if in_mkt and start is None:
                    start = df.index[i]
                if not in_mkt and start is not None:
                    ax.axvspan(start, df.index[i], color="#2a7f3f", alpha=0.06, lw=0)
                    start = None
            if start is not None:
                ax.axvspan(start, df.index[-1], color="#2a7f3f", alpha=0.06, lw=0)
            ax.plot(df.index, bh, color=GRAY, lw=1.1, label="buy & hold")
            ax.plot(df.index, eq2, color="#7a4d00", lw=1.0, label="long while RSI(14) > 50")
            ax.plot(df.index, eq, color=UP, lw=1.3, label="long while DI+ > DI-")
            ax.set_yscale("log")
            ax.set_ylabel(f"{lab} {tf}: value of $1")
            ax.legend(loc="upper left", fontsize=7.6, frameon=False)
            ax.text(0.99, 0.03,
                    f"DI rule {eq.iloc[-1]:.0f}\u00d7 \u00b7 RSI>50 {eq2.iloc[-1]:.0f}\u00d7 \u00b7 "
                    f"B&H {bh.iloc[-1]:.0f}\u00d7 \u00b7 in market {pos.mean():.0%}",
                    transform=ax.transAxes, ha="right", fontsize=7.6, color="#444444")
    title(axes[0, 0], "6 \u00b7 The practical reading: DI dominance as a trend filter",
          "One row per asset (individual studies). Signal acted on at the next bar, 0.1% per "
          "side paid; BTC/ETH from Aug 2017, SOL from Aug 2020. Green shading = bars the DI "
          "rule is in the market.")
    fig.tight_layout()
    save(fig, "adx_explain_6_trend_filter.png")


# ---------------------------------------------------------------- fig 7
def fig7_costs():
    """The contrast with RSI at 4h: even fast DI windows survive costs."""
    windows = [2, 4, 7, 14, 21, 30]
    x = np.arange(len(windows))
    fig, ax = plt.subplots(figsize=(11.2, 5.6))
    idx4 = None
    tops, trades_map = [], {}
    groups = [("BTCUSDT", -0.25, UP, "BTC"),
              ("ETHUSDT", 0.0, DOWN, "ETH"),
              ("SOLUSDT", 0.25, SOLC, "SOL")]
    for sym, off, col, lab in groups:
        df = scan.load(sym, "4h")
        idx4 = df.index if idx4 is None else idx4
        r = df["close"].pct_change(fill_method=None).fillna(0.0)
        mult, trades = [], []
        for n in windows:
            pdi, mdi, _ = wilder_dmi(df, n, n)
            pos = (pdi > mdi).astype(float).shift(1).fillna(0.0)
            s = pos * r - pos.diff().abs().fillna(0.0) * scan.COST_PER_SIDE
            mult.append((1.0 + s).prod())
            trades.append(int(pos.diff().abs().sum() // 2))
        trades_map[lab] = trades
        tops += mult
        bars = ax.bar(x + off, mult, width=0.24, color=col,
                      label=f"{lab}: long while DI+ > DI-, net of costs")
        for b, m in zip(bars, mult):
            ax.text(b.get_x() + b.get_width() / 2, m + 0.4, f"{m:.0f}\u00d7",
                    ha="center", va="bottom", fontsize=7.6, color="#444444")
        bh = df["close"].iloc[-1] / df["close"].iloc[0]
        tops.append(bh)
        ax.axhline(bh, color=col, lw=0.9, ls=":", alpha=0.8)
        ax.text(0.01, bh * 1.15, f"{lab} buy & hold {bh:.0f}\u00d7", fontsize=7.8,
                color=col, ha="left",
                transform=matplotlib.transforms.blended_transform_factory(
                    ax.transAxes, ax.transData))

    def trades_txt(v):
        return f"{v / 1000:.1f}k" if v >= 1000 else str(v)

    ax.axhline(0, color="#444444", lw=0.8)
    # one compact 4-line block per group: window + per-asset trade counts
    ax.set_xticks(x, [f"len {n}\n" + "\n".join(
        f"{lab[0]} {trades_txt(trades_map[lab][i])}" for _, _, _, lab in groups)
        for i, n in enumerate(windows)], fontsize=7.0)
    ax.set_ylabel(f"value of $1 after {(idx4[-1] - idx4[0]).days / 365.25:.0f} years (4h candles)")
    ax.set_ylim(0, max(tops) * 1.22)
    ax.legend(fontsize=8.2, frameon=False, loc="upper left")
    title(ax, "7 \u00b7 The 4h cost test the DI rule survives (RSI's did not)",
          f"4h candles, {idx4[0]:%b %Y} - {idx4[-1]:%b %Y} (SOL from Aug 2020), 0.1% paid per "
          "side; trade counts under each group (B=BTC, E=ETH, S=SOL). RSI(2) at 4h churned "
          "~6,700 switches into ruin on BTC; the DI rule flips far less often and stays "
          "profitable even at length 2 \u2014 though slower windows still do better.", pad=46)
    fig.tight_layout()
    save(fig, "adx_explain_7_costs.png")


# ---------------------------------------------------------------- main
def main():
    heatmaps()
    fig1_anatomy()
    fig2_notebook()
    fig3_own_distribution()
    fig4_direction_split()
    fig5_gating_and_crosses()
    fig6_trend_filter()
    fig7_costs()


if __name__ == "__main__":
    main()

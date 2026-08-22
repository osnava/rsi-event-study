"""Research-paper-style RSI decile event-study heatmaps.

Builds one figure per asset (and optionally the combined average):
  heatmap_btc.png / heatmap_eth.png / heatmap.png (BTC+ETH average)
"""
import os
import textwrap

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.patches import Rectangle

HERE = os.path.dirname(os.path.abspath(__file__))

plt.rcParams.update({
    "font.family": "serif",
    "font.serif": ["DejaVu Serif"],
    "axes.edgecolor": "#444444",
    "axes.linewidth": 0.8,
})

TFS = ["1w", "1d", "4h"]

PANELS = [
    ("A", "low", "fwd", "Oversold decile (bottom 10% of RSI)\nmean next-candle return, %"),
    ("B", "high", "fwd", "Overbought decile (top 10% of RSI)\nmean next-candle return, %"),
    ("C", "low", "t", "Oversold decile\nt-statistic (spell-clustered)"),
    ("D", "high", "t", "Overbought decile\nt-statistic (spell-clustered)"),
]

CAPTION = (
    "Figure 1.  Candles in which RSI fell in the bottom (panel A) or top (panel B) decile of its "
    "own distribution were sampled and the next candle's close-to-close return averaged; panels C "
    "and D report t-statistics with standard errors clustered by decile spell (runs of consecutive "
    "candles in the decile), correcting the overstatement of significance caused by clustered "
    "events. Black borders mark |t| \u2265 2; with about 200 cells tested, a Bonferroni 5% "
    "threshold requires |t| \u2265 3.5 (Harvey, Liu & Zhu 2016 argue for t > 3 hurdles). Decile "
    "thresholds use the full sample, so results describe this dataset rather than a tradable rule; "
    "costs and execution are not modelled. Weekly cells average 46 events but only about 13 "
    "independent spells \u2014 indicative only."
)
REFS = (
    "References:  Wilder (1978), New Concepts in Technical Trading Systems  \u00b7  Connors & "
    "Alvarez (2009), Short Term Trading Strategies That Work  \u00b7  Zatwarnicki et al. (2023), "
    "Sensors 23(3):1664  \u00b7  Sullivan, Timmermann & White (1999), J. Finance 54(5)  \u00b7  "
    "Harvey, Liu & Zhu (2016), Rev. Financ. Stud. 29(1)  \u00b7  Newey & West (1987), "
    "Econometrica 55(3)."
)


def build(sub_ic, sub_cl, asset_line, out_name, caption=CAPTION):
    agg = sub_ic.groupby(["tf", "window"])[["low10_fwd", "high10_fwd"]].mean()
    windows = sorted(sub_ic["window"].unique())

    def matrix(col, scale):
        return agg[col].unstack(0).reindex(index=windows, columns=TFS) * scale

    fwd = {"low": matrix("low10_fwd", 100), "high": matrix("high10_fwd", 100)}

    def tmat(side):
        p = sub_cl[sub_cl["side"].eq(side)].pivot_table(
            index="window", columns="tf", values="t_cluster")
        return p.reindex(index=windows, columns=TFS)

    tst = {"low": tmat("lo"), "high": tmat("hi")}

    fig, axes = plt.subplots(2, 2, figsize=(10.5, 13.8))
    for ax, (letter, side, kind, title) in zip(axes.flat, PANELS):
        m = fwd[side] if kind == "fwd" else tst[side]
        vmax = np.nanmax(np.abs(m.to_numpy(float)))
        im = ax.imshow(m.to_numpy(float), cmap="RdBu_r", vmin=-vmax, vmax=vmax,
                       aspect="auto")
        ax.set_xticks(range(len(TFS)), TFS)
        ax.set_yticks(range(len(windows)), [str(w) for w in windows])
        ax.set_xlabel("Timeframe", fontsize=10)
        ax.set_ylabel("RSI lookback window", fontsize=10)
        ax.set_title(f"({letter})  {title}", fontsize=10.5, loc="left", pad=8)
        ax.tick_params(length=0)
        ax.set_xticks(np.arange(-0.5, len(TFS), 1), minor=True)
        ax.set_yticks(np.arange(-0.5, len(windows), 1), minor=True)
        ax.grid(which="minor", color="white", linewidth=1.6)
        ax.tick_params(which="minor", length=0)

        for y in range(m.shape[0]):
            for x in range(m.shape[1]):
                v = m.iloc[y, x]
                if np.isnan(v):
                    continue
                fmt = "%+.2f" if kind == "fwd" else "%+.1f"
                ax.text(x, y, fmt % v, ha="center", va="center", fontsize=9)
                if kind == "fwd" and abs(tst[side].iloc[y, x]) >= 2:
                    ax.add_patch(Rectangle((x - 0.5, y - 0.5), 1, 1, fill=False,
                                           edgecolor="black", linewidth=1.5))
        cb = fig.colorbar(im, ax=ax, shrink=0.8)
        cb.ax.tick_params(labelsize=8)
        cb.set_label("next-candle return (%)" if kind == "fwd" else "t-statistic",
                     fontsize=8.5)
        cb.outline.set_edgecolor("#444444")

    fig.suptitle("When RSI was at an extreme, what did price do on the very next candle?",
                 fontsize=13.5, fontweight="bold", y=0.965)
    fig.text(0.5, 0.935, asset_line, ha="center", fontsize=9, style="italic")

    plt.subplots_adjust(top=0.90, bottom=0.19, hspace=0.34, wspace=0.35)

    # Anchor the caption below the bottom panels' FULL extent (axis labels and
    # colorbars included), so it can never collide with panels C and D.
    fig.canvas.draw()
    r = fig.canvas.get_renderer()
    px_h = fig.get_size_inches()[1] * fig.dpi
    tight_y0 = min(a.get_tightbbox(r).y0 for a in (axes.flat[2], axes.flat[3]))
    cap_text = fig.text(0.07, tight_y0 / px_h - 0.014, textwrap.fill(caption, 116),
                        ha="left", va="top", fontsize=8.2)
    fig.canvas.draw()
    cap_y0 = cap_text.get_window_extent(fig.canvas.get_renderer()).y0
    refs_text = fig.text(0.07, cap_y0 / px_h - 0.010,
                         textwrap.fill(REFS, 116), ha="left", va="top", fontsize=7.6,
                         color="#333333")
    fig.canvas.draw()
    refs_y0 = refs_text.get_window_extent(fig.canvas.get_renderer()).y0
    fig.text(0.93, max(0.018, refs_y0 / px_h - 0.012), "Made by Oscash",
             ha="right", va="bottom", fontsize=8.5, style="italic")

    fig.savefig(os.path.join(HERE, "figures", out_name), dpi=200)
    print(f"saved {out_name}")
    return fig


def main():
    ic = pd.read_csv(os.path.join(HERE, "results", "results_ic.csv"))
    cl = pd.read_csv(os.path.join(HERE, "results", "results_ic_clustered.csv"))
    bars = "471 weekly / 3,293 daily / 19,736 4h candles"
    figs = []
    for sym, label in [("BTCUSDT", "BTC"), ("ETHUSDT", "ETH")]:
        figs.append(build(ic[ic["symbol"].eq(sym)], cl[cl["symbol"].eq(sym)],
                          f"RSI decile event study  \u00b7  {sym} ({label}), "
                          f"Binance spot, August 2017 \u2013 August 2026  \u00b7  {bars}",
                          f"heatmap_{label.lower()}.png"))
    figs.append(build(ic, cl, f"RSI decile event study  \u00b7  BTC & ETH average, Binance spot, "
                              f"August 2017 \u2013 August 2026  \u00b7  {bars} per asset",
                      "heatmap.png"))
    return figs


if __name__ == "__main__":
    main()

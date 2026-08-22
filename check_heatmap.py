"""Verify paper-style heatmaps: cell labels fit, footer blocks inside and non-overlapping."""
import matplotlib
matplotlib.use("Agg")

import paper_heatmap as ph

for fig in ph.main():
    fig.canvas.draw()
    r = fig.canvas.get_renderer()
    W, H = fig.get_size_inches() * fig.dpi
    ok = True
    boxes = {}
    margin = 0.010 * H  # every footer text block must clear the edges by this much
    for t in fig.texts:
        bb = t.get_window_extent(r)
        boxes[t.get_text()[:28]] = bb
        if not (bb.x0 >= margin and bb.y0 >= margin and bb.x1 <= W - margin
                and bb.y1 <= H - margin):
            ok = False
            print("  TOO CLOSE TO / OUT OF BOUNDS:", repr(t.get_text()[:28]))
    names = list(boxes)
    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            if boxes[names[i]].overlaps(boxes[names[j]]):
                ok = False
                print("  OVERLAP:", names[i], "<->", names[j])
    ax_bottom = min(a.get_tightbbox(r).y0 for a in fig.axes if a.get_tightbbox(r) is not None)
    cap_top = max(bb.y1 for n, bb in boxes.items() if n.startswith("Figure"))
    gap = ax_bottom - cap_top
    if gap < 0.005 * H:
        ok = False
        print(f"  caption collides with panels C/D (gap {gap:.0f}px)")
    bad = n = 0
    for ax in fig.axes:
        for t in ax.texts:
            n += 1
            tb = t.get_window_extent(r)
            x, y = t.get_position()
            p0 = ax.transData.transform((x - 0.5, y - 0.5))
            p1 = ax.transData.transform((x + 0.5, y + 0.5))
            if tb.width >= abs(p1[0] - p0[0]) * 0.96 or tb.height >= abs(p1[1] - p0[1]) * 0.96:
                bad += 1
    subtitle = [t.get_text() for t in fig.texts if "event study" in t.get_text()][0]
    tag = "BTC" if "BTCUSDT (BTC)" in subtitle else "ETH" if "ETHUSDT" in subtitle else "AVG"
    print(f"{tag}: footer {'PASS' if ok else 'FAIL'}, cell labels {n} checked, {bad} problems")

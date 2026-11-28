#!/usr/bin/env python3
"""Control plots: stacked backgrounds, signal lines and (if --unblind) data, for every
histogram and category of an era.

Writes plots/<era>/<category>/<histogram>.png (+ index.html with all plots).

Example:
    python3 scripts/plot_stack.py --era 2022
    python3 scripts/plot_stack.py --era 2022 --unblind --outdir /eos/user/s/snandan/www/hnl/fw
"""
import argparse
import os
import pickle
import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from hnl.bkg import estimate_backgrounds  # noqa: E402
from hnl.config import FW_DIR  # noqa: E402


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--era", required=True)
    p.add_argument("--unblind", action="store_true")
    p.add_argument("--log", action="store_true", help="log y axis")
    p.add_argument("--results", default=os.path.join(FW_DIR, "results"))
    p.add_argument("--outdir", default=os.path.join(FW_DIR, "plots"))
    args = p.parse_args()

    with open(os.path.join(args.results, args.era, "merged.pkl"), "rb") as f:
        merged = pickle.load(f)
    any_sample = next(iter(merged.values()))
    hnames = list(any_sample["hists"])
    cats = sorted({c for s in merged.values() for h in s["hists"].values() for c in h.axes["category"]})

    for cat in cats:
        odir = os.path.join(args.outdir, args.era, cat)
        os.makedirs(odir, exist_ok=True)
        for hname in hnames:
            bkg = estimate_backgrounds(merged, hname, [cat])
            fig, ax = plt.subplots(figsize=(6, 4.5))
            axis = any_sample["hists"][hname].axes[1]
            edges = axis.edges
            bottom = np.zeros(len(edges) - 1)
            for b, hs in bkg.items():
                vals = hs[cat].values()
                ax.stairs(bottom + vals, edges, baseline=bottom, fill=True, alpha=0.7, label=b)
                bottom = bottom + vals
            for name, s in merged.items():
                h = s["hists"][hname]
                if s["kind"] == "signal" and cat in list(h.axes["category"]):
                    ax.stairs(h[cat, :].values(), edges, lw=2, label=name)
            if args.unblind:
                data = [s["hists"][hname] for s in merged.values() if s["kind"] == "data"]
                data = [h[cat, :].values() for h in data if cat in list(h.axes["category"])]
                if data:
                    d = np.sum(data, axis=0)
                    ax.errorbar(axis.centers, d, yerr=np.sqrt(d), fmt="ko", ms=3, label="data")
            ax.set_xlabel(axis.label)
            ax.set_ylabel("Events")
            ax.set_title(f"{args.era}, {cat}")
            if args.log:
                ax.set_yscale("log")
            ax.legend(fontsize=7)
            fig.tight_layout()
            fig.savefig(os.path.join(odir, f"{hname}.png"), dpi=120)
            plt.close(fig)
        imgs = "\n".join(f'<a href="{h}.png"><img src="{h}.png" width="32%"></a>' for h in hnames)
        with open(os.path.join(odir, "index.html"), "w") as f:
            f.write(f"<html><body><h2>{args.era} / {cat}</h2>{imgs}</body></html>")
        print(f"plots in {odir}")


if __name__ == "__main__":
    main()

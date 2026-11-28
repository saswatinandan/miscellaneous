#!/usr/bin/env python3
"""Step 7: table and plot of the limits from run_limits.sh.

Reads limits/higgsCombine_<signal>.AsymptoticLimits.mH*.root and plots, for each
HNL mass, the limit on the signal strength r versus |V|^2.
Signal names must contain _M<mass>_V2_<v2> (e.g. HNL_M10_V2_6.30e-07_2022).

Example:
    python3 scripts/plot_limits.py
"""
import argparse
import glob
import os
import re
import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import uproot  # noqa: E402

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from hnl.config import FW_DIR  # noqa: E402

QUANTILES = {0.025: "-2s", 0.16: "-1s", 0.5: "exp", 0.84: "+1s", 0.975: "+2s", -1.0: "obs"}


def read(path):
    t = uproot.open(path)["limit"].arrays(["quantileExpected", "limit"], library="np")
    out = {}
    for q, v in zip(t["quantileExpected"], t["limit"]):
        for qq, name in QUANTILES.items():
            if abs(q - qq) < 1e-3:
                out[name] = float(v)
    return out


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--indir", default=os.path.join(FW_DIR, "limits"))
    args = p.parse_args()

    rows = []
    for path in sorted(glob.glob(os.path.join(args.indir, "higgsCombine_*.AsymptoticLimits.*.root"))):
        fm = re.match(r"^higgsCombine_(.+)\.AsymptoticLimits\.mH[0-9.]+\.root$", os.path.basename(path))
        if not fm:
            continue
        sig = fm.group(1)
        m = re.search(r"_M([0-9.]+)_V2_([0-9.eE+-]+?)(?:_|$)", sig)
        if not m:
            print(f"skip {sig}: name has no _M<mass>_V2_<v2>")
            continue
        rows.append((float(m.group(1)), float(m.group(2)), sig, read(path)))
    if not rows:
        sys.exit(f"no limit files in {args.indir}")

    print(f"{'signal':40s} {'exp':>10s} {'-1s':>10s} {'+1s':>10s} {'obs':>10s}")
    for mass, v2, sig, r in rows:
        print(f"{sig:40s}" + "".join(f"{r.get(k, float('nan')):10.3g}" for k in ("exp", "-1s", "+1s", "obs")))

    fig, ax = plt.subplots(figsize=(7, 5))
    for mass in sorted({r[0] for r in rows}):
        pts = sorted((v2, r) for m, v2, _, r in rows if m == mass)
        x = [v for v, _ in pts]
        line, = ax.plot(x, [r["exp"] for _, r in pts], "--o", label=f"M = {mass:g} GeV (expected)")
        if all("-1s" in r and "+1s" in r for _, r in pts):
            ax.fill_between(x, [r["-1s"] for _, r in pts], [r["+1s"] for _, r in pts], color=line.get_color(), alpha=0.2)
        if all("obs" in r for _, r in pts):
            ax.plot(x, [r["obs"] for _, r in pts], "-", color=line.get_color())
    ax.axhline(1, color="black", ls=":", lw=1)
    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xlabel(r"$|V_{\mu N}|^2$")
    ax.set_ylabel("95% CL limit on signal strength r")
    ax.legend(fontsize=8)
    fig.tight_layout()
    out = os.path.join(args.indir, "limits.png")
    fig.savefig(out, dpi=150)
    print(f"wrote {out}")


if __name__ == "__main__":
    main()

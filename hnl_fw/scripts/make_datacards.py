#!/usr/bin/env python3
"""Step 5: write Combine datacards and shape files.

For every era, category and signal point:
    datacards/<era>/<category>/<signal>.txt   (datacard)
    datacards/<era>/<category>/<signal>.root  (shapes: signal, backgrounds, data_obs)

Backgrounds come from hnl.bkg.estimate_backgrounds(). While there are none, a tiny
placeholder background is written so that the cards are valid; replace it.
data_obs: real data with --unblind, otherwise the sum of backgrounds (Asimov, blinded).

Example:
    python3 scripts/make_datacards.py --eras 2022 2022EE
"""
import argparse
import os
import pickle
import sys

import hist
import numpy as np
import uproot

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from hnl.bkg import estimate_backgrounds  # noqa: E402
from hnl.config import FW_DIR, load_analysis  # noqa: E402

PLACEHOLDER = "bkg_placeholder"


def project(h, cat):
    """1D fit histogram for one category (empty if the category was never filled)."""
    if cat in list(h.axes["category"]):
        return h[cat, :]
    return hist.Hist(h.axes[1], storage=hist.storage.Weight())


def write_card(path, shapes_name, signal, bkgs, era_cfg, rates):
    procs = [signal] + list(bkgs)
    lumi = era_cfg.get("lumi_unc", 1.0)
    w = max(14, max(len(p) for p in procs) + 2)
    col = lambda vals: "".join(f"{str(v):>{w}s}" for v in vals)  # noqa: E731
    lines = [
        "imax 1  number of channels",
        f"jmax {len(bkgs)}  number of backgrounds",
        "kmax *  number of nuisance parameters",
        "-" * 60,
        f"shapes * * {shapes_name} $PROCESS $PROCESS_$SYSTEMATIC",
        "-" * 60,
        "bin          ch",
        "observation  -1",
        "-" * 60,
        f"{'bin':22s}" + col(["ch"] * len(procs)),
        f"{'process':22s}" + col(procs),
        f"{'process':22s}" + col(range(len(procs))),
        f"{'rate':22s}" + col([f"{rates[p]:.6g}" for p in procs]),
        "-" * 60,
        f"{'lumi lnN':22s}" + col([lumi] * len(procs)),
        "# TODO: add systematic uncertainties here",
        "* autoMCStats 0",
    ]
    with open(path, "w") as f:
        f.write("\n".join(lines) + "\n")


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--eras", nargs="+", required=True)
    p.add_argument("--unblind", action="store_true", help="use real data for data_obs")
    p.add_argument("--results", default=os.path.join(FW_DIR, "results"))
    p.add_argument("--outdir", default=os.path.join(FW_DIR, "datacards"))
    p.add_argument("--analysis", default=None)
    args = p.parse_args()

    ana = load_analysis(args.analysis)
    hname, categories = ana["fit"]["histogram"], ana["fit"]["categories"]

    for era in args.eras:
        with open(os.path.join(args.results, era, "merged.pkl"), "rb") as f:
            merged = pickle.load(f)
        signals = {n: s for n, s in merged.items() if s["kind"] == "signal"}
        if not signals:
            print(f"{era}: no signal samples, nothing to do")
            continue
        bkg = estimate_backgrounds(merged, hname, categories)
        data = [s for s in merged.values() if s["kind"] == "data"]

        for cat in categories:
            odir = os.path.join(args.outdir, era, cat)
            os.makedirs(odir, exist_ok=True)
            bkg_h = {b: hs[cat] for b, hs in bkg.items() if cat in hs}
            ref = project(next(iter(signals.values()))["hists"][hname], cat)
            if not bkg_h:
                print(f"WARNING {era}/{cat}: no backgrounds yet, writing '{PLACEHOLDER}' (1e-3 per bin)")
                h = hist.Hist(ref.axes[0], storage=hist.storage.Weight())
                h.view().value[...] = 1e-3
                h.view().variance[...] = 0.0
                bkg_h = {PLACEHOLDER: h}

            if args.unblind and data:
                obs = sum((project(d["hists"][hname], cat) for d in data[1:]), project(data[0]["hists"][hname], cat))
            else:
                obs = sum(list(bkg_h.values())[1:], list(bkg_h.values())[0])

            for sname, s in signals.items():
                sig = project(s["hists"][hname], cat)
                shapes = f"{sname}.root"
                with uproot.recreate(os.path.join(odir, shapes)) as f:
                    f[sname] = sig
                    for b, h in bkg_h.items():
                        f[b] = h
                    obs_h = hist.Hist(obs.axes[0], storage=hist.storage.Weight())
                    obs_h.view().value[...] = obs.values()
                    obs_h.view().variance[...] = obs.values()
                    f["data_obs"] = obs_h
                rates = {sname: float(np.sum(sig.values()))}
                rates.update({b: float(np.sum(h.values())) for b, h in bkg_h.items()})
                write_card(os.path.join(odir, f"{sname}.txt"), shapes, sname, list(bkg_h), ana["eras"][era], rates)
            print(f"{era}/{cat}: {len(signals)} datacards in {odir}")


if __name__ == "__main__":
    main()

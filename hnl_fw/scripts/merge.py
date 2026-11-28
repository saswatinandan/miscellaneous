#!/usr/bin/env python3
"""Step 4: merge the job outputs of an era and normalise the MC.

Reads <output eos_dir>/<era>/<sample>/job_*.pkl (or --indir), adds the jobs of each
sample, scales MC to   xsec [pb] * 1000 * lumi [fb^-1] / sum(genWeight)
and writes results/<era>/merged.pkl:
    {sample: {"kind", "group", "mass", "v2", "scale", "sumw", "nevents", "cutflow", "hists"}}

Example:
    python3 scripts/merge.py --era 2022
"""
import argparse
import glob
import math
import os
import pickle
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from hnl.config import FW_DIR, load_analysis, load_metadata  # noqa: E402
from hnl.processor import add_outputs, empty_output  # noqa: E402


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--era", required=True)
    p.add_argument("--indir", default=None, help="folder with <sample>/job_*.pkl (default: output eos_dir/<era>)")
    p.add_argument("--outdir", default=os.path.join(FW_DIR, "results"))
    p.add_argument("--analysis", default=None)
    p.add_argument("--metadata-dir", default=None)
    p.add_argument("--jobdir", default=os.environ.get("HNL_JOBDIR", os.path.expanduser("~/hnl_fw_jobs")),
                   help="job folder used by submit_condor.py (to check for missing jobs)")
    p.add_argument("--allow-missing", action="store_true", help="merge even if some jobs have no output")
    args = p.parse_args()

    ana = load_analysis(args.analysis)
    era_cfg = ana["eras"][args.era]
    meta = load_metadata(args.era, args.metadata_dir)
    indir = args.indir or os.path.join(ana["output"]["eos_dir"], args.era)
    fpj_file = os.path.join(args.jobdir, args.era, "files_per_job.txt")
    fpj = int(open(fpj_file).read()) if os.path.exists(fpj_file) else None

    merged, missing = {}, []
    for name, s in meta.items():
        outs = sorted(glob.glob(os.path.join(indir, name, "job_*.pkl")))
        if fpj:
            expected = math.ceil(len(s["files"]) / fpj)
            if len(outs) != expected:
                missing.append(f"{name}: {len(outs)}/{expected} job outputs")
        if not outs:
            continue
        total = empty_output()
        for o in outs:
            with open(o, "rb") as f:
                add_outputs(total, pickle.load(f))

        scale = 1.0
        if s["kind"] != "data":
            scale = s["xsec_pb"] * 1000.0 * era_cfg["lumi_fb"] / total["sumw"] if total["sumw"] else 0.0
            total["hists"] = {k: h * scale for k, h in total["hists"].items()}
            total["cutflow"] = {k: v * scale for k, v in total["cutflow"].items()}
        merged[name] = {**{k: s.get(k) for k in ("kind", "group", "mass", "v2")}, "scale": scale, **total}
        print(f"{name:45s} {s['kind']:6s} jobs={len(outs):4d} events={total['nevents']:10d} scale={scale:.4g}")

    if missing:
        print("\nMISSING OUTPUTS (resubmit with submit_condor.py --resubmit):")
        for m in missing:
            print("  " + m)
        if not args.allow_missing:
            sys.exit("not merged: some jobs are missing (use --allow-missing to merge anyway)")

    os.makedirs(os.path.join(args.outdir, args.era), exist_ok=True)
    path = os.path.join(args.outdir, args.era, "merged.pkl")
    with open(path, "wb") as f:
        pickle.dump(merged, f)
    print(f"\nwrote {path}")

    # cut flow table (yields after normalisation)
    steps = []
    for s in merged.values():
        steps += [k for k in s["cutflow"] if k not in steps]
    print("\ncut flow (normalised yields):")
    print(f"{'sample':45s}" + "".join(f"{st:>14s}" for st in steps))
    for name, s in merged.items():
        print(f"{name:45s}" + "".join(f"{s['cutflow'].get(st, float('nan')):14.1f}" for st in steps))


if __name__ == "__main__":
    main()

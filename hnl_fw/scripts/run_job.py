#!/usr/bin/env python3
"""Step 2: process (part of) one sample and save the histograms.

Runs locally or inside a batch job.

Examples:
    # quick local test on the first 2 files of a sample
    python3 scripts/run_job.py --era 2022 --sample data_Muon_2022C --first 0 --nfiles 2 --out test.pkl
    # what a batch job runs (job number 3, 5 files per job)
    python3 scripts/run_job.py --era 2022 --sample data_Muon_2022C --job 3 --files-per-job 5 --out out.pkl
"""
import argparse
import os
import pickle
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from hnl.config import load_analysis, load_metadata  # noqa: E402
from hnl.processor import process_files  # noqa: E402


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--era", required=True)
    p.add_argument("--sample", required=True)
    p.add_argument("--out", required=True, help="output .pkl")
    p.add_argument("--metadata-dir", default=None)
    p.add_argument("--analysis", default=None)
    g = p.add_mutually_exclusive_group()
    g.add_argument("--job", type=int, help="job number (uses --files-per-job)")
    g.add_argument("--first", type=int, default=0, help="index of the first file")
    p.add_argument("--files-per-job", type=int, default=5)
    p.add_argument("--nfiles", type=int, default=None, help="number of files (default: all from --first)")
    args = p.parse_args()

    ana = load_analysis(args.analysis)
    sample = load_metadata(args.era, args.metadata_dir)[args.sample]
    files = sample["files"]
    if args.job is not None:
        files = files[args.job * args.files_per_job:(args.job + 1) * args.files_per_job]
    else:
        files = files[args.first:] if args.nfiles is None else files[args.first:args.first + args.nfiles]
    if not files:
        sys.exit("no files selected")

    t0 = time.time()
    out = process_files(files, sample, ana["eras"][args.era])
    out["meta"] = {"sample": args.sample, "era": args.era, "files": files}
    with open(args.out, "wb") as f:
        pickle.dump(out, f)
    print(f"done: {out['nevents']} events in {time.time() - t0:.0f} s -> {args.out}")
    print("cutflow:", {k: round(v, 2) for k, v in out["cutflow"].items()})


if __name__ == "__main__":
    main()

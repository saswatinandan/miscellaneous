#!/usr/bin/env python3
"""Step 1: build the file lists for every sample.

Reads config/samples_*.yaml and writes metadata/<era>.json:
    {sample: {"kind", "era", "files": [...], "xsec_pb", "group", "mass", "v2"}}

Files come from DAS (needs `dasgoclient` and a valid grid proxy, e.g. on lxplus:
`voms-proxy-init -voms cms`) or from a glob on EOS/local disk.

Example:
    python3 scripts/make_metadata.py --samples config/samples_2022.yaml
"""
import argparse
import glob
import json
import os
import shutil
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from hnl.config import FW_DIR, load_analysis, load_samples  # noqa: E402

KEEP = ("kind", "era", "xsec_pb", "group", "mass", "v2")


def das_files(dataset, redirector):
    if shutil.which("dasgoclient") is None:
        raise RuntimeError("dasgoclient not found: run this on lxplus (with a grid proxy) or use files_glob")
    res = subprocess.run(["dasgoclient", "-query", f"file dataset={dataset}"],
                         capture_output=True, text=True)
    if res.returncode != 0:
        raise RuntimeError(f"DAS query failed for {dataset}:\n{res.stderr}")
    files = sorted(l.strip() for l in res.stdout.splitlines() if l.strip().endswith(".root"))
    return [redirector + f for f in files]


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--samples", required=True, help="samples YAML file")
    p.add_argument("--analysis", default=None, help="analysis YAML (default: config/analysis.yaml)")
    p.add_argument("--outdir", default=os.path.join(FW_DIR, "metadata"))
    p.add_argument("--only", nargs="*", default=None, help="only these sample names")
    args = p.parse_args()

    ana = load_analysis(args.analysis)
    samples = load_samples(args.samples)
    if not samples:
        sys.exit(f"no samples defined in {args.samples}")

    by_era, problems = {}, []
    for name, s in samples.items():
        if args.only and name not in args.only:
            continue
        if s.get("era") not in ana["eras"]:
            problems.append(f"{name}: era '{s.get('era')}' not in analysis.yaml")
            continue
        if s.get("kind") not in ("data", "bkg", "signal"):
            problems.append(f"{name}: kind must be data, bkg or signal")
            continue
        if s["kind"] != "data" and "xsec_pb" not in s:
            problems.append(f"{name}: MC sample without xsec_pb")
            continue
        try:
            if "das" in s:
                files = das_files(s["das"], ana.get("xrootd_redirector", ""))
            elif "files_glob" in s:
                files = sorted(glob.glob(s["files_glob"]))
            else:
                raise RuntimeError("needs 'das' or 'files_glob'")
        except RuntimeError as e:
            problems.append(f"{name}: {e}")
            continue
        if not files:
            problems.append(f"{name}: no files found")
            continue
        entry = {k: s[k] for k in KEEP if k in s}
        entry["files"] = files
        by_era.setdefault(s["era"], {})[name] = entry
        print(f"{name:45s} {s['era']:7s} {s['kind']:6s} {len(files):5d} files")

    os.makedirs(args.outdir, exist_ok=True)
    for era, entries in by_era.items():
        path = os.path.join(args.outdir, f"{era}.json")
        old = {}
        if os.path.exists(path):
            with open(path) as f:
                old = json.load(f)
        old.update(entries)                     # keep samples not re-queried this time
        with open(path, "w") as f:
            json.dump(old, f, indent=1)
        print(f"wrote {path} ({len(old)} samples)")

    if problems:
        print("\nPROBLEMS:")
        for x in problems:
            print("  " + x)
        sys.exit(1)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Step 3: submit the processing to HTCondor (run on lxplus).

Splits every sample of an era into jobs of N files, writes the HTCondor files to
jobs/<era>/ and submits them. Each job writes one .pkl to
    <output eos_dir>/<era>/<sample>/job_<N>.pkl

Examples:
    python3 scripts/submit_condor.py --era 2022 --dry-run         # only write the files
    python3 scripts/submit_condor.py --era 2022                   # write and submit
    python3 scripts/submit_condor.py --era 2022 --resubmit        # only jobs whose output is missing
    python3 scripts/submit_condor.py --era 2022 --only data_Muon_2022C --files-per-job 10

Before submitting:
  * the framework must be on AFS or EOS (the jobs read it from there),
  * job files and logs go to ~/hnl_fw_jobs/<era> on AFS (change with --jobdir or $HNL_JOBDIR),
  * for DAS/xrootd files you need a grid proxy readable by the jobs, e.g.
        voms-proxy-init -voms cms -valid 192:00 --out ~/private/x509up
        export X509_USER_PROXY=~/private/x509up
"""
import argparse
import math
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from hnl.config import FW_DIR, load_analysis, load_metadata  # noqa: E402

# HTCondor cannot write logs to EOS, so job files and logs go to AFS (your lxplus home).
DEFAULT_JOBDIR = os.environ.get("HNL_JOBDIR", os.path.expanduser("~/hnl_fw_jobs"))

# Same software as SWAN (it has coffea, hist, uproot, pyyaml). Change if needed.
DEFAULT_LCG = "/cvmfs/sft.cern.ch/lcg/views/LCG_110_swan/x86_64-el9-gcc13-opt/setup.sh"

WRAPPER = """#!/bin/bash
# Runs one job: <era> <sample> <job> <files_per_job> <fw_dir> <out_dir> <eos_url> <lcg_setup>
set -e
ERA=$1; SAMPLE=$2; JOB=$3; FPJ=$4; FWDIR=$5; OUTDIR=$6; EOSURL=$7; LCG=$8
source "$LCG"
WORK=${_CONDOR_SCRATCH_DIR:-$PWD}
cd "$FWDIR"
python3 scripts/run_job.py --era "$ERA" --sample "$SAMPLE" --job "$JOB" --files-per-job "$FPJ" --out "$WORK/out.pkl"
xrdcp -f -p "$WORK/out.pkl" "${EOSURL}${OUTDIR}/${ERA}/${SAMPLE}/job_${JOB}.pkl"
"""


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--era", required=True)
    p.add_argument("--files-per-job", type=int, default=5)
    p.add_argument("--only", nargs="*", default=None, help="only these samples")
    p.add_argument("--flavour", default="workday", help="HTCondor JobFlavour (espresso, microcentury, longlunch, workday, ...)")
    p.add_argument("--lcg", default=DEFAULT_LCG, help="LCG view setup script")
    p.add_argument("--proxy", default=os.environ.get("X509_USER_PROXY"), help="grid proxy file")
    p.add_argument("--resubmit", action="store_true", help="only jobs whose output file is missing")
    p.add_argument("--dry-run", action="store_true", help="write the files but do not submit")
    p.add_argument("--jobdir", default=DEFAULT_JOBDIR, help="where job files and logs go (must be on AFS, not EOS)")
    p.add_argument("--analysis", default=None)
    args = p.parse_args()

    ana = load_analysis(args.analysis)
    meta = load_metadata(args.era)
    out_dir, eos_url = ana["output"]["eos_dir"], ana["output"]["eos_url"]

    jobdir = os.path.join(args.jobdir, args.era)
    if jobdir.startswith("/eos"):
        sys.exit("--jobdir must not be on EOS (HTCondor cannot write logs there); use your AFS home")
    os.makedirs(os.path.join(jobdir, "logs"), exist_ok=True)
    lines, needs_proxy = [], False
    for name, s in meta.items():
        if args.only and name not in args.only:
            continue
        njobs = math.ceil(len(s["files"]) / args.files_per_job)
        needs_proxy |= any(f.startswith("root://") for f in s["files"])
        for j in range(njobs):
            if args.resubmit and os.path.exists(os.path.join(out_dir, args.era, name, f"job_{j}.pkl")):
                continue
            lines.append(f"{args.era} {name} {j}")
        print(f"{name:45s} {len(s['files']):5d} files -> {njobs} jobs")

    if not lines:
        print("nothing to submit")
        return
    if needs_proxy and not (args.proxy and os.path.exists(args.proxy)):
        sys.exit("some files are read with xrootd: create a proxy and set X509_USER_PROXY (see --help)")

    with open(os.path.join(jobdir, "jobs.txt"), "w") as f:
        f.write("\n".join(lines) + "\n")
    with open(os.path.join(jobdir, "run_job.sh"), "w") as f:
        f.write(WRAPPER)
    os.chmod(os.path.join(jobdir, "run_job.sh"), 0o755)
    # how many jobs each sample has, used by merge.py to check for missing outputs
    with open(os.path.join(jobdir, "files_per_job.txt"), "w") as f:
        f.write(str(args.files_per_job))

    proxy_lines = f"use_x509userproxy = true\nx509userproxy = {args.proxy}\n" if needs_proxy else ""
    sub = f"""universe   = vanilla
executable = {jobdir}/run_job.sh
arguments  = $(era) $(sample) $(job) {args.files_per_job} {FW_DIR} {out_dir} {eos_url} {args.lcg}
output     = {jobdir}/logs/$(sample)_$(job).out
error      = {jobdir}/logs/$(sample)_$(job).err
log        = {jobdir}/logs/condor.log
+JobFlavour = "{args.flavour}"
max_retries = 2
{proxy_lines}queue era, sample, job from {jobdir}/jobs.txt
"""
    sub_path = os.path.join(jobdir, "submit.sub")
    with open(sub_path, "w") as f:
        f.write(sub)
    print(f"{len(lines)} jobs written to {sub_path}")
    if args.dry_run:
        print("dry run: not submitted. Submit with: condor_submit " + sub_path)
        return
    subprocess.run(["condor_submit", sub_path], check=True)


if __name__ == "__main__":
    main()

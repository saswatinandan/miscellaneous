#!/bin/bash
# Runs the whole chain locally on fake NanoAOD files (no grid, no Condor, no Combine).
#   bash tests/run_test.sh      (from hnl_fw/)
set -e
cd "$(dirname "$0")/.."
A=tests/analysis_test.yaml
rm -rf tests/data tests/out
python3 tests/make_test_nano.py tests/data
python3 scripts/make_metadata.py --samples tests/samples_test.yaml --analysis $A --outdir tests/out/metadata
for S in data_test bkg_test HNL_M10_V2_1e-06_test; do
    for J in 0 1; do      # 2 "jobs" per sample, 2 files per job
        mkdir -p tests/out/jobs/2022/$S
        python3 scripts/run_job.py --era 2022 --sample $S --job $J --files-per-job 2 \
            --metadata-dir tests/out/metadata --analysis $A --out tests/out/jobs/2022/$S/job_$J.pkl
    done
done
python3 scripts/merge.py --era 2022 --analysis $A --metadata-dir tests/out/metadata --indir tests/out/jobs/2022 --outdir tests/out/results
python3 scripts/make_datacards.py --eras 2022 --analysis $A --results tests/out/results --outdir tests/out/datacards
python3 scripts/plot_stack.py --era 2022 --results tests/out/results --outdir tests/out/plots
echo "TEST OK: see tests/out/"

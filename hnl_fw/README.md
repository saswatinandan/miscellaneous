# HNL analysis framework (2022)

From the sample lists to the limits, in seven steps. Event selection, corrections
and background estimation are **placeholders** (they keep everything) so the whole
chain runs now; fill them in as the analysis develops.

```
config/analysis.yaml        eras, luminosity, golden JSON, triggers, fit variable, output dir
config/samples_2022.yaml    data / background / signal samples (DAS dataset or file glob)
hnl/selection.py            object selection, cut flow, categories        <- TODO
hnl/corrections.py          MC weights (pileup, scale factors)            <- TODO
hnl/histograms.py           histograms (add new ones here)
hnl/bkg.py                  background estimation                         <- TODO
hnl/processor.py            processing of one file (selection -> histograms)
scripts/                    the steps below
tests/run_test.sh           whole chain on fake NanoAOD files
```

Eras: `2022` = Run2022 C, D (pre-EE) and `2022EE` = Run2022 E, F, G (post-EE).
Values marked `CHECK` in the config (luminosity, golden JSON path, dataset names)
are placeholders: verify them before using any result.

## Requirements

* Processing, merging, datacards, plots: Python with `coffea`, `awkward`, `hist`,
  `uproot`, `pyyaml`, `matplotlib`. SWAN (LCG_110_swan) has all of them.
* DAS file lists and HTCondor: lxplus (`dasgoclient`, `condor_submit`, grid proxy).
* Limits: CMSSW with Combine (HiggsAnalysis/CombinedLimit).

Run all commands from the `hnl_fw/` folder.

## 0. Test the chain (no grid, no batch)

```bash
bash tests/run_test.sh
```
Makes fake NanoAOD files and runs metadata -> jobs -> merge -> datacards -> plots
into `tests/out/`.

## 1. Metadata: file lists of all samples (lxplus)

Fill `config/samples_2022.yaml`, then:
```bash
voms-proxy-init -voms cms -valid 192:00 --out ~/private/x509up
export X509_USER_PROXY=~/private/x509up
python3 scripts/make_metadata.py --samples config/samples_2022.yaml
```
Writes `metadata/2022.json` and `metadata/2022EE.json`.

## 2. Quick local test on real files

```bash
python3 scripts/run_job.py --era 2022 --sample data_Muon_2022C --first 0 --nfiles 1 --out test.pkl
```

## 3. Submit to HTCondor (lxplus)

```bash
python3 scripts/submit_condor.py --era 2022   --dry-run   # check the job files first
python3 scripts/submit_condor.py --era 2022
python3 scripts/submit_condor.py --era 2022EE
condor_q
```
Job outputs: `<output eos_dir>/<era>/<sample>/job_N.pkl`. Job files and logs:
`~/hnl_fw_jobs/<era>/` (AFS; HTCondor cannot write logs to EOS).
Failed or missing jobs: `python3 scripts/submit_condor.py --era 2022 --resubmit`.

## 4. Merge and normalise

```bash
python3 scripts/merge.py --era 2022
python3 scripts/merge.py --era 2022EE
```
Adds the jobs of each sample, scales MC to `xsec * lumi / sum(genWeight)`, prints
the cut flow and writes `results/<era>/merged.pkl`. Stops if jobs are missing.

## 5. Control plots

```bash
python3 scripts/plot_stack.py --era 2022 --log
```
Stacked backgrounds + signals (+ data with `--unblind`) for every histogram and
category, in `plots/<era>/<category>/` with an `index.html`. Use
`--outdir /eos/user/s/snandan/www/hnl/fw` to put them on your website.

## 6. Datacards and limits

```bash
python3 scripts/make_datacards.py --eras 2022 2022EE          # blinded: data_obs = sum of backgrounds
bash scripts/run_limits.sh 2022 2022EE                        # needs Combine (cmsenv)
python3 scripts/plot_limits.py
```
One card per era, category and signal point in `datacards/`; `run_limits.sh`
combines eras and categories per signal point and runs `AsymptoticLimits`;
`plot_limits.py` prints a table and plots the limit on r versus |V|^2 for each mass.
While there are no backgrounds, the cards contain a tiny `bkg_placeholder` so that
they are valid.

## Where to add things

| What | Where |
|---|---|
| muon / jet selection | `select_muons`, `select_jets` in `hnl/selection.py` |
| event selection (cut flow) | `cutflow_steps` in `hnl/selection.py` |
| categories | `categories` in `hnl/selection.py` (and `fit.categories` in `analysis.yaml`) |
| triggers | `triggers` per era in `analysis.yaml` |
| new histogram | `HISTOGRAMS` in `hnl/histograms.py` |
| pileup / scale factors | `hnl/corrections.py` |
| background estimation | `data_driven_backgrounds` in `hnl/bkg.py`, or MC samples with `kind: bkg` |
| systematics | `write_card` in `scripts/make_datacards.py` |
| fit variable | `fit.histogram` in `analysis.yaml` |

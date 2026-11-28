#!/usr/bin/env python3
"""Write small fake NanoAOD files to test the whole chain without grid access.

    python3 tests/make_test_nano.py tests/data
creates tests/data/{data,bkg,signal}/file_<i>.root
"""
import os
import sys

import awkward as ak
import numpy as np
import uproot


def make(path, n, seed, is_mc, mass_peak=None):
    rng = np.random.default_rng(seed)
    nmu = rng.integers(0, 4, n)
    njet = rng.integers(0, 5, n)

    def jag(counts, values):
        return ak.unflatten(values, counts)

    tot_mu, tot_jet = nmu.sum(), njet.sum()
    mu_pt = rng.exponential(20, tot_mu) + 3
    if mass_peak:   # signal-like: put a mass peak in the two leading muons
        mu_pt = rng.normal(mass_peak / 2, 2, tot_mu).clip(3)
    branches = {
        "run": np.full(n, 357000, dtype=np.uint32),
        "luminosityBlock": rng.integers(1, 100, n).astype(np.uint32),
        "event": np.arange(n, dtype=np.uint64),
        "Muon": ak.zip({
            "pt": jag(nmu, mu_pt.astype(np.float32)),
            "eta": jag(nmu, rng.uniform(-2.4, 2.4, tot_mu).astype(np.float32)),
            "phi": jag(nmu, rng.uniform(-np.pi, np.pi, tot_mu).astype(np.float32)),
            "mass": jag(nmu, np.full(tot_mu, 0.106, dtype=np.float32)),
            "charge": jag(nmu, rng.choice([-1, 1], tot_mu).astype(np.int32)),
        }),
        "Jet": ak.zip({
            "pt": jag(njet, (rng.exponential(30, tot_jet) + 15).astype(np.float32)),
            "eta": jag(njet, rng.uniform(-2.5, 2.5, tot_jet).astype(np.float32)),
            "phi": jag(njet, rng.uniform(-np.pi, np.pi, tot_jet).astype(np.float32)),
            "mass": jag(njet, rng.uniform(1, 10, tot_jet).astype(np.float32)),
        }),
        "PuppiMET_pt": rng.exponential(30, n).astype(np.float32),
        "PuppiMET_phi": rng.uniform(-np.pi, np.pi, n).astype(np.float32),
        "HLT_IsoMu24": rng.random(n) < 0.7,
    }
    if is_mc:
        branches["genWeight"] = rng.choice([1.0, -1.0], n, p=[0.9, 0.1]).astype(np.float32)
    with uproot.recreate(path) as f:
        f["Events"] = branches


def main():
    out = sys.argv[1] if len(sys.argv) > 1 else "tests/data"
    for kind, is_mc, peak in (("data", False, None), ("bkg", True, None), ("signal", True, 40)):
        os.makedirs(os.path.join(out, kind), exist_ok=True)
        for i in range(3):
            make(os.path.join(out, kind, f"file_{i}.root"), 2000, hash((kind, i)) % 2**32, is_mc, peak)
    print(f"test files written to {out}/")


if __name__ == "__main__":
    main()

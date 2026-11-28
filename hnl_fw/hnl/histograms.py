"""Histogram definitions and filling. Every histogram has a category axis plus one variable axis.

To add a histogram: add an entry to HISTOGRAMS with its axis and a function that
returns one value per event (None where it is not defined, e.g. no second muon).
"""
import awkward as ak
import hist
import numpy as np


def _p4(obj):
    px = obj.pt * np.cos(obj.phi)
    py = obj.pt * np.sin(obj.phi)
    pz = obj.pt * np.sinh(obj.eta)
    e = np.sqrt(px**2 + py**2 + pz**2 + obj.mass**2)
    return e, px, py, pz


def invariant_mass(a, b):
    ea, xa, ya, za = _p4(a)
    eb, xb, yb, zb = _p4(b)
    m2 = (ea + eb) ** 2 - (xa + xb) ** 2 - (ya + yb) ** 2 - (za + zb) ** 2
    return np.sqrt(np.maximum(m2, 0))


def delta_phi(a, b):
    d = abs(a - b) % (2 * np.pi)
    return np.where(d > np.pi, 2 * np.pi - d, d)


def delta_r(a, b):
    return np.hypot(a.eta - b.eta, delta_phi(a.phi, b.phi))


def _nth(objs, n):
    """n-th object of each event (None if there are fewer)."""
    return ak.pad_none(objs, n + 1, clip=True)[:, n]


# name: (axis, function(objects) -> one value per event)
HISTOGRAMS = {
    "n_muons":  (hist.axis.Regular(6, -0.5, 5.5, name="x", label="number of muons"),
                 lambda o: ak.num(o["muons"])),
    "mu1_pt":   (hist.axis.Regular(50, 0, 100, name="x", label=r"leading $\mu$ $p_T$ [GeV]"),
                 lambda o: _nth(o["muons"], 0).pt),
    "mu2_pt":   (hist.axis.Regular(50, 0, 100, name="x", label=r"subleading $\mu$ $p_T$ [GeV]"),
                 lambda o: _nth(o["muons"], 1).pt),
    "mass_mm":  (hist.axis.Regular(50, 0, 100, name="x", label=r"$m_{\mu\mu}$ [GeV]"),
                 lambda o: invariant_mass(_nth(o["muons"], 0), _nth(o["muons"], 1))),
    "dr_mm":    (hist.axis.Regular(50, 0, 6, name="x", label=r"$\Delta R(\mu_1, \mu_2)$"),
                 lambda o: delta_r(_nth(o["muons"], 0), _nth(o["muons"], 1))),
    "n_jets":   (hist.axis.Regular(10, -0.5, 9.5, name="x", label="number of jets"),
                 lambda o: ak.num(o["jets"])),
    "jet1_pt":  (hist.axis.Regular(50, 0, 200, name="x", label=r"leading jet $p_T$ [GeV]"),
                 lambda o: _nth(o["jets"], 0).pt),
    "met_pt":   (hist.axis.Regular(50, 0, 200, name="x", label=r"$p_T^{miss}$ [GeV]"),
                 lambda o: o["met"].pt),
}


def book():
    """Empty histograms: category axis + variable axis, weighted storage."""
    return {
        name: hist.Hist(hist.axis.StrCategory([], name="category", growth=True), axis,
                        storage=hist.storage.Weight())
        for name, (axis, _) in HISTOGRAMS.items()
    }


def fill(hists, objects, weights, category_masks):
    """Fill all histograms for the selected events, once per category."""
    for name, (_, func) in HISTOGRAMS.items():
        values = ak.to_numpy(ak.fill_none(func(objects), np.nan)).astype(float)
        ok = np.isfinite(values)
        for cat, cmask in category_masks.items():
            sel = ok & cmask
            hists[name].fill(category=cat, x=values[sel], weight=weights[sel])

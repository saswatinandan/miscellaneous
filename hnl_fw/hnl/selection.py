"""Object selection, event selection (cut flow) and categories.

Everything here is a placeholder that keeps all objects / events, so the full
chain runs before the real cuts exist. Fill in the TODOs.
"""
import awkward as ak
import numpy as np


# ---------------------------------------------------------------- objects
def select_muons(events):
    """TODO: muon ID / isolation / pT / eta / dxy / dz cuts. Currently: all muons."""
    muons = events.Muon
    mask = ak.ones_like(muons.pt, dtype=bool)
    # Example (fill later):
    # mask = (muons.pt > 5) & (abs(muons.eta) < 2.4) & muons.looseId
    return muons[mask]


def select_jets(events):
    """TODO: jet ID / pT / eta cuts and lepton cleaning. Currently: all jets."""
    jets = events.Jet
    mask = ak.ones_like(jets.pt, dtype=bool)
    # Example (fill later):
    # mask = (jets.pt > 20) & (abs(jets.eta) < 2.4)
    return jets[mask]


def select_objects(events):
    """All selected objects of an event, used by the cut flow and the histograms."""
    return {
        "muons": select_muons(events),
        "jets": select_jets(events),
        "met": events.PuppiMET if "PuppiMET" in events.fields else events.MET,
    }


# ---------------------------------------------------------------- events
def trigger_mask(events, triggers):
    """OR of the given HLT paths (names without 'HLT_'). Empty list = no requirement."""
    if not triggers:
        return np.ones(len(events), dtype=bool)
    mask = np.zeros(len(events), dtype=bool)
    for name in triggers:
        if name in events.HLT.fields:
            mask = mask | ak.to_numpy(events.HLT[name])
        else:
            print(f"WARNING: trigger HLT_{name} not in this file, ignored")
    return mask


def cutflow_steps(events, objects, era_cfg):
    """Ordered list of (name, boolean mask). Each mask is applied on top of the previous ones."""
    return [
        ("trigger", trigger_mask(events, era_cfg.get("triggers", []))),
        # TODO: add the event selection, e.g.
        # ("two_muons", ak.to_numpy(ak.num(objects["muons"]) >= 2)),
        # ("one_jet",   ak.to_numpy(ak.num(objects["jets"]) >= 1)),
    ]


def categories(events, objects):
    """Analysis categories: name -> boolean mask (on selected events). TODO: define them."""
    return {"inclusive": np.ones(len(events), dtype=bool)}

"""Event weights and corrections for MC. Placeholders that return 1, to be filled
(e.g. pileup, muon ID/iso/trigger scale factors with correctionlib)."""
import numpy as np


def event_weight(events, era, is_mc):
    """Per-event weight before normalisation. Data: 1. MC: generator weight x corrections."""
    if not is_mc:
        return np.ones(len(events))
    w = np.asarray(events.genWeight, dtype=float)
    w = w * pileup_weight(events, era)
    w = w * muon_sf(events, era)
    return w


def pileup_weight(events, era):
    """TODO: pileup reweighting (e.g. correctionlib LUM POG json)."""
    return np.ones(len(events))


def muon_sf(events, era):
    """TODO: muon ID / isolation / trigger scale factors."""
    return np.ones(len(events))

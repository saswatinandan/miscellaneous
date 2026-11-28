"""Processing of one sample: read files one by one, apply the selection, fill histograms.

The output of a job is a plain dict that can be pickled and added together:
    {"sumw": sum of generator weights before any cut (MC normalisation),
     "nevents": number of events read,
     "cutflow": {step: weighted events passing},
     "hists": {name: hist.Hist}}
"""
import os

import numpy as np

from . import corrections, histograms, selection
from .io import load_events


def empty_output():
    return {"sumw": 0.0, "nevents": 0, "cutflow": {}, "hists": histograms.book()}


def add_outputs(a, b):
    """a += b (in place), returns a."""
    a["sumw"] += b["sumw"]
    a["nevents"] += b["nevents"]
    for k, v in b["cutflow"].items():
        a["cutflow"][k] = a["cutflow"].get(k, 0.0) + v
    for k, h in b["hists"].items():
        a["hists"][k] = a["hists"][k] + h if k in a["hists"] else h
    return a


def _lumi_mask(events, golden_json):
    if not golden_json:
        return np.ones(len(events), dtype=bool)
    if not os.path.exists(golden_json):
        raise FileNotFoundError(f"golden JSON not found: {golden_json}")
    from coffea.lumi_tools import LumiMask
    return np.asarray(LumiMask(golden_json)(events.run, events.luminosityBlock))


def process_file(path, sample, era_cfg):
    """Process one NanoAOD file of `sample` (a metadata entry). Returns an output dict."""
    is_mc = sample["kind"] != "data"
    events = load_events(path)
    out = empty_output()
    out["nevents"] = len(events)

    weights = corrections.event_weight(events, sample["era"], is_mc)
    out["sumw"] = float(np.sum(np.asarray(events.genWeight, dtype=float))) if is_mc else float(len(events))

    mask = np.ones(len(events), dtype=bool)
    out["cutflow"]["all"] = float(np.sum(weights))
    if not is_mc:
        mask &= _lumi_mask(events, era_cfg.get("golden_json"))
        out["cutflow"]["golden_json"] = float(np.sum(weights[mask]))

    objects = selection.select_objects(events)
    for name, step in selection.cutflow_steps(events, objects, era_cfg):
        mask &= np.asarray(step, dtype=bool)
        out["cutflow"][name] = float(np.sum(weights[mask]))

    sel_events = events[mask]
    sel_objects = {k: v[mask] for k, v in objects.items()}
    cats = selection.categories(sel_events, sel_objects)
    histograms.fill(out["hists"], sel_objects, weights[mask], cats)
    return out


def process_files(paths, sample, era_cfg):
    out = empty_output()
    for i, path in enumerate(paths):
        print(f"[{i + 1}/{len(paths)}] {path}", flush=True)
        add_outputs(out, process_file(path, sample, era_cfg))
    return out

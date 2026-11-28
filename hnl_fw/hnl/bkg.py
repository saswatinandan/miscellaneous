"""Background estimation.

estimate_backgrounds() is what the datacard and plotting scripts call. It returns
    {process_name: {category: hist.Hist (1D, fit variable)}}

For now it only collects MC backgrounds (there are none yet, so it returns {}).
Replace / extend it with the real method (e.g. ABCD or a fake-rate method) later;
the scripts that use it do not need to change.
"""


def mc_backgrounds(merged, histogram, categories):
    """Sum the MC background samples by their 'group'."""
    out = {}
    for name, s in merged.items():
        if s["kind"] != "bkg":
            continue
        group = s.get("group") or name
        h = s["hists"][histogram]
        for cat in categories:
            h1 = h[cat, :] if cat in list(h.axes["category"]) else None
            if h1 is None:
                continue
            out.setdefault(group, {})
            out[group][cat] = out[group][cat] + h1 if cat in out[group] else h1
    return out


def data_driven_backgrounds(merged, histogram, categories):
    """TODO: data-driven background estimate (e.g. ABCD). Return the same structure as mc_backgrounds."""
    return {}


def estimate_backgrounds(merged, histogram, categories):
    bkg = mc_backgrounds(merged, histogram, categories)
    bkg.update(data_driven_backgrounds(merged, histogram, categories))
    return bkg

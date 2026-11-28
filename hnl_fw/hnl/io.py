"""Opening one NanoAOD file as NanoEvents, for old and new coffea versions."""
from coffea.nanoevents import NanoAODSchema, NanoEventsFactory

NanoAODSchema.error_missing_event_ids = False


def _drop_cartesian(name):
    return not name.endswith(("_px", "_py", "_pz"))


def load_events(path, entry_start=None, entry_stop=None):
    """Return NanoEvents for one file. Each file is read on its own, so the
    GenPart mother/daughter links stay correct."""
    try:                                   # coffea >= 2025 (virtual arrays)
        return NanoEventsFactory.from_root(
            {path: "Events"}, schemaclass=NanoAODSchema, mode="virtual",
            entry_start=entry_start, entry_stop=entry_stop,
            iteritems_options={"filter_name": _drop_cartesian},
        ).events()
    except TypeError:
        pass
    try:                                   # coffea 2024.x
        return NanoEventsFactory.from_root(
            {path: "Events"}, schemaclass=NanoAODSchema, mode="eager",
            entry_start=entry_start, entry_stop=entry_stop,
        ).events()
    except TypeError:                      # coffea 0.7.x
        return NanoEventsFactory.from_root(
            path, treepath="Events", schemaclass=NanoAODSchema,
            entry_start=entry_start, entry_stop=entry_stop,
        ).events()

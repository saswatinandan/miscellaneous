"""Reading the YAML configuration and the metadata files."""
import json
import os

import yaml

FW_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load_yaml(path):
    with open(path) as f:
        return yaml.safe_load(f)


def load_analysis(path=None):
    return load_yaml(path or os.path.join(FW_DIR, "config", "analysis.yaml"))


def load_samples(path):
    cfg = load_yaml(path) or {}
    return cfg.get("samples") or {}


def metadata_path(era, metadata_dir=None):
    return os.path.join(metadata_dir or os.path.join(FW_DIR, "metadata"), f"{era}.json")


def load_metadata(era, metadata_dir=None):
    with open(metadata_path(era, metadata_dir)) as f:
        return json.load(f)

from __future__ import annotations

import json
from pathlib import Path

import pytest


@pytest.fixture
def medrag_dataset():
    dataset_path = Path(__file__).resolve().parents[1] / "medrag" / "golden_dataset.json"
    return json.loads(dataset_path.read_text())


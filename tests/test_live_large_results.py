"""Opt-in live checks for very large PuRe result windows."""

import importlib.util
import sys
from pathlib import Path

import pytest


_PROBE_PATH = Path(__file__).parents[1] / "scripts" / "probe_large_result_window.py"
_SPEC = importlib.util.spec_from_file_location("probe_large_result_window", _PROBE_PATH)
assert _SPEC and _SPEC.loader
_PROBE_MODULE = importlib.util.module_from_spec(_SPEC)
sys.modules[_SPEC.name] = _PROBE_MODULE
_SPEC.loader.exec_module(_PROBE_MODULE)
probe = _PROBE_MODULE.probe


pytestmark = [pytest.mark.network, pytest.mark.limit]


async def test_live_large_result_window_supports_500k_offsets_without_full_download():
    results = await probe(pause=1.0)
    by_name = {result.name: result for result in results}

    assert by_name["size=0,offset=0"].total > 500_000
    assert by_name["size=20000,offset=0"].status == 200
    assert by_name["size=20000,offset=0"].records == 20_000
    edge = by_name["size=26000,offset=0"]
    if edge.status == 200:
        assert edge.records == 26_000
    else:
        assert edge.status in {429, 500, 502, 503, 504}
    assert by_name["size=1,offset=500000"].status == 200
    assert by_name["size=1,offset=500000"].records == 1

    total = by_name["size=0,offset=0"].total
    assert by_name[f"size=1,offset={total - 1}"].records == 1
    assert by_name[f"size=1,offset={total}"].records == 0
    assert by_name[f"size=1,offset={total + 1}"].records == 0

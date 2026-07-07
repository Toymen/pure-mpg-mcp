"""Opt-in tests for public-service limits and upstream edge behavior."""

import importlib.util
from pathlib import Path

import pytest


_PROBE_PATH = Path(__file__).parents[1] / "scripts" / "probe_public_limits.py"
_SPEC = importlib.util.spec_from_file_location("probe_public_limits", _PROBE_PATH)
assert _SPEC and _SPEC.loader
_PROBE_MODULE = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_PROBE_MODULE)
probe = _PROBE_MODULE.probe


pytestmark = [pytest.mark.network, pytest.mark.limit]


async def test_live_items_search_paced_limit_probe_stays_below_rate_limit():
    statuses = await probe(count=3, interval=1.0, base_url="https://pure.mpg.de/rest")
    assert statuses == [200, 200, 200]

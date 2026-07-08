"""Live smoke tests against the public PuRe API.

Run only the offline tests with:
    pytest -m "not network"
"""

from __future__ import annotations

import pytest

from pure_mpg_mcp.client import PureClient


@pytest.mark.network
async def test_service_info_live():
    async with PureClient() as c:
        info = await c.service_info()
        assert isinstance(info, dict)


@pytest.mark.network
async def test_search_live():
    async with PureClient() as c:
        payload = await c.search_items(query={"match_all": {}}, size=2)
        assert payload["numberOfRecords"] > 0
        assert len(payload["records"]) == 2

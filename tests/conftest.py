import os

import httpx
import pytest

from fixtures_cone import cone_handler
from fixtures_enrich import enrich_handler
from fixtures_pure import mock_transport, pure_handler
from pure_mpg_mcp.client import PureClient
from pure_mpg_mcp.cone import ConeClient
from pure_mpg_mcp.enrichment import Enrichment


def pytest_collection_modifyitems(config, items):
    if os.getenv("PURE_RUN_LIMIT_TESTS") == "1":
        return
    skip_limit = pytest.mark.skip(reason="set PURE_RUN_LIMIT_TESTS=1 to run public API limit probes")
    for item in items:
        if "limit" in item.keywords:
            item.add_marker(skip_limit)


@pytest.fixture
async def pure() -> PureClient:
    """A PureClient wired to an in-memory httpx.MockTransport (see fixtures_pure.py)."""
    c = PureClient(base_url="https://pure.test/rest")
    mock_transport(c, pure_handler)
    async with c:
        yield c


@pytest.fixture
async def cone() -> ConeClient:
    """A ConeClient wired to an in-memory httpx.MockTransport (see fixtures_cone.py)."""
    c = ConeClient(base_url="https://pure.test/cone")
    mock_transport(c, cone_handler, base_url="https://pure.test/cone")
    async with c:
        yield c


@pytest.fixture
async def enrich(monkeypatch) -> Enrichment:
    """An Enrichment wired to an in-memory httpx.MockTransport (see fixtures_enrich.py)."""
    monkeypatch.setenv("PURE_CONTACT_EMAIL", "real@mpg.de")
    e = Enrichment()
    e._client = httpx.AsyncClient(transport=httpx.MockTransport(enrich_handler))
    yield e
    await e.aclose()

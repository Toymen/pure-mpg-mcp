import os

import pytest


def pytest_collection_modifyitems(config, items):
    if os.getenv("PURE_RUN_LIMIT_TESTS") == "1":
        return
    skip_limit = pytest.mark.skip(reason="set PURE_RUN_LIMIT_TESTS=1 to run public API limit probes")
    for item in items:
        if "limit" in item.keywords:
            item.add_marker(skip_limit)

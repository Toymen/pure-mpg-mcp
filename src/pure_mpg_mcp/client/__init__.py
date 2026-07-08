"""Thin async HTTP client for the public PuRe (PubMan) REST API.

Wraps https://pure.mpg.de/rest — read-only, anonymous (public) access only.
No authentication is performed; only endpoints that serve RELEASED, publicly
visible records are reachable through this client.
"""

from __future__ import annotations

from .base import BaseClient
from .contexts_feeds import ContextsFeedsMixin
from .items import ItemsMixin
from .ous import OusMixin
from .paging import PagingMixin


class PureClient(ItemsMixin, PagingMixin, OusMixin, ContextsFeedsMixin, BaseClient):
    """Minimal async wrapper over the PuRe REST API (public read surface)."""

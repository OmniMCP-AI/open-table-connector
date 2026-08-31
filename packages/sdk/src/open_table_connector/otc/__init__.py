"""Convenience facade for the OTC Python SDK.

The :mod:`open_table_connector.sdk` package contains the complete typed SDK.
This module is the short application-facing namespace documented by the
architecture: pure query preparation remains stateless, while physical
operations use one lazily configured default client.
"""

from __future__ import annotations

import atexit
import os
from threading import RLock
from typing import Any

import open_table_connector.sdk as _sdk

for _name in _sdk.__all__:
    globals()[_name] = getattr(_sdk, _name)

_lock = RLock()
_default_client: _sdk.Client | None = None


def _client() -> _sdk.Client:
    global _default_client
    with _lock:
        if _default_client is None:
            environ = dict(os.environ)
            _default_client = _sdk.Client.from_config(
                _sdk.load_client_config(environ=environ),
                descriptors=_sdk.discover_descriptors(),
                environ=environ,
            )
        return _default_client


def configure(client: _sdk.Client) -> _sdk.Client:
    """Install ``client`` as the process-local convenience client."""

    if not isinstance(client, _sdk.Client):
        raise TypeError("client must be an OTC Client")
    global _default_client
    with _lock:
        _default_client = client
    return client


def close_default_client() -> None:
    """Close and forget the lazily configured convenience client."""

    global _default_client
    with _lock:
        client = _default_client
        _default_client = None
    if client is not None:
        client.close()


def open(target: str | Any):
    """Open one physical Table through the default client."""

    return _client().open(target)


def collect(source: object):
    """Collect a DataFrame, Table, or Query through the default client."""

    return _client().collect(source)


def read(target: str | Any):
    """Open and read one physical table through the default client."""

    return _client().open(target).require_value().read()


def materialize(source: object, *, to: str | _sdk.TableDestination):
    """Create a destination table from any supported Table Source."""

    return _client().materialize(source, to=to)


def time_series(source: object, descriptor: _sdk.TemporalTableDescriptor):
    """Create a time-series view over a Table or target URI."""

    table = (
        source if isinstance(source, _sdk.Table) else _client().open(source).require_value()
    )
    return table.time_series(descriptor)


atexit.register(close_default_client)

__all__ = [
    *_sdk.__all__,
    "close_default_client",
    "collect",
    "configure",
    "materialize",
    "open",
    "read",
    "time_series",
]

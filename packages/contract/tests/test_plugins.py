from __future__ import annotations

import pytest
from open_table_connector.contract import ConnectorIdentity, PluginDescriptor


def _factory() -> object:
    return object()


def test_plugin_descriptor_normalizes_and_exposes_routes() -> None:
    descriptor = PluginDescriptor(
        " google_sheets ",
        ConnectorIdentity("google_sheets", "0.1.0", "1.0"),
        ("HTTPS", "gsheets"),
        _factory,
        ("docs.google.com",),
    )

    assert descriptor.name == "google_sheets"
    assert descriptor.schemes == ("https", "gsheets")
    assert descriptor.route_keys() == (("https", "docs.google.com"), ("gsheets", None))


@pytest.mark.parametrize(
    "kwargs",
    (
        {"schemes": (), "hosts": ()},
        {"schemes": ("csv", "csv"), "hosts": ()},
        {"schemes": ("csv",), "hosts": ("example.test",)},
    ),
)
def test_plugin_descriptor_rejects_invalid_routes(kwargs: dict[str, object]) -> None:
    with pytest.raises(ValueError):
        PluginDescriptor(
            "csv",
            ConnectorIdentity("csv", "0.1.0", "1.0"),
            kwargs["schemes"],
            _factory,
            kwargs["hosts"],
        )

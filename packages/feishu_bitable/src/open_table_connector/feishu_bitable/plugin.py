"""Provider-neutral registration metadata for Feishu Bitable."""

from __future__ import annotations

from .cli_adapter import feishu_bitable_cli_plugin

provider_plugin = feishu_bitable_cli_plugin

__all__ = ["provider_plugin"]

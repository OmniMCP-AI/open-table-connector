"""Framework-neutral Feishu Bitable records connector."""

from .connector import (
    FEISHU_BATCH_CREATE_LIMIT,
    FEISHU_API_ENDPOINT,
    FEISHU_MAX_RESPONSE_BYTES,
    FeishuBitableConnector,
    FeishuBitableReadOptions,
    FeishuBitableTableReadRequest,
)
from .cli_adapter import FeishuBitableCliAdapter, feishu_bitable_cli_plugin
from .identity import FEISHU_RECORD_ID_FIELD

__all__ = [
    "FEISHU_BATCH_CREATE_LIMIT",
    "FEISHU_API_ENDPOINT",
    "FEISHU_MAX_RESPONSE_BYTES",
    "FEISHU_RECORD_ID_FIELD",
    "FeishuBitableCliAdapter",
    "FeishuBitableConnector",
    "FeishuBitableReadOptions",
    "FeishuBitableTableReadRequest",
    "feishu_bitable_cli_plugin",
]

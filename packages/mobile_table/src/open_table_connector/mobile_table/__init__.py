"""OTC mobile table contract primitives."""

from .adapter import MobileHttpResponse, MobileTableAdapter
from .host import MobileTableHost, SdkMobileTableHost
from .models import (
    MobileCapabilities,
    MobileError,
    MobileField,
    MobileInspection,
    MobileReadPage,
    MobileRecord,
    MobileUpdateResult,
)
from .validation import CONTRACT, parse_request, validate_field_selection, validate_patch_size

__all__ = [
    "CONTRACT",
    "MobileCapabilities",
    "MobileError",
    "MobileField",
    "MobileInspection",
    "MobileReadPage",
    "MobileRecord",
    "MobileUpdateResult",
    "MobileHttpResponse",
    "MobileTableAdapter",
    "MobileTableHost",
    "SdkMobileTableHost",
    "parse_request",
    "validate_field_selection",
    "validate_patch_size",
]

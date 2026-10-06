"""Explicit, fail-closed MCP access policy."""

from __future__ import annotations

import json
import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from urllib.parse import unquote, urlsplit

from open_table_connector.contract import SCHEME_FILE, OperationRequest

_CREDENTIAL_KEYS = {"token", "password", "secret", "access_token", "credential"}
_PATH_KEYS = {
    "uri",
    "source_uri",
    "destination_uri",
    "path",
    "asset",
    "asset_path",
    "assets",
}


@dataclass(frozen=True, slots=True)
class AccessPolicy:
    allowed_roots: tuple[Path, ...]
    allowed_provider_ids: tuple[str, ...]
    allowed_document_origins: tuple[str, ...]
    credential_references: tuple[str, ...]

    def __post_init__(self):
        object.__setattr__(self, "allowed_roots", tuple(Path(item).resolve() for item in self.allowed_roots))
        object.__setattr__(self, "allowed_provider_ids", tuple(self.allowed_provider_ids))
        object.__setattr__(self, "allowed_document_origins", tuple(self.allowed_document_origins))
        object.__setattr__(self, "credential_references", tuple(self.credential_references))


def load_policy(path: Path) -> AccessPolicy:
    path = Path(path)
    if not path.is_absolute() or not path.exists():
        raise ValueError("explicit MCP policy file is required")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, Mapping) or set(payload) != {"allowed_roots", "allowed_provider_ids", "allowed_document_origins", "credential_references"}:
        raise ValueError("MCP policy keys mismatch")
    return AccessPolicy(tuple(Path(item) for item in payload["allowed_roots"]), tuple(payload["allowed_provider_ids"]), tuple(payload["allowed_document_origins"]), tuple(payload["credential_references"]))


def authorize(request: OperationRequest, policy: AccessPolicy) -> None:
    if request.target is None:
        raise PermissionError("MCP target is required")
    _authorize_value(request.target.uri, "uri", policy)
    _walk_arguments(request.arguments, policy)
    if policy.allowed_provider_ids and request.namespace not in policy.allowed_provider_ids:
        raise PermissionError("provider is not authorized")


def _walk_arguments(value: object, policy: AccessPolicy, key: str = "") -> None:
    if isinstance(value, Mapping):
        for child_key, child_value in value.items():
            child_name = str(child_key).casefold()
            if child_name in _CREDENTIAL_KEYS:
                raise PermissionError("credential values are not accepted in MCP arguments")
            _walk_arguments(child_value, policy, child_name)
        return
    if isinstance(value, (list, tuple)):
        for child in value:
            _walk_arguments(child, policy, key)
        return
    if isinstance(value, str) and key in _PATH_KEYS:
        _authorize_value(value, key, policy)


def _authorize_value(value: str, key: str, policy: AccessPolicy) -> None:
    parsed = urlsplit(value)
    if parsed.scheme == SCHEME_FILE:
        _authorize_local_path(Path(unquote(parsed.path)), policy)
        return
    if parsed.scheme:
        origin = f"{parsed.scheme}://{parsed.netloc}"
        if origin not in policy.allowed_document_origins:
            raise PermissionError("remote document origin is not authorized")
        return
    if key in {"asset", "asset_path", "path"} and (
        os.path.isabs(value) or ".." in PurePosixPath(value).parts
    ):
        if os.path.isabs(value):
            _authorize_local_path(Path(value), policy)
        else:
            raise PermissionError("asset path escapes its configured root")
    elif os.path.isabs(value):
        _authorize_local_path(Path(value), policy)


def _authorize_local_path(path: Path, policy: AccessPolicy) -> None:
    parent = path.parent.resolve()
    target = path.resolve(strict=False)
    if not any(
        root in (target, parent) or root in target.parents or root in parent.parents
        for root in policy.allowed_roots
    ):
        raise PermissionError("local target is outside allowed MCP roots")
    if path.exists() and path.is_symlink():
        raise PermissionError("symlink targets are not authorized")


__all__ = ["AccessPolicy", "authorize", "load_policy"]

"""Deployment-owned credential references and scoped leases."""

from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType


class CredentialLease:
    def __init__(self, reference: str | None, connector_id: str, values: Mapping[str, str]) -> None:
        self.reference = reference
        self.connector_id = connector_id
        self._values = {str(key): str(value) for key, value in values.items()}
        self.disposed = False

    @property
    def values(self) -> Mapping[str, str]:
        if self.disposed:
            raise RuntimeError("credential lease is disposed")
        return MappingProxyType(self._values)

    def dispose(self) -> None:
        self._values.clear()
        self.disposed = True

    def __enter__(self) -> "CredentialLease":
        return self

    def __exit__(self, *_: object) -> None:
        self.dispose()


class CredentialResolver:
    def __init__(
        self,
        references: Mapping[str, Mapping[str, Mapping[str, str]]] | None = None,
    ) -> None:
        self._references = {
            str(connector): {
                str(reference): dict(values) for reference, values in connector_values.items()
            }
            for connector, connector_values in (references or {}).items()
        }
        self.resolve_count = 0
        self.last_lease: CredentialLease | None = None

    def resolve(self, reference: str | None, connector_id: str) -> CredentialLease:
        self.resolve_count += 1
        if reference is None:
            values: Mapping[str, str] = {}
        else:
            try:
                values = self._references[connector_id][reference]
            except KeyError as exc:
                raise PermissionError("credential reference is not authorized for connector") from exc
        lease = CredentialLease(reference, connector_id, values)
        self.last_lease = lease
        return lease


__all__ = ["CredentialLease", "CredentialResolver"]

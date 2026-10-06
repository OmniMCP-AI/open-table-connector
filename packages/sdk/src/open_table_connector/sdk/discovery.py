"""Lazy operation catalog and truthful endpoint capability resolution."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from importlib.metadata import EntryPoint, entry_points
from urllib.parse import urlsplit

from open_table_connector.contract import (
    SCHEME_FILE,
    CapabilityObservation,
    OperationDescriptor,
    TargetSelector,
)

from .result import CommitState, ErrorCode, ErrorInfo, OperationResult, Outcome, VerificationState

OPERATION_CATALOG_GROUP = "open_table_connector.operation_catalogs.v1"
OPERATION_HANDLER_GROUP = "open_table_connector.operation_handlers.v1"


def _failure(code: ErrorCode, message: str, **details: object) -> OperationResult[None]:
    return OperationResult(
        None,
        Outcome.REJECTED,
        CommitState.NOT_STARTED,
        VerificationState.SKIPPED,
        (),
        error=ErrorInfo(code, message, details),
    )


class OperationCatalog:
    def __init__(self, descriptors: Iterable[OperationDescriptor] = ()) -> None:
        self._descriptors: dict[tuple[str, str, str], OperationDescriptor] = {}
        for descriptor in descriptors:
            self.register(descriptor)

    @classmethod
    def default(cls) -> OperationCatalog:
        descriptors: list[OperationDescriptor] = []
        try:
            from open_table_connector.spreadsheets.operation_catalog import operation_catalog

            descriptors.extend(operation_catalog())
        except (ImportError, ModuleNotFoundError):
            pass
        descriptors.extend(discover_operation_descriptors())
        # The built-in spreadsheet package also publishes an entry point.  It
        # is the same static catalog, so retain the first deterministic copy.
        unique: dict[tuple[str, str, str], OperationDescriptor] = {}
        for descriptor in descriptors:
            key = (descriptor.capability.split(".", 1)[0], descriptor.operation_id, descriptor.version)
            unique.setdefault(key, descriptor)
        return cls(unique.values())

    def register(self, descriptor: OperationDescriptor) -> None:
        if not isinstance(descriptor, OperationDescriptor):
            raise TypeError("operation catalog entries must be OperationDescriptor values")
        namespace = descriptor.capability.split(".", 1)[0]
        key = (namespace, descriptor.operation_id, descriptor.version)
        if key in self._descriptors:
            raise ValueError("duplicate operation descriptor")
        self._descriptors[key] = descriptor

    def describe(self, namespace: str | None = None, operation_id: str | None = None, version: str | None = None) -> tuple[OperationDescriptor, ...]:
        values = self._descriptors.values()
        selected = [
            descriptor
            for descriptor in values
            if (namespace is None or descriptor.capability.split(".", 1)[0] == namespace)
            and (operation_id is None or descriptor.operation_id == operation_id)
            and (version is None or descriptor.version == version)
        ]
        return tuple(sorted(selected, key=lambda item: (item.operation_id, item.version)))

    def get(self, namespace: str, operation_id: str, version: str) -> OperationDescriptor | None:
        return self._descriptors.get((namespace, operation_id, version))

    def __iter__(self):
        return iter(self.describe())


def discover_operation_descriptors(entries: Iterable[EntryPoint] | None = None) -> tuple[OperationDescriptor, ...]:
    selected = entry_points() if entries is None else tuple(entries)
    if hasattr(selected, "select"):
        selected = selected.select(group=OPERATION_CATALOG_GROUP)
    result: list[OperationDescriptor] = []
    for entry in sorted(selected, key=lambda item: (item.name, item.value)):
        try:
            loaded = entry.load()
        except (ImportError, ModuleNotFoundError):
            # Optional operation packages must not make core help unusable.
            continue
        values = loaded() if callable(loaded) else loaded
        if isinstance(values, OperationDescriptor):
            values = (values,)
        result.extend(values)
    return tuple(result)


def _target(value: TargetSelector | str | Mapping[str, object]) -> TargetSelector:
    if isinstance(value, TargetSelector):
        return value
    if isinstance(value, Mapping):
        return TargetSelector(str(value["uri"]), value.get("sheet"), value.get("object_id"))
    return TargetSelector(value)


def resolve_capabilities(client, target: TargetSelector | str, *, catalog: OperationCatalog | None = None) -> OperationResult[CapabilityObservation]:
    selected_catalog = catalog or OperationCatalog.default()
    target_selector = _target(target)
    try:
        endpoint = target_selector.uri
        descriptor = client._registry.descriptor_for(endpoint)
    except AttributeError:
        try:
            from open_table_connector.contract import parse_adapter_endpoint

            endpoint = parse_adapter_endpoint(target_selector.uri)
            descriptor = client._registry.descriptor_for(endpoint)
        except Exception:
            return _failure(ErrorCode.INVALID_TARGET, "target could not be routed")
    except Exception:
        return _failure(ErrorCode.INVALID_TARGET, "target could not be routed")

    is_local = urlsplit(target_selector.uri).scheme == SCHEME_FILE
    resolution = "static" if is_local else "live"
    if not is_local:
        try:
            client._registry.connector_for(endpoint)
        except Exception:
            return OperationResult(
                None,
                Outcome.UNKNOWN,
                CommitState.UNKNOWN,
                VerificationState.UNAVAILABLE,
                (),
                error=ErrorInfo(ErrorCode.AUTHENTICATION, "live capability state is unavailable"),
            )
    capabilities = {
        f"{item.capability_id}/{item.capability_version}"
        for item in getattr(descriptor, "capabilities", ())
    }
    operations = tuple(
        item for item in selected_catalog
        if item.capability in capabilities
    )
    provider_identity = getattr(descriptor, "identity", None)
    provider = getattr(provider_identity, "connector_id", "unknown")
    provider_version = getattr(provider_identity, "connector_version", None)
    observation = CapabilityObservation(
        target_selector,
        provider,
        provider_version,
        resolution,
        operations,
    )
    return OperationResult(
        observation,
        Outcome.SUCCEEDED,
        CommitState.NOT_APPLICABLE,
        VerificationState.PASSED,
        (),
    )


__all__ = ["OPERATION_CATALOG_GROUP", "OPERATION_HANDLER_GROUP", "OperationCatalog", "discover_operation_descriptors", "resolve_capabilities"]

# Python API Inventory

Generated from public exports and runtime signatures. Regenerate with
`uv run --all-packages python scripts/generate_reference_manuals.py`.

Start with the [SDK manual](../user-guide/sdk-manual.md) for behavior and examples, and
the [component manual](../user-guide/components.md) for provider prerequisites. A public
name or callable signature does not prove provider support. Returned handles
are obtained through their owning client/session, not constructed directly.

Annotations are printed as declared; string annotations are not evaluated.
Private implementation methods are excluded. Inherited public OTC methods
are included; third-party base-class methods are omitted.

## open_table_connector.sdk

| Name | Kind | Definition |
| --- | --- | --- |
| `A1Rectangle` | class | `(worksheet_name: 'str \| None', start_address: 'str', end_address: 'str', start_column: 'int', start_row: 'int', end_column: 'int', end_row: 'int') -> None` [source](../../packages/formulas/src/open_table_connector/formulas/ranges.py) |
| `AbortDisposition` | enum | `(value, names=None, *, module=None, qualname=None, type=None, start=1, boundary=None)` [source](../../packages/sdk/src/open_table_connector/sdk/temporal.py) |
| `AggregateFunction` | enum | `(value, names=None, *, module=None, qualname=None, type=None, start=1, boundary=None)` [source](../../packages/timeseries/src/open_table_connector/timeseries/plan.py) |
| `AggregateMeasure` | class | `(output_field: 'str', function: 'AggregateFunction', value_field: 'str \| None') -> None` [source](../../packages/timeseries/src/open_table_connector/timeseries/plan.py) |
| `ArtifactAccess` | class | `(client)` [source](../../packages/sdk/src/open_table_connector/sdk/artifacts.py) |
| `BaseModeDestination` | class | `(container: 'TableURI \| str', table_name: 'str') -> None` [source](../../packages/sdk/src/open_table_connector/sdk/model.py) |
| `BaseModeTableAddress` | class | `(container: 'TableURI \| str', table_id: 'str') -> None` [source](../../packages/sdk/src/open_table_connector/sdk/model.py) |
| `CalculationState` | enum | `(value, names=None, *, module=None, qualname=None, type=None, start=1, boundary=None)` [source](../../packages/formulas/src/open_table_connector/formulas/observations.py) |
| `CalculationTrigger` | enum | `(value, names=None, *, module=None, qualname=None, type=None, start=1, boundary=None)` [source](../../packages/formulas/src/open_table_connector/formulas/observations.py) |
| `CalendarBucket` | class | `(count: 'int', unit: 'CalendarUnit', timezone: 'str', week_start: 'int', origin: 'str', offset_ns: 'int' = 0) -> None` [source](../../packages/timeseries/src/open_table_connector/timeseries/plan.py) |
| `CapabilitySet` | class | `(capability_ids: 'tuple[str, ...]', modes: 'tuple[TableMode, ...]' = (), details: 'Mapping[str, Any]' = <factory>) -> None` [source](../../packages/sdk/src/open_table_connector/sdk/table.py) |
| `Client` | class | `(*, registry: 'ConnectorRegistry') -> 'None'` [source](../../packages/sdk/src/open_table_connector/sdk/client.py) |
| `ClientConfig` | class | `(providers: 'Mapping[str, ProviderConfig]' = <factory>, credentials: 'Mapping[str, Mapping[str, CredentialBinding]]' = <factory>) -> None` [source](../../packages/sdk/src/open_table_connector/sdk/config.py) |
| `CommitState` | enum | `(value, names=None, *, module=None, qualname=None, type=None, start=1, boundary=None)` [source](../../packages/sdk/src/open_table_connector/sdk/result.py) |
| `ConfiguredPlugin` | class | `(descriptor: 'PluginDescriptor', config: 'ProviderConfig') -> None` [source](../../packages/sdk/src/open_table_connector/sdk/registry.py) |
| `ConnectorRegistry` | class | `(connectors: 'Iterable[TableConnector] \| None' = None, *, resolver: 'CredentialResolver \| None' = None, environ: 'Mapping[str, str] \| None' = None, transports: 'Mapping[str, Any] \| None' = None) -> 'None'` [source](../../packages/sdk/src/open_table_connector/sdk/registry.py) |
| `CredentialBinding` | class | `(env: 'str') -> None` [source](../../packages/sdk/src/open_table_connector/sdk/config.py) |
| `CredentialLease` | class | `(values: 'Mapping[str, str]') -> 'None'` [source](../../packages/sdk/src/open_table_connector/sdk/credentials.py) |
| `CredentialResolver` | class | `(*args, **kwargs)` [source](../../packages/sdk/src/open_table_connector/sdk/credentials.py) |
| `DatabaseTableAddress` | class | `(database: 'TableURI \| str', name: 'QualifiedTableName') -> None` [source](../../packages/sdk/src/open_table_connector/sdk/model.py) |
| `DirectDestination` | class | `(uri: 'TableURI \| str') -> None` [source](../../packages/sdk/src/open_table_connector/sdk/model.py) |
| `DirectTableAddress` | class | `(uri: 'TableURI \| str') -> None` [source](../../packages/sdk/src/open_table_connector/sdk/model.py) |
| `EXCEL_A1` | constant | `'excel-a1'`  |
| `EnvironmentCredentialResolver` | class | `(config: 'ClientConfig', environ: 'Mapping[str, str]') -> 'None'` [source](../../packages/sdk/src/open_table_connector/sdk/credentials.py) |
| `ErrorCode` | enum | `(value, names=None, *, module=None, qualname=None, type=None, start=1, boundary=None)` [source](../../packages/sdk/src/open_table_connector/sdk/result.py) |
| `ErrorInfo` | class | `(code: 'ErrorCode', message: 'str', safe_details: 'Mapping[str, Any]' = <factory>, reconciliation: 'ReconciliationReference \| None' = None) -> None` [source](../../packages/sdk/src/open_table_connector/sdk/result.py) |
| `ExistingTableAddress` | constant | `open_table_connector.sdk.model.DirectTableAddress \| open_table_connector.sdk.model.DatabaseTableAddress \| open_table_connector.sdk.model.BaseModeTableAddress \| open_table_connector.sdk.model.SheetModeTableAddress`  |
| `FEISHU_BITABLE` | constant | `'feishu-bitable'`  |
| `FIELD_READ` | constant | `CapabilityIdentity(capability_id='formula.field.read', capability_version='1.0')`  |
| `FIELD_RECALCULATE` | constant | `CapabilityIdentity(capability_id='formula.field.recalculate', capability_version='1.0')`  |
| `FIELD_SET` | constant | `CapabilityIdentity(capability_id='formula.field.set', capability_version='1.0')`  |
| `FIELD_VALUES_READ` | constant | `CapabilityIdentity(capability_id='formula.field.values.read', capability_version='1.0')`  |
| `FieldFormulaObservation` | class | `(table_uri: 'TableURI \| str', field_id: 'str', field_name: 'str', expression: 'FormulaExpression', result_type: 'str \| None', observed_revision: 'str') -> None` [source](../../packages/formulas/src/open_table_connector/formulas/observations.py) |
| `FieldFormulaTarget` | class | `(table: '_TTable', field: 'FieldRef') -> None` [source](../../packages/formulas/src/open_table_connector/formulas/model.py) |
| `FieldFormulaValueObservation` | class | `(table_uri: 'TableURI \| str', field_id: 'str', field_name: 'str', values: 'tuple[FormulaRecordValue, ...]', calculation_state: 'CalculationState', calculation_trigger: 'CalculationTrigger', dependency_scope: 'str', observed_revision: 'str') -> None` [source](../../packages/formulas/src/open_table_connector/formulas/observations.py) |
| `FieldFormulaView` | class | `(client: 'Client', *, owner_token: 'object', connector_id: 'str', extension: 'FormulaConnectorExtension', table_binding: 'TableBinding', binding: 'FieldFormulaBinding[Table]') -> 'None'` [source](../../packages/sdk/src/open_table_connector/sdk/formula.py) |
| `FieldRecalculationScope` | enum | `(value, names=None, *, module=None, qualname=None, type=None, start=1, boundary=None)` [source](../../packages/formulas/src/open_table_connector/formulas/model.py) |
| `FieldRef` | class | `(name: 'str \| None' = None, field_id: 'str \| None' = None) -> None` [source](../../packages/formulas/src/open_table_connector/formulas/model.py) |
| `FillMode` | enum | `(value, names=None, *, module=None, qualname=None, type=None, start=1, boundary=None)` [source](../../packages/timeseries/src/open_table_connector/timeseries/plan.py) |
| `FillRule` | class | `(field: 'str', mode: 'FillMode', value: 'JsonScalar') -> None` [source](../../packages/timeseries/src/open_table_connector/timeseries/plan.py) |
| `FixedBucket` | class | `(width_ns: 'int', origin: 'str', offset_ns: 'int' = 0) -> None` [source](../../packages/timeseries/src/open_table_connector/timeseries/plan.py) |
| `FormulaCapabilityDetails` | class | `(target_kind: 'str', dialects: 'tuple[str, ...]', max_cells_per_operation: 'int \| None', max_expression_bytes: 'int', recalculation_scopes: 'tuple[str, ...]', calculation_states: 'tuple[CalculationState, ...]', mutation_atomicity: 'MutationAtomicity', revision_enforcement: 'RevisionEnforcement', idempotency_strength: 'IdempotencyStrength') -> None` [source](../../packages/formulas/src/open_table_connector/formulas/observations.py) |
| `FormulaCapabilitySet` | class | `(capabilities: 'tuple[CapabilityIdentity, ...]', details: 'FormulaCapabilityDetails') -> None` [source](../../packages/formulas/src/open_table_connector/formulas/observations.py) |
| `FormulaCell` | class | `(address: 'str', expression: 'FormulaExpression') -> None` [source](../../packages/formulas/src/open_table_connector/formulas/observations.py) |
| `FormulaError` | class | `(signature unavailable; see source)` [source](../../packages/formulas/src/open_table_connector/formulas/errors.py) |
| `FormulaErrorValue` | class | `(code: 'str') -> None` [source](../../packages/formulas/src/open_table_connector/formulas/observations.py) |
| `FormulaExpression` | class | `(text: 'str', dialect: 'str') -> None` [source](../../packages/formulas/src/open_table_connector/formulas/model.py) |
| `FormulaMutation` | class | `(target_kind: 'str', affected_count: 'int', formula_observation: 'GridFormulaObservation \| FieldFormulaObservation', revision_before: 'str \| None', revision_after: 'str') -> None` [source](../../packages/formulas/src/open_table_connector/formulas/observations.py) |
| `FormulaRecordValue` | class | `(record_id: 'str', value: 'FormulaValue') -> None` [source](../../packages/formulas/src/open_table_connector/formulas/observations.py) |
| `FormulaResourceLimits` | class | `(max_cells: 'int \| None' = None, max_records: 'int \| None' = None, max_response_bytes: 'int \| None' = None, timeout_seconds: 'float \| None' = None, max_expression_bytes: 'int \| None' = None) -> None` [source](../../packages/formulas/src/open_table_connector/formulas/model.py) |
| `FormulaValue` | class | `(kind: 'str', value: 'object' = None, logical_type: 'str \| None' = None) -> None` [source](../../packages/formulas/src/open_table_connector/formulas/observations.py) |
| `FormulaValueCell` | class | `(address: 'str', value: 'FormulaValue') -> None` [source](../../packages/formulas/src/open_table_connector/formulas/observations.py) |
| `GOOGLE_SHEETS_A1` | constant | `'google-sheets-a1'`  |
| `GRID_READ` | constant | `CapabilityIdentity(capability_id='formula.grid.read', capability_version='1.0')`  |
| `GRID_RECALCULATE` | constant | `CapabilityIdentity(capability_id='formula.grid.recalculate', capability_version='1.0')`  |
| `GRID_SET` | constant | `CapabilityIdentity(capability_id='formula.grid.set', capability_version='1.0')`  |
| `GRID_VALUES_READ` | constant | `CapabilityIdentity(capability_id='formula.grid.values.read', capability_version='1.0')`  |
| `GridFormulaObservation` | class | `(worksheet_id: 'str', requested_range: 'str', formulas: 'tuple[FormulaCell, ...]', observed_revision: 'str') -> None` [source](../../packages/formulas/src/open_table_connector/formulas/observations.py) |
| `GridFormulaTarget` | class | `(grid: 'TableURI \| str', worksheet: 'WorksheetRef') -> None` [source](../../packages/formulas/src/open_table_connector/formulas/model.py) |
| `GridFormulaValueObservation` | class | `(worksheet_id: 'str', requested_range: 'str', values: 'tuple[FormulaValueCell, ...]', calculation_state: 'CalculationState', calculation_trigger: 'CalculationTrigger', dependency_scope: 'str', observed_revision: 'str') -> None` [source](../../packages/formulas/src/open_table_connector/formulas/observations.py) |
| `GridFormulaView` | class | `(client: 'Client', *, owner_token: 'object', connector_id: 'str', extension: 'FormulaConnectorExtension', binding: 'GridFormulaBinding') -> 'None'` [source](../../packages/sdk/src/open_table_connector/sdk/formula.py) |
| `GridRecalculationScope` | enum | `(value, names=None, *, module=None, qualname=None, type=None, start=1, boundary=None)` [source](../../packages/formulas/src/open_table_connector/formulas/model.py) |
| `IdempotencyStrength` | enum | `(value, names=None, *, module=None, qualname=None, type=None, start=1, boundary=None)` [source](../../packages/formulas/src/open_table_connector/formulas/observations.py) |
| `LegacyConnectorAdapterBridge` | class | `(adapter: 'ConnectorAdapter') -> 'None'` [source](../../packages/sdk/src/open_table_connector/sdk/connector.py) |
| `MATERIALIZE_CREATE_CAPABILITY` | constant | `CapabilityIdentity(capability_id='table.materialize.create', capability_version='1.0')`  |
| `MAYBE_BASE` | constant | `'maybe-base'`  |
| `MAYBE_SHEET_A1` | constant | `'maybe-sheet-a1'`  |
| `ManagedSnapshot` | class | `(logical_target: 'TableURI', stage_id: 'str', snapshot_id: 'str', snapshot_reference: 'str', descriptor_hash: 'str', committed_at: 'str', _binding: 'TableBinding', _owner_client_id: 'str', retention_expires_at: 'str \| None' = None) -> None` [source](../../packages/sdk/src/open_table_connector/sdk/temporal.py) |
| `ManagedSnapshotState` | class | `(snapshot: 'ManagedSnapshot', schema: 'pa.Schema') -> None` [source](../../packages/sdk/src/open_table_connector/sdk/temporal.py) |
| `ManagedStage` | class | `(logical_target: 'TableURI', physical_target: 'TableURI', stage_id: 'str', idempotency_key: 'str', descriptor_hash: 'str', artifact_hash: 'str', staged_at: 'str', _binding: 'TableBinding', _owner_client_id: 'str', lease_expires_at: 'str \| None' = None) -> None` [source](../../packages/sdk/src/open_table_connector/sdk/temporal.py) |
| `MaterializationRequest` | class | `(source: 'pl.DataFrame', destination: 'TableDestination', profile: 'str', idempotency_key: 'str') -> None` [source](../../packages/sdk/src/open_table_connector/sdk/materialization.py) |
| `MutationAtomicity` | enum | `(value, names=None, *, module=None, qualname=None, type=None, start=1, boundary=None)` [source](../../packages/formulas/src/open_table_connector/formulas/observations.py) |
| `NativeSql` | class | `(client: 'Client', target: 'str \| TableURI') -> 'None'` [source](../../packages/sdk/src/open_table_connector/sdk/sql.py) |
| `NativeSqlResourceLimits` | class | `(max_rows: 'int' = 100000, max_bytes: 'int' = 134217728, max_duration_ms: 'int' = 30000) -> None` [source](../../packages/sdk/src/open_table_connector/sdk/sql.py) |
| `OPERATION_CATALOG_GROUP` | constant | `'open_table_connector.operation_catalogs.v1'`  |
| `OPERATION_HANDLER_GROUP` | constant | `'open_table_connector.operation_handlers.v1'`  |
| `OTCError` | class | `(message: 'str', result: 'OperationResult[Any]') -> 'None'` [source](../../packages/sdk/src/open_table_connector/sdk/result.py) |
| `OperationCatalog` | class | `(descriptors: 'Iterable[OperationDescriptor]' = ()) -> 'None'` [source](../../packages/sdk/src/open_table_connector/sdk/discovery.py) |
| `OperationResult` | class | `(value: 'T \| None', outcome: 'Outcome', commit: 'CommitState', verification: 'VerificationState', receipts: 'tuple[Receipt, ...]', continuation: 'str \| None' = None, warnings: 'tuple[OperationWarning, ...]' = (), error: 'ErrorInfo \| None' = None) -> None` [source](../../packages/sdk/src/open_table_connector/sdk/result.py) |
| `OperationWarning` | class | `(code: 'str', message: 'str', safe_details: 'Mapping[str, Any]' = <factory>) -> None` [source](../../packages/sdk/src/open_table_connector/sdk/result.py) |
| `Outcome` | enum | `(value, names=None, *, module=None, qualname=None, type=None, start=1, boundary=None)` [source](../../packages/sdk/src/open_table_connector/sdk/result.py) |
| `PORTABLE_TABLE_PROFILE_V1` | constant | `'otc.portable-table/v1'`  |
| `PolarsPlanMapper` | class | `()` [source](../../packages/sdk/src/open_table_connector/sdk/sql.py) |
| `PortablePredicate` | class | `(expression: 'str \| None' = None, parameters: 'Mapping[str, Any]' = <factory>, kind: 'PredicateKind' = <PredicateKind.SQL: 'sql'>) -> None` [source](../../packages/sdk/src/open_table_connector/sdk/predicates.py) |
| `PredicateKind` | enum | `(value, names=None, *, module=None, qualname=None, type=None, start=1, boundary=None)` [source](../../packages/sdk/src/open_table_connector/sdk/predicates.py) |
| `QualifiedTableName` | class | `(table: 'str', schema: 'str \| None' = None, catalog: 'str \| None' = None) -> None` [source](../../packages/sdk/src/open_table_connector/sdk/model.py) |
| `Query` | class | `(lane: 'QueryLane', statement: 'str', sources: 'Mapping[str, object]', parameters: 'Mapping[str, Any]' = <factory>, limits: 'object' = <factory>, _definition: 'object \| None' = None) -> None` [source](../../packages/sdk/src/open_table_connector/sdk/query.py) |
| `QueryLane` | enum | `(value, names=None, *, module=None, qualname=None, type=None, start=1, boundary=None)` [source](../../packages/sdk/src/open_table_connector/sdk/query.py) |
| `RecalculationObservation` | class | `(target_kind: 'str', requested_scope: 'str', effective_scope: 'str', revision_before: 'str \| None', revision_after: 'str \| None', provider_status: 'str', calculation_state: 'CalculationState', verification: 'str', value_observation: 'GridFormulaValueObservation \| FieldFormulaValueObservation \| None') -> None` [source](../../packages/formulas/src/open_table_connector/formulas/observations.py) |
| `Receipt` | class | `(kind: 'str', operation: 'str', connector_id: 'str \| None' = None, capability: 'str \| None' = None, safe_target: 'TableURI \| None' = None, mode: 'TableMode \| None' = None, details: 'Mapping[str, Any]' = <factory>) -> None` [source](../../packages/sdk/src/open_table_connector/sdk/result.py) |
| `ReconciliationReference` | class | `(operation_id: 'str', connector_id: 'str \| None' = None, idempotency_key: 'str \| None' = None, expires_at: 'str \| None' = None) -> None` [source](../../packages/sdk/src/open_table_connector/sdk/result.py) |
| `RevisionEnforcement` | enum | `(value, names=None, *, module=None, qualname=None, type=None, start=1, boundary=None)` [source](../../packages/formulas/src/open_table_connector/formulas/observations.py) |
| `SchemaPolicy` | enum | `(value, names=None, *, module=None, qualname=None, type=None, start=1, boundary=None)` [source](../../packages/sdk/src/open_table_connector/sdk/model.py) |
| `SheetModeDestination` | class | `(grid: 'TableURI \| str', anchor: 'str', header: 'bool', worksheet: 'str \| None' = None) -> None` [source](../../packages/sdk/src/open_table_connector/sdk/model.py) |
| `SheetModeTableAddress` | class | `(grid: 'TableURI \| str', table_id: 'str') -> None` [source](../../packages/sdk/src/open_table_connector/sdk/model.py) |
| `SheetRangeSource` | class | `(grid: 'TableURI \| str', cell_range: 'str', header: 'bool', schema: 'pl.Schema \| None', schema_policy: 'SchemaPolicy', observed_revision: 'str \| None' = None, _owner_token: 'object \| None' = None) -> None` [source](../../packages/sdk/src/open_table_connector/sdk/model.py) |
| `SqlResourceLimits` | class | `(max_source_rows: 'int' = 1000000, max_source_bytes: 'int' = 268435456, max_total_input_rows: 'int' = 2000000, max_total_input_bytes: 'int' = 536870912, max_intermediate_rows: 'int' = 2000000, max_intermediate_bytes: 'int' = 536870912, max_output_rows: 'int' = 100000, max_output_bytes: 'int' = 134217728, max_duration_ms: 'int' = 30000) -> None` [source](../../packages/sdk/src/open_table_connector/sdk/query.py) |
| `Table` | class | `(client: 'Client', binding: 'TableBinding') -> 'None'` [source](../../packages/sdk/src/open_table_connector/sdk/table.py) |
| `TableBinding` | class | `(uri: 'TableURI', mode: 'TableMode', schema: 'pl.Schema \| None', observed_revision: 'str \| None', connector_id: 'str', profile: 'str \| None' = None, row_count: 'int \| None' = None, schema_fingerprint: 'str \| None' = None, content_fingerprint: 'str \| None' = None, address: 'ExistingTableAddress \| None' = None, schema_observed: 'bool' = True, layout_binding: 'Mapping[str, Any] \| None' = None) -> None` [source](../../packages/sdk/src/open_table_connector/sdk/table.py) |
| `TableConnector` | class | `(*args, **kwargs)` [source](../../packages/sdk/src/open_table_connector/sdk/connector.py) |
| `TableDestination` | constant | `open_table_connector.sdk.model.DirectDestination \| open_table_connector.sdk.model.BaseModeDestination \| open_table_connector.sdk.model.SheetModeDestination`  |
| `TableInspection` | class | `(uri: 'TableURI', mode: 'TableMode', schema: 'pl.Schema', row_count: 'int \| None' = None, observed_revision: 'str \| None' = None, facts: 'Mapping[str, Any]' = <factory>) -> None` [source](../../packages/sdk/src/open_table_connector/sdk/table.py) |
| `TableLayoutSession` | class | `(table, connector, payload: 'Mapping[str, Any]') -> 'None'` [source](../../packages/sdk/src/open_table_connector/sdk/layout.py) |
| `TableMode` | enum | `(value, names=None, *, module=None, qualname=None, type=None, start=1, boundary=None)` [source](../../packages/sdk/src/open_table_connector/sdk/model.py) |
| `TableTransaction` | class | `(table: 'Table', *, idempotency_key: 'str \| None' = None) -> 'None'` [source](../../packages/sdk/src/open_table_connector/sdk/table.py) |
| `TemporalConnectorExtension` | class | `(*args, **kwargs)` [source](../../packages/sdk/src/open_table_connector/sdk/temporal.py) |
| `TemporalResourceLimits` | class | `(max_rows: 'int' = 100000, max_bytes: 'int' = 134217728, max_duration_ms: 'int' = 30000) -> None` [source](../../packages/sdk/src/open_table_connector/sdk/temporal.py) |
| `TemporalTableDescriptor` | class | `(time_field: 'str', timezone: 'str', precision: 'TimestampPrecision', series_key_fields: 'tuple[str, ...]', tag_fields: 'tuple[str, ...]', value_fields: 'tuple[str, ...]', ingestion_time_field: 'str \| None', duplicate_policy: 'DuplicatePolicy', ordering: 'TemporalOrdering') -> None` [source](../../packages/timeseries/src/open_table_connector/timeseries/descriptor.py) |
| `TimeSeriesView` | class | `(table: 'Table', descriptor: 'TemporalTableDescriptor') -> 'None'` [source](../../packages/sdk/src/open_table_connector/sdk/temporal.py) |
| `VerificationState` | enum | `(value, names=None, *, module=None, qualname=None, type=None, start=1, boundary=None)` [source](../../packages/sdk/src/open_table_connector/sdk/result.py) |
| `WorkbookAccess` | class | `(client: 'Client') -> 'None'` [source](../../packages/sdk/src/open_table_connector/sdk/workbook.py) |
| `WorksheetRef` | class | `(name: 'str \| None' = None, worksheet_id: 'str \| None' = None) -> None` [source](../../packages/formulas/src/open_table_connector/formulas/model.py) |
| `all_rows` | function | `() -> 'PortablePredicate'` [source](../../packages/sdk/src/open_table_connector/sdk/predicates.py) |
| `apply_credential_overrides` | function | `(config: 'ClientConfig', overrides: 'Mapping[str, str]') -> 'ClientConfig'` [source](../../packages/sdk/src/open_table_connector/sdk/credentials.py) |
| `capture_workbook_snapshot` | function | `(client, target: 'TargetSelector \| str', directory) -> 'OperationResult[WorkbookSnapshot]'` [source](../../packages/sdk/src/open_table_connector/sdk/snapshots.py) |
| `discover_configured_plugins` | function | `(config: 'ClientConfig', *, entries: 'Iterable[EntryPoint] \| None' = None) -> 'tuple[ConfiguredPlugin, ...]'` [source](../../packages/sdk/src/open_table_connector/sdk/registry.py) |
| `discover_descriptors` | function | `(entries: 'Iterable[EntryPoint] \| None' = None) -> 'tuple[PluginDescriptor, ...]'` [source](../../packages/sdk/src/open_table_connector/sdk/registry.py) |
| `discover_operation_descriptors` | function | `(entries: 'Iterable[EntryPoint] \| None' = None) -> 'tuple[OperationDescriptor, ...]'` [source](../../packages/sdk/src/open_table_connector/sdk/discovery.py) |
| `discover_operation_handlers` | function | `() -> 'tuple[tuple[str, str, str, Handler], ...]'` [source](../../packages/sdk/src/open_table_connector/sdk/operations.py) |
| `execute_operation` | function | `(client, request: 'OperationRequest', options: 'ExecutionOptions', *, catalog: 'OperationCatalog \| None' = None) -> 'OperationResult[object]'` [source](../../packages/sdk/src/open_table_connector/sdk/operations.py) |
| `load_client_config` | function | `(explicit: 'str \| Path \| None' = None, *, environ: 'Mapping[str, str] \| None' = None, home: 'Path \| None' = None) -> 'ClientConfig'` [source](../../packages/sdk/src/open_table_connector/sdk/config.py) |
| `parse_credential_overrides` | function | `(values: 'Sequence[str]') -> 'Mapping[str, str]'` [source](../../packages/sdk/src/open_table_connector/sdk/credentials.py) |
| `register_operation_handler` | function | `(namespace: 'str', operation_id: 'str', version: 'str', handler: 'Handler') -> 'None'` [source](../../packages/sdk/src/open_table_connector/sdk/operations.py) |
| `resolve_capabilities` | function | `(client, target: 'TargetSelector \| str', *, catalog: 'OperationCatalog \| None' = None) -> 'OperationResult[CapabilityObservation]'` [source](../../packages/sdk/src/open_table_connector/sdk/discovery.py) |
| `resolve_config_path` | function | `(explicit: 'str \| Path \| None', environ: 'Mapping[str, str]', *, home: 'Path \| None' = None) -> 'Path \| None'` [source](../../packages/sdk/src/open_table_connector/sdk/config.py) |
| `sql` | function | `(statement: 'str', *, sources: 'dict[str, object]', parameters: 'dict[str, Any] \| None' = None, limits: 'SqlResourceLimits \| None' = None) -> 'Query'` [source](../../packages/sdk/src/open_table_connector/sdk/sql.py) |

### A1Rectangle

| Field | Declared type |
| --- | --- |
| `end_address` | `str` |
| `end_column` | `int` |
| `end_row` | `int` |
| `start_address` | `str` |
| `start_column` | `int` |
| `start_row` | `int` |
| `worksheet_name` | `str \| None` |

| Public member | Signature or access |
| --- | --- |
| `cell_count` | `property (read-only)` |
| `height` | `property (read-only)` |
| `parse` | `(selector: 'str') -> 'A1Rectangle'` |
| `require_unbound_selector` | `(self, selector: 'str') -> 'A1Rectangle'` |
| `width` | `property (read-only)` |

### AbortDisposition

| Member | Wire value |
| --- | --- |
| `ABORTED` | `aborted` |
| `ALREADY_ABORTED` | `already_aborted` |
| `ALREADY_COMMITTED` | `already_committed` |
| `EXPIRED` | `expired` |

### AggregateFunction

| Member | Wire value |
| --- | --- |
| `COUNT` | `count` |
| `MIN` | `min` |
| `MAX` | `max` |
| `SUM` | `sum` |
| `AVG` | `avg` |
| `FIRST` | `first` |
| `LAST` | `last` |

### AggregateMeasure

| Field | Declared type |
| --- | --- |
| `function` | `AggregateFunction` |
| `output_field` | `str` |
| `value_field` | `str \| None` |

| Public member | Signature or access |
| --- | --- |
| `to_wire` | `(self) -> 'dict[str, object]'` |

### ArtifactAccess

| Public member | Signature or access |
| --- | --- |
| `export` | `(self, request)` |
| `view` | `(self, request)` |
| `watch` | `(self, request)` |

### BaseModeDestination

| Field | Declared type |
| --- | --- |
| `container` | `TableURI \| str` |
| `table_name` | `str` |

| Public member | Signature or access |
| --- | --- |
| `from_wire` | `(payload: 'Mapping[str, Any]') -> 'BaseModeDestination'` |
| `to_wire` | `(self) -> 'dict[str, Any]'` |

### BaseModeTableAddress

| Field | Declared type |
| --- | --- |
| `container` | `TableURI \| str` |
| `table_id` | `str` |

| Public member | Signature or access |
| --- | --- |
| `from_wire` | `(payload: 'Mapping[str, Any]') -> 'BaseModeTableAddress'` |
| `to_wire` | `(self) -> 'dict[str, Any]'` |

### CalculationState

| Member | Wire value |
| --- | --- |
| `PROVIDER_CURRENT` | `provider_current` |
| `CACHED` | `cached` |
| `UNKNOWN` | `unknown` |

### CalculationTrigger

| Member | Wire value |
| --- | --- |
| `EXPLICIT_RECALCULATION` | `explicit_recalculation` |
| `MUTATION` | `mutation` |
| `PROVIDER_READ` | `provider_read` |
| `STORED_CACHE` | `stored_cache` |

### CalendarBucket

| Field | Declared type |
| --- | --- |
| `count` | `int` |
| `offset_ns` | `int` |
| `origin` | `str` |
| `timezone` | `str` |
| `unit` | `CalendarUnit` |
| `week_start` | `int` |

| Public member | Signature or access |
| --- | --- |
| `to_wire` | `(self) -> 'dict[str, object]'` |

### CapabilitySet

| Field | Declared type |
| --- | --- |
| `capability_ids` | `tuple[str, ...]` |
| `details` | `Mapping[str, Any]` |
| `modes` | `tuple[TableMode, ...]` |

| Public member | Signature or access |
| --- | --- |
| `supports` | `(self, capability_id: 'str') -> 'bool'` |

### Client

| Public member | Signature or access |
| --- | --- |
| `artifacts` | `(self)` |
| `bind_sheet_range` | `(self, *, grid: 'TableURI \| str', cell_range: 'str', header: 'bool', schema: 'pl.Schema \| None' = None, schema_policy: 'SchemaPolicy' = <SchemaPolicy.VALIDATE_DECLARED: 'validate_declared'>) -> 'OperationResult[SheetRangeSource]'` |
| `close` | `(self) -> 'None'` |
| `collect` | `(self, source: 'object') -> 'OperationResult[pl.DataFrame]'` |
| `copy_workbook` | `(self, source: 'str \| TableURI', *, to: 'str \| TableURI \| None' = None, title: 'str \| None' = None, limits: 'Any' = None)` |
| `formulas` | `(self, target)` |
| `from_config` | `(config: 'ClientConfig \| str \| Path', *, descriptors: 'Iterable[PluginDescriptor] \| None' = None, resolver: 'CredentialResolver \| None' = None, environ: 'dict[str, str] \| None' = None, transports: 'dict[str, Any] \| None' = None) -> 'Client'` |
| `materialize` | `(self, source: 'object', *, to: 'str \| TableDestination', profile: 'str \| None' = None, idempotency_key: 'str \| None' = None)` |
| `native_sql` | `(self, target: 'str \| TableURI') -> 'NativeSql'` |
| `open` | `(self, target: 'str \| TableURI \| ExistingTableAddress', *, schema: 'pl.Schema \| None' = None, metadata_only: 'bool' = False)` |
| `reconcile_materialization` | `(self, reference: 'ReconciliationReference', *, destination: 'BaseModeDestination')` |
| `sql` | `(self, statement: 'str', *, sources: 'dict[str, object]', parameters: 'dict[str, Any] \| None' = None, limits: 'SqlResourceLimits \| None' = None) -> 'OperationResult[pl.DataFrame]'` |
| `workbook` | `property (read-only)` |

### ClientConfig

| Field | Declared type |
| --- | --- |
| `credentials` | `Mapping[str, Mapping[str, CredentialBinding]]` |
| `providers` | `Mapping[str, ProviderConfig]` |

| Public member | Signature or access |
| --- | --- |
| `empty` | `() -> 'ClientConfig'` |

### CommitState

| Member | Wire value |
| --- | --- |
| `NOT_APPLICABLE` | `not_applicable` |
| `NOT_STARTED` | `not_started` |
| `NOT_COMMITTED` | `not_committed` |
| `COMMITTED` | `committed` |
| `PARTIAL` | `partial` |
| `UNKNOWN` | `unknown` |

### ConfiguredPlugin

| Field | Declared type |
| --- | --- |
| `config` | `ProviderConfig` |
| `descriptor` | `PluginDescriptor` |

### ConnectorRegistry

| Public member | Signature or access |
| --- | --- |
| `close` | `(self) -> 'None'` |
| `connector_for` | `(self, target: 'str \| object') -> 'TableConnector'` |
| `descriptor_for` | `(self, target: 'str \| object') -> 'PluginDescriptor'` |
| `from_descriptors` | `(descriptors: 'Iterable[PluginDescriptor]', config: 'ClientConfig', *, resolver: 'CredentialResolver \| None' = None, environ: 'Mapping[str, str] \| None' = None, transports: 'Mapping[str, Any] \| None' = None) -> 'ConnectorRegistry'` |
| `list` | `(self) -> 'tuple[PluginDescriptor, ...]'` |
| `register` | `(self, connector: 'TableConnector') -> 'None'` |

### CredentialBinding

| Field | Declared type |
| --- | --- |
| `env` | `str` |

### CredentialLease

| Public member | Signature or access |
| --- | --- |
| `dispose` | `(self) -> 'None'` |
| `values` | `property (read-only)` |

### CredentialResolver

| Public member | Signature or access |
| --- | --- |
| `resolve` | `(self, provider: 'ProviderConfig') -> 'CredentialLease'` |

### DatabaseTableAddress

| Field | Declared type |
| --- | --- |
| `database` | `TableURI \| str` |
| `name` | `QualifiedTableName` |

| Public member | Signature or access |
| --- | --- |
| `from_wire` | `(payload: 'Mapping[str, Any]') -> 'DatabaseTableAddress'` |
| `to_wire` | `(self) -> 'dict[str, Any]'` |

### DirectDestination

| Field | Declared type |
| --- | --- |
| `uri` | `TableURI \| str` |

| Public member | Signature or access |
| --- | --- |
| `from_wire` | `(payload: 'Mapping[str, Any]') -> 'DirectDestination'` |
| `to_wire` | `(self) -> 'dict[str, Any]'` |

### DirectTableAddress

| Field | Declared type |
| --- | --- |
| `uri` | `TableURI \| str` |

| Public member | Signature or access |
| --- | --- |
| `from_wire` | `(payload: 'Mapping[str, Any]') -> 'DirectTableAddress'` |
| `to_wire` | `(self) -> 'dict[str, Any]'` |

### EnvironmentCredentialResolver

| Public member | Signature or access |
| --- | --- |
| `resolve` | `(self, provider: 'ProviderConfig') -> 'CredentialLease'` |

### ErrorCode

| Member | Wire value |
| --- | --- |
| `INVALID_TARGET` | `invalid_target` |
| `INVALID_FORMULA` | `invalid_formula` |
| `INVALID_SCHEMA` | `invalid_schema` |
| `INVALID_PREDICATE` | `invalid_predicate` |
| `INVALID_SQL` | `invalid_sql` |
| `INVALID_DESCRIPTOR` | `invalid_descriptor` |
| `INVALID_CONFIGURATION` | `invalid_configuration` |
| `UNSUPPORTED_CAPABILITY` | `unsupported_capability` |
| `UNSUPPORTED_MODE` | `unsupported_mode` |
| `AUTHENTICATION` | `authentication` |
| `AUTHORIZATION` | `authorization` |
| `DESTINATION_EXISTS` | `destination_exists` |
| `TARGET_NOT_FOUND` | `target_not_found` |
| `STALE_REVISION` | `stale_revision` |
| `KEY_CONFLICT` | `key_conflict` |
| `DUPLICATE_UPDATE_KEY` | `duplicate_update_key` |
| `MISSING_UPDATE_KEY` | `missing_update_key` |
| `IDEMPOTENCY_CONFLICT` | `idempotency_conflict` |
| `RESOURCE_LIMIT` | `resource_limit` |
| `TIMEOUT` | `timeout` |
| `CANCELLED` | `cancelled` |
| `SNAPSHOT_UNAVAILABLE` | `snapshot_unavailable` |
| `EXECUTION_FAILED` | `execution_failed` |
| `PARTIAL_EFFECT` | `partial_effect` |
| `UNCERTAIN_MUTATION` | `uncertain_mutation` |
| `RECONCILIATION_UNAVAILABLE` | `reconciliation_unavailable` |
| `READBACK_MISMATCH` | `readback_mismatch` |
| `PROTOCOL_FAILURE` | `protocol_failure` |
| `ARTIFACT_INTEGRITY` | `artifact_integrity` |
| `CLIENT_CLOSED` | `client_closed` |
| `CLIENT_AFFINITY_MISMATCH` | `client_affinity_mismatch` |

### ErrorInfo

| Field | Declared type |
| --- | --- |
| `code` | `ErrorCode` |
| `message` | `str` |
| `reconciliation` | `ReconciliationReference \| None` |
| `safe_details` | `Mapping[str, Any]` |

| Public member | Signature or access |
| --- | --- |
| `from_wire` | `(payload: 'Mapping[str, Any]') -> 'ErrorInfo'` |
| `to_wire` | `(self) -> 'dict[str, Any]'` |

### FieldFormulaObservation

| Field | Declared type |
| --- | --- |
| `expression` | `FormulaExpression` |
| `field_id` | `str` |
| `field_name` | `str` |
| `observed_revision` | `str` |
| `result_type` | `str \| None` |
| `table_uri` | `TableURI \| str` |

| Public member | Signature or access |
| --- | --- |
| `from_wire` | `(payload: 'Mapping[str, Any]') -> 'FieldFormulaObservation'` |
| `to_wire` | `(self) -> 'dict[str, object]'` |

### FieldFormulaTarget

| Field | Declared type |
| --- | --- |
| `field` | `FieldRef` |
| `table` | `_TTable` |

### FieldFormulaValueObservation

| Field | Declared type |
| --- | --- |
| `calculation_state` | `CalculationState` |
| `calculation_trigger` | `CalculationTrigger` |
| `dependency_scope` | `str` |
| `field_id` | `str` |
| `field_name` | `str` |
| `observed_revision` | `str` |
| `table_uri` | `TableURI \| str` |
| `values` | `tuple[FormulaRecordValue, ...]` |

| Public member | Signature or access |
| --- | --- |
| `from_wire` | `(payload: 'Mapping[str, Any]') -> 'FieldFormulaValueObservation'` |
| `to_wire` | `(self) -> 'dict[str, object]'` |

### FieldFormulaView

| Public member | Signature or access |
| --- | --- |
| `read` | `(self) -> 'OperationResult[FieldFormulaObservation]'` |
| `read_values` | `(self, *, limits: 'FormulaResourceLimits \| None' = None) -> 'OperationResult[FieldFormulaValueObservation]'` |
| `recalculate` | `(self, *, scope: 'FieldRecalculationScope', expected_revision: 'str \| None' = None, idempotency_key: 'str \| None' = None) -> 'OperationResult[RecalculationObservation]'` |
| `set` | `(self, expression: 'FormulaExpression', *, expected_revision: 'str \| None' = None, idempotency_key: 'str \| None' = None) -> 'OperationResult[FormulaMutation]'` |

### FieldRecalculationScope

| Member | Wire value |
| --- | --- |
| `FIELD` | `field` |
| `TABLE` | `table` |

### FieldRef

| Field | Declared type |
| --- | --- |
| `field_id` | `str \| None` |
| `name` | `str \| None` |

### FillMode

| Member | Wire value |
| --- | --- |
| `NULL` | `null` |
| `CONSTANT` | `constant` |
| `LOCF` | `locf` |
| `LINEAR` | `linear` |

### FillRule

| Field | Declared type |
| --- | --- |
| `field` | `str` |
| `mode` | `FillMode` |
| `value` | `JsonScalar` |

| Public member | Signature or access |
| --- | --- |
| `to_wire` | `(self) -> 'dict[str, object]'` |

### FixedBucket

| Field | Declared type |
| --- | --- |
| `offset_ns` | `int` |
| `origin` | `str` |
| `width_ns` | `int` |

| Public member | Signature or access |
| --- | --- |
| `to_wire` | `(self) -> 'dict[str, object]'` |

### FormulaCapabilityDetails

| Field | Declared type |
| --- | --- |
| `calculation_states` | `tuple[CalculationState, ...]` |
| `dialects` | `tuple[str, ...]` |
| `idempotency_strength` | `IdempotencyStrength` |
| `max_cells_per_operation` | `int \| None` |
| `max_expression_bytes` | `int` |
| `mutation_atomicity` | `MutationAtomicity` |
| `recalculation_scopes` | `tuple[str, ...]` |
| `revision_enforcement` | `RevisionEnforcement` |
| `target_kind` | `str` |

| Public member | Signature or access |
| --- | --- |
| `from_wire` | `(payload: 'Mapping[str, Any]') -> 'FormulaCapabilityDetails'` |
| `to_wire` | `(self) -> 'dict[str, object]'` |

### FormulaCapabilitySet

| Field | Declared type |
| --- | --- |
| `capabilities` | `tuple[CapabilityIdentity, ...]` |
| `details` | `FormulaCapabilityDetails` |

| Public member | Signature or access |
| --- | --- |
| `from_wire` | `(payload: 'Mapping[str, Any]') -> 'FormulaCapabilitySet'` |
| `to_wire` | `(self) -> 'dict[str, object]'` |

### FormulaCell

| Field | Declared type |
| --- | --- |
| `address` | `str` |
| `expression` | `FormulaExpression` |

| Public member | Signature or access |
| --- | --- |
| `from_wire` | `(payload: 'Mapping[str, Any]') -> 'FormulaCell'` |
| `to_wire` | `(self) -> 'dict[str, object]'` |

### FormulaError

### FormulaErrorValue

| Field | Declared type |
| --- | --- |
| `code` | `str` |

| Public member | Signature or access |
| --- | --- |
| `from_wire` | `(payload: 'Mapping[str, Any]') -> 'FormulaErrorValue'` |
| `to_wire` | `(self) -> 'dict[str, str]'` |

### FormulaExpression

| Field | Declared type |
| --- | --- |
| `dialect` | `str` |
| `text` | `str` |

| Public member | Signature or access |
| --- | --- |
| `byte_count` | `property (read-only)` |
| `from_wire` | `(payload: 'Mapping[str, Any]') -> 'FormulaExpression'` |
| `sha256` | `property (read-only)` |
| `to_wire` | `(self) -> 'dict[str, str]'` |

### FormulaMutation

| Field | Declared type |
| --- | --- |
| `affected_count` | `int` |
| `formula_observation` | `GridFormulaObservation \| FieldFormulaObservation` |
| `revision_after` | `str` |
| `revision_before` | `str \| None` |
| `target_kind` | `str` |

| Public member | Signature or access |
| --- | --- |
| `from_wire` | `(payload: 'Mapping[str, Any]') -> 'FormulaMutation'` |
| `to_wire` | `(self) -> 'dict[str, object]'` |

### FormulaRecordValue

| Field | Declared type |
| --- | --- |
| `record_id` | `str` |
| `value` | `FormulaValue` |

| Public member | Signature or access |
| --- | --- |
| `from_wire` | `(payload: 'Mapping[str, Any]') -> 'FormulaRecordValue'` |
| `to_wire` | `(self) -> 'dict[str, object]'` |

### FormulaResourceLimits

| Field | Declared type |
| --- | --- |
| `max_cells` | `int \| None` |
| `max_expression_bytes` | `int \| None` |
| `max_records` | `int \| None` |
| `max_response_bytes` | `int \| None` |
| `timeout_seconds` | `float \| None` |

### FormulaValue

| Field | Declared type |
| --- | --- |
| `kind` | `str` |
| `logical_type` | `str \| None` |
| `value` | `object` |

| Public member | Signature or access |
| --- | --- |
| `from_python` | `(value: 'object') -> 'FormulaValue'` |
| `from_wire` | `(payload: 'Mapping[str, Any]') -> 'FormulaValue'` |
| `logical` | `(logical_type: 'str', value: 'str \| int \| float') -> 'FormulaValue'` |
| `provider_error` | `(value: 'FormulaErrorValue') -> 'FormulaValue'` |
| `to_python` | `(self) -> 'object'` |
| `to_wire` | `(self) -> 'dict[str, object]'` |

### FormulaValueCell

| Field | Declared type |
| --- | --- |
| `address` | `str` |
| `value` | `FormulaValue` |

| Public member | Signature or access |
| --- | --- |
| `from_wire` | `(payload: 'Mapping[str, Any]') -> 'FormulaValueCell'` |
| `to_wire` | `(self) -> 'dict[str, object]'` |

### GridFormulaObservation

| Field | Declared type |
| --- | --- |
| `formulas` | `tuple[FormulaCell, ...]` |
| `observed_revision` | `str` |
| `requested_range` | `str` |
| `worksheet_id` | `str` |

| Public member | Signature or access |
| --- | --- |
| `from_wire` | `(payload: 'Mapping[str, Any]') -> 'GridFormulaObservation'` |
| `to_wire` | `(self) -> 'dict[str, object]'` |

### GridFormulaTarget

| Field | Declared type |
| --- | --- |
| `grid` | `TableURI \| str` |
| `worksheet` | `WorksheetRef` |

### GridFormulaValueObservation

| Field | Declared type |
| --- | --- |
| `calculation_state` | `CalculationState` |
| `calculation_trigger` | `CalculationTrigger` |
| `dependency_scope` | `str` |
| `observed_revision` | `str` |
| `requested_range` | `str` |
| `values` | `tuple[FormulaValueCell, ...]` |
| `worksheet_id` | `str` |

| Public member | Signature or access |
| --- | --- |
| `from_wire` | `(payload: 'Mapping[str, Any]') -> 'GridFormulaValueObservation'` |
| `to_wire` | `(self) -> 'dict[str, object]'` |

### GridFormulaView

| Public member | Signature or access |
| --- | --- |
| `read` | `(self, cell_range: 'str', *, limits: 'FormulaResourceLimits \| None' = None) -> 'OperationResult[GridFormulaObservation]'` |
| `read_values` | `(self, cell_range: 'str', *, limits: 'FormulaResourceLimits \| None' = None) -> 'OperationResult[GridFormulaValueObservation]'` |
| `recalculate` | `(self, *, scope: 'GridRecalculationScope', cell_range: 'str \| None' = None, expected_revision: 'str \| None' = None, idempotency_key: 'str \| None' = None, limits: 'FormulaResourceLimits \| None' = None) -> 'OperationResult[RecalculationObservation]'` |
| `set` | `(self, cell_range: 'str', expression: 'FormulaExpression \| str', *, dialect: 'str \| None' = None, expected_revision: 'str \| None' = None, idempotency_key: 'str \| None' = None, limits: 'FormulaResourceLimits \| None' = None) -> 'OperationResult[FormulaMutation]'` |

### GridRecalculationScope

| Member | Wire value |
| --- | --- |
| `RANGE` | `range` |
| `WORKSHEET` | `worksheet` |
| `WORKBOOK` | `workbook` |

### IdempotencyStrength

| Member | Wire value |
| --- | --- |
| `PROVIDER` | `provider` |
| `HOST_LEDGER` | `host_ledger` |
| `RECONCILED` | `reconciled` |

### LegacyConnectorAdapterBridge

| Public member | Signature or access |
| --- | --- |
| `begin_transaction` | `(self, binding: 'TableBinding') -> 'object'` |
| `bind_sheet_range` | `(self, source: 'SheetRangeSource') -> 'OperationResult[SheetRangeSource]'` |
| `capabilities_for` | `(self, binding: 'TableBinding') -> 'OperationResult[CapabilitySet]'` |
| `close` | `(self) -> 'None'` |
| `create_table` | `(self, source: 'object \| MaterializationRequest', destination: 'TableDestination \| None' = None) -> 'OperationResult[TableBinding]'` |
| `delete_rows` | `(self, binding: 'TableBinding', *, where, parameters: 'Mapping[str, Any] \| None' = None) -> 'OperationResult[int]'` |
| `drop_table` | `(self, binding: 'TableBinding') -> 'OperationResult[None]'` |
| `formula_extension_for` | `(self) -> 'FormulaConnectorExtension'` |
| `insert_rows` | `(self, binding: 'TableBinding', frame: 'pl.DataFrame') -> 'OperationResult[int]'` |
| `inspect_table` | `(self, binding: 'TableBinding') -> 'OperationResult[TableInspection]'` |
| `open_table` | `(self, address: 'object') -> 'OperationResult[TableBinding]'` |
| `read_sheet_range` | `(self, source: 'SheetRangeSource') -> 'OperationResult[ArrowTableCarrier]'` |
| `read_table` | `(self, binding: 'TableBinding', *, limit: 'int \| None' = None, continuation: 'str \| None' = None) -> 'OperationResult[ArrowTableCarrier]'` |
| `spreadsheet_provider` | `(self)` |
| `update_rows` | `(self, binding: 'TableBinding', frame: 'pl.DataFrame', *, keys: 'tuple[str, ...]') -> 'OperationResult[int]'` |

### ManagedSnapshot

| Field | Declared type |
| --- | --- |
| `committed_at` | `str` |
| `descriptor_hash` | `str` |
| `logical_target` | `TableURI` |
| `retention_expires_at` | `str \| None` |
| `snapshot_id` | `str` |
| `snapshot_reference` | `str` |
| `stage_id` | `str` |

### ManagedSnapshotState

| Field | Declared type |
| --- | --- |
| `schema` | `pa.Schema` |
| `snapshot` | `ManagedSnapshot` |

### ManagedStage

| Field | Declared type |
| --- | --- |
| `artifact_hash` | `str` |
| `descriptor_hash` | `str` |
| `idempotency_key` | `str` |
| `lease_expires_at` | `str \| None` |
| `logical_target` | `TableURI` |
| `physical_target` | `TableURI` |
| `stage_id` | `str` |
| `staged_at` | `str` |

### MaterializationRequest

| Field | Declared type |
| --- | --- |
| `destination` | `TableDestination` |
| `idempotency_key` | `str` |
| `profile` | `str` |
| `source` | `pl.DataFrame` |

| Public member | Signature or access |
| --- | --- |
| `content_fingerprint` | `property (read-only)` |
| `row_count` | `property (read-only)` |
| `schema_fingerprint` | `property (read-only)` |

### MutationAtomicity

| Member | Wire value |
| --- | --- |
| `ATOMIC` | `atomic` |
| `PARTIAL_REPORTED` | `partial_reported` |
| `UNKNOWN` | `unknown` |

### NativeSql

| Public member | Signature or access |
| --- | --- |
| `execute` | `(self, statement: 'str', *, parameters: 'Sequence[Any] \| None' = None, limits: 'NativeSqlResourceLimits \| None' = None, idempotency_key: 'str') -> 'OperationResult[int]'` |
| `query` | `(self, statement: 'str', *, parameters: 'Sequence[Any] \| None' = None, limits: 'NativeSqlResourceLimits \| None' = None) -> 'OperationResult[pl.DataFrame]'` |

### NativeSqlResourceLimits

| Field | Declared type |
| --- | --- |
| `max_bytes` | `int` |
| `max_duration_ms` | `int` |
| `max_rows` | `int` |

| Public member | Signature or access |
| --- | --- |
| `to_wire` | `(self) -> 'dict[str, int]'` |

### OTCError

### OperationCatalog

| Public member | Signature or access |
| --- | --- |
| `default` | `() -> 'OperationCatalog'` |
| `describe` | `(self, namespace: 'str \| None' = None, operation_id: 'str \| None' = None, version: 'str \| None' = None) -> 'tuple[OperationDescriptor, ...]'` |
| `get` | `(self, namespace: 'str', operation_id: 'str', version: 'str') -> 'OperationDescriptor \| None'` |
| `register` | `(self, descriptor: 'OperationDescriptor') -> 'None'` |

### OperationResult

| Field | Declared type |
| --- | --- |
| `commit` | `CommitState` |
| `continuation` | `str \| None` |
| `error` | `ErrorInfo \| None` |
| `outcome` | `Outcome` |
| `receipts` | `tuple[Receipt, ...]` |
| `value` | `T \| None` |
| `verification` | `VerificationState` |
| `warnings` | `tuple[OperationWarning, ...]` |

| Public member | Signature or access |
| --- | --- |
| `from_wire` | `(payload: 'Mapping[str, Any]', *, value_decoder: 'Callable[[Any], T] \| None' = None) -> 'OperationResult[T]'` |
| `require_value` | `(self) -> 'T'` |
| `to_wire` | `(self, value_encoder: 'Callable[[T], Any] \| None' = None) -> 'dict[str, Any]'` |
| `with_results` | `(self) -> 'OperationResult[T]'` |

### OperationWarning

| Field | Declared type |
| --- | --- |
| `code` | `str` |
| `message` | `str` |
| `safe_details` | `Mapping[str, Any]` |

| Public member | Signature or access |
| --- | --- |
| `from_wire` | `(payload: 'Mapping[str, Any]') -> 'OperationWarning'` |
| `to_wire` | `(self) -> 'dict[str, Any]'` |

### Outcome

| Member | Wire value |
| --- | --- |
| `SUCCEEDED` | `succeeded` |
| `PLANNED` | `planned` |
| `REJECTED` | `rejected` |
| `FAILED` | `failed` |
| `PARTIAL` | `partial` |
| `UNKNOWN` | `unknown` |

### PolarsPlanMapper

| Public member | Signature or access |
| --- | --- |
| `execute` | `(self, query: 'Query', frames: 'dict[str, pl.DataFrame]') -> 'pl.DataFrame'` |

### PortablePredicate

| Field | Declared type |
| --- | --- |
| `expression` | `str \| None` |
| `kind` | `PredicateKind` |
| `parameters` | `Mapping[str, Any]` |

| Public member | Signature or access |
| --- | --- |
| `from_wire` | `(payload: 'Mapping[str, Any]') -> 'PortablePredicate'` |
| `to_wire` | `(self) -> 'dict[str, Any]'` |

### PredicateKind

| Member | Wire value |
| --- | --- |
| `SQL` | `sql` |
| `ALL_ROWS` | `all_rows` |

### QualifiedTableName

| Field | Declared type |
| --- | --- |
| `catalog` | `str \| None` |
| `schema` | `str \| None` |
| `table` | `str` |

| Public member | Signature or access |
| --- | --- |
| `from_wire` | `(payload: 'Mapping[str, Any]') -> 'QualifiedTableName'` |
| `to_wire` | `(self) -> 'dict[str, str \| None]'` |

### Query

| Field | Declared type |
| --- | --- |
| `lane` | `QueryLane` |
| `limits` | `object` |
| `parameters` | `Mapping[str, Any]` |
| `sources` | `Mapping[str, object]` |
| `statement` | `str` |

| Public member | Signature or access |
| --- | --- |
| `definition_hash` | `property (read-only)` |
| `plan_hash` | `property (read-only)` |

### QueryLane

| Member | Wire value |
| --- | --- |
| `RELATIONAL` | `relational` |
| `TEMPORAL` | `temporal` |

### RecalculationObservation

| Field | Declared type |
| --- | --- |
| `calculation_state` | `CalculationState` |
| `effective_scope` | `str` |
| `provider_status` | `str` |
| `requested_scope` | `str` |
| `revision_after` | `str \| None` |
| `revision_before` | `str \| None` |
| `target_kind` | `str` |
| `value_observation` | `GridFormulaValueObservation \| FieldFormulaValueObservation \| None` |
| `verification` | `str` |

| Public member | Signature or access |
| --- | --- |
| `from_wire` | `(payload: 'Mapping[str, Any]') -> 'RecalculationObservation'` |
| `to_wire` | `(self) -> 'dict[str, object]'` |

### Receipt

| Field | Declared type |
| --- | --- |
| `capability` | `str \| None` |
| `connector_id` | `str \| None` |
| `details` | `Mapping[str, Any]` |
| `kind` | `str` |
| `mode` | `TableMode \| None` |
| `operation` | `str` |
| `safe_target` | `TableURI \| None` |

| Public member | Signature or access |
| --- | --- |
| `from_wire` | `(payload: 'Mapping[str, Any]') -> 'Receipt'` |
| `to_wire` | `(self) -> 'dict[str, Any]'` |

### ReconciliationReference

| Field | Declared type |
| --- | --- |
| `connector_id` | `str \| None` |
| `expires_at` | `str \| None` |
| `idempotency_key` | `str \| None` |
| `operation_id` | `str` |

| Public member | Signature or access |
| --- | --- |
| `from_wire` | `(payload: 'Mapping[str, Any]') -> 'ReconciliationReference'` |
| `to_wire` | `(self) -> 'dict[str, str \| None]'` |

### RevisionEnforcement

| Member | Wire value |
| --- | --- |
| `ATOMIC` | `atomic` |
| `CHECKED` | `checked` |
| `UNAVAILABLE` | `unavailable` |

### SchemaPolicy

| Member | Wire value |
| --- | --- |
| `VALIDATE_DECLARED` | `validate_declared` |
| `INFER_COMPLETE` | `infer_complete` |

### SheetModeDestination

| Field | Declared type |
| --- | --- |
| `anchor` | `str` |
| `grid` | `TableURI \| str` |
| `header` | `bool` |
| `worksheet` | `str \| None` |

| Public member | Signature or access |
| --- | --- |
| `from_wire` | `(payload: 'Mapping[str, Any]') -> 'SheetModeDestination'` |
| `to_wire` | `(self) -> 'dict[str, Any]'` |

### SheetModeTableAddress

| Field | Declared type |
| --- | --- |
| `grid` | `TableURI \| str` |
| `table_id` | `str` |

| Public member | Signature or access |
| --- | --- |
| `from_wire` | `(payload: 'Mapping[str, Any]') -> 'SheetModeTableAddress'` |
| `to_wire` | `(self) -> 'dict[str, Any]'` |

### SheetRangeSource

| Field | Declared type |
| --- | --- |
| `cell_range` | `str` |
| `grid` | `TableURI \| str` |
| `header` | `bool` |
| `observed_revision` | `str \| None` |
| `schema` | `pl.Schema \| None` |
| `schema_policy` | `SchemaPolicy` |

| Public member | Signature or access |
| --- | --- |
| `from_wire` | `(payload: 'Mapping[str, Any]') -> 'SheetRangeSource'` |
| `to_wire` | `(self) -> 'dict[str, Any]'` |

### SqlResourceLimits

| Field | Declared type |
| --- | --- |
| `max_duration_ms` | `int` |
| `max_intermediate_bytes` | `int` |
| `max_intermediate_rows` | `int` |
| `max_output_bytes` | `int` |
| `max_output_rows` | `int` |
| `max_source_bytes` | `int` |
| `max_source_rows` | `int` |
| `max_total_input_bytes` | `int` |
| `max_total_input_rows` | `int` |

| Public member | Signature or access |
| --- | --- |
| `to_wire` | `(self) -> 'dict[str, int]'` |

### Table

| Public member | Signature or access |
| --- | --- |
| `address` | `property (read-only)` |
| `capabilities` | `(self)` |
| `connector_id` | `property (read-only)` |
| `delete` | `(self, *, where, parameters: 'Mapping[str, Any] \| None' = None)` |
| `drop` | `(self)` |
| `insert` | `(self, frame: 'pl.DataFrame')` |
| `inspect` | `(self)` |
| `layout` | `(self)` |
| `mode` | `property (read-only)` |
| `observed_revision` | `property (read-only)` |
| `read` | `(self)` |
| `read_page` | `(self, *, limit: 'int', continuation: 'str \| None' = None)` |
| `schema` | `property (read-only)` |
| `time_series` | `(self, descriptor: 'TemporalTableDescriptor')` |
| `transaction` | `(self, *, idempotency_key: 'str \| None' = None) -> 'TableTransaction'` |
| `update` | `(self, frame: 'pl.DataFrame', *, keys: 'tuple[str, ...]')` |
| `uri` | `property (read-only)` |

### TableBinding

| Field | Declared type |
| --- | --- |
| `address` | `ExistingTableAddress \| None` |
| `connector_id` | `str` |
| `content_fingerprint` | `str \| None` |
| `layout_binding` | `Mapping[str, Any] \| None` |
| `mode` | `TableMode` |
| `observed_revision` | `str \| None` |
| `profile` | `str \| None` |
| `row_count` | `int \| None` |
| `schema` | `pl.Schema \| None` |
| `schema_fingerprint` | `str \| None` |
| `schema_observed` | `bool` |
| `uri` | `TableURI` |

### TableConnector

| Field | Declared type |
| --- | --- |
| `capabilities` | `tuple[object, ...]` |
| `handles_paths` | `bool` |
| `hosts` | `tuple[str, ...]` |
| `identity` | `object` |
| `local` | `bool` |
| `materialization` | `tuple[MaterializationCapability, ...]` |
| `modes` | `tuple[TableMode, ...]` |
| `schemes` | `tuple[str, ...]` |

| Public member | Signature or access |
| --- | --- |
| `begin_transaction` | `(self, binding: 'TableBinding') -> 'object'` |
| `capabilities_for` | `(self, binding: 'TableBinding') -> 'OperationResult[CapabilitySet]'` |
| `close` | `(self) -> 'None'` |
| `create_table` | `(self, source: 'object \| MaterializationRequest', destination: 'TableDestination \| None' = None) -> 'OperationResult[TableBinding]'` |
| `delete_rows` | `(self, binding: 'TableBinding', *, where, parameters: 'Mapping[str, Any] \| None' = None) -> 'OperationResult[int]'` |
| `drop_table` | `(self, binding: 'TableBinding') -> 'OperationResult[None]'` |
| `insert_rows` | `(self, binding: 'TableBinding', frame: 'pl.DataFrame') -> 'OperationResult[int]'` |
| `inspect_table` | `(self, binding: 'TableBinding') -> 'OperationResult[TableInspection]'` |
| `open_table` | `(self, address: 'object') -> 'OperationResult[TableBinding]'` |
| `read_table` | `(self, binding: 'TableBinding', *, limit: 'int \| None' = None, continuation: 'str \| None' = None) -> 'OperationResult[ArrowTableCarrier]'` |
| `update_rows` | `(self, binding: 'TableBinding', frame: 'pl.DataFrame', *, keys: 'tuple[str, ...]') -> 'OperationResult[int]'` |

### TableInspection

| Field | Declared type |
| --- | --- |
| `facts` | `Mapping[str, Any]` |
| `mode` | `TableMode` |
| `observed_revision` | `str \| None` |
| `row_count` | `int \| None` |
| `schema` | `pl.Schema` |
| `uri` | `TableURI` |

### TableLayoutSession

| Public member | Signature or access |
| --- | --- |
| `capabilities` | `property (read-only)` |
| `close` | `(self)` |
| `config` | `(self, **kwargs)` |
| `range` | `(self, address: 'str')` |
| `read_config` | `(self, *, rows: 'Sequence[int]', columns: 'Sequence[str]', view_fields=None)` |
| `verify` | `(self, expected=None)` |
| `worksheet` | `property (read-only)` |
| `write` | `(self, **kwargs)` |

### TableMode

| Member | Wire value |
| --- | --- |
| `BASE_MODE` | `base-mode` |
| `SHEET_MODE` | `sheet-mode` |

### TableTransaction

| Public member | Signature or access |
| --- | --- |
| `abort` | `(self)` |
| `commit` | `(self)` |
| `delete` | `(self, *, where, parameters: 'Mapping[str, Any] \| None' = None)` |
| `insert` | `(self, frame: 'pl.DataFrame')` |
| `update` | `(self, frame: 'pl.DataFrame', *, keys: 'tuple[str, ...]')` |

### TemporalConnectorExtension

| Public member | Signature or access |
| --- | --- |
| `abort_stage` | `(self, binding: 'TableBinding', descriptor: 'TemporalTableDescriptor', stage: 'ManagedStage') -> 'ManagedAbortReceipt'` |
| `append_rows` | `(self, binding: 'TableBinding', descriptor: 'TemporalTableDescriptor', frame: 'pl.DataFrame', *, idempotency_key: 'str') -> 'OperationResult[int]'` |
| `commit_stage` | `(self, binding: 'TableBinding', descriptor: 'TemporalTableDescriptor', stage: 'ManagedStage') -> 'ManagedCommitReceipt'` |
| `current_snapshot` | `(self, binding: 'TableBinding', descriptor: 'TemporalTableDescriptor') -> 'ManagedCurrentResult \| None'` |
| `descriptor_hash_for` | `(self, binding: 'TableBinding', descriptor: 'TemporalTableDescriptor') -> 'str'` |
| `executor_for` | `(self, binding: 'TableBinding', descriptor: 'TemporalTableDescriptor') -> 'object'` |
| `readback_snapshot` | `(self, binding: 'TableBinding', descriptor: 'TemporalTableDescriptor', snapshot: 'ManagedSnapshot') -> 'ManagedReadbackResult'` |
| `stage_rows` | `(self, binding: 'TableBinding', descriptor: 'TemporalTableDescriptor', frame: 'pl.DataFrame', *, idempotency_key: 'str') -> 'ManagedStageReceipt'` |
| `upsert_rows` | `(self, binding: 'TableBinding', descriptor: 'TemporalTableDescriptor', frame: 'pl.DataFrame', *, idempotency_key: 'str') -> 'OperationResult[int]'` |

### TemporalResourceLimits

| Field | Declared type |
| --- | --- |
| `max_bytes` | `int` |
| `max_duration_ms` | `int` |
| `max_rows` | `int` |

| Public member | Signature or access |
| --- | --- |
| `to_bounds` | `(self) -> 'ResourceBounds'` |

### TemporalTableDescriptor

| Field | Declared type |
| --- | --- |
| `duplicate_policy` | `DuplicatePolicy` |
| `ingestion_time_field` | `str \| None` |
| `ordering` | `TemporalOrdering` |
| `precision` | `TimestampPrecision` |
| `series_key_fields` | `tuple[str, ...]` |
| `tag_fields` | `tuple[str, ...]` |
| `time_field` | `str` |
| `timezone` | `str` |
| `value_fields` | `tuple[str, ...]` |

| Public member | Signature or access |
| --- | --- |
| `declared_fields` | `property (read-only)` |
| `to_wire` | `(self) -> 'dict[str, object]'` |

### TimeSeriesView

| Public member | Signature or access |
| --- | --- |
| `aggregate` | `(self, start: 'str', end: 'str', *, bucket: 'FixedBucket \| CalendarBucket', group_by: 'tuple[str, ...]' = (), measures: 'tuple[AggregateMeasure, ...]', tag_predicates: 'tuple[TagPredicate, ...]' = (), snapshot_reference: 'str \| None' = None, limits: 'TemporalResourceLimits \| None' = None) -> 'Query'` |
| `append` | `(self, frame: 'pl.DataFrame', *, idempotency_key: 'str') -> 'OperationResult[int]'` |
| `as_of` | `(self, at: 'str', *, columns: 'tuple[str, ...] \| None' = None, tag_predicates: 'tuple[TagPredicate, ...]' = (), snapshot_reference: 'str \| None' = None, limits: 'TemporalResourceLimits \| None' = None) -> 'Query'` |
| `gap_fill` | `(self, start: 'str', end: 'str', *, bucket: 'FixedBucket \| CalendarBucket', group_by: 'tuple[str, ...]' = (), measures: 'tuple[AggregateMeasure, ...]', fills: 'tuple[FillRule, ...]', tag_predicates: 'tuple[TagPredicate, ...]' = (), snapshot_reference: 'str \| None' = None, limits: 'TemporalResourceLimits \| None' = None) -> 'Query'` |
| `latest` | `(self, *, at_or_before: 'str \| None' = None, columns: 'tuple[str, ...] \| None' = None, tag_predicates: 'tuple[TagPredicate, ...]' = (), snapshot_reference: 'str \| None' = None, limits: 'TemporalResourceLimits \| None' = None) -> 'Query'` |
| `scan_range` | `(self, start: 'str', end: 'str', *, columns: 'tuple[str, ...] \| None' = None, tag_predicates: 'tuple[TagPredicate, ...]' = (), snapshot_reference: 'str \| None' = None, limits: 'TemporalResourceLimits \| None' = None) -> 'Query'` |
| `sql` | `(self, statement: 'str', *, parameters: 'Mapping[str \| int, Any]', snapshot_reference: 'str \| None' = None, limits: 'TemporalResourceLimits \| None' = None) -> 'Query'` |
| `upsert` | `(self, frame: 'pl.DataFrame', *, idempotency_key: 'str') -> 'OperationResult[int]'` |

### VerificationState

| Member | Wire value |
| --- | --- |
| `NOT_APPLICABLE` | `not_applicable` |
| `PASSED` | `passed` |
| `FAILED` | `failed` |
| `SKIPPED` | `skipped` |
| `UNAVAILABLE` | `unavailable` |

### WorkbookAccess

| Public member | Signature or access |
| --- | --- |
| `copy` | `(self, source: 'str \| TableURI', *, to: 'str \| TableURI \| None' = None, title: 'str \| None' = None, limits: 'Any' = None)` |
| `create` | `(self, uri: 'str \| TableURI', *, profile: 'str \| None' = None, limits: 'Any' = None, failure_directory: 'Any' = None)` |
| `open` | `(self, uri: 'str \| TableURI', *, limits: 'Any' = None, profile: 'str' = 'general/1.0')` |

### WorksheetRef

| Field | Declared type |
| --- | --- |
| `name` | `str \| None` |
| `worksheet_id` | `str \| None` |

## open_table_connector.sdk.workbook

| Name | Kind | Definition |
| --- | --- | --- |
| `RemoteWorkbookSession` | class | `(connector: 'Any', uri: 'TableURI', profile: 'str' = 'general/1.0', _client: 'Any' = None) -> None` [source](../../packages/sdk/src/open_table_connector/sdk/workbook.py) |
| `WorkbookAccess` | class | `(client: 'Client') -> 'None'` [source](../../packages/sdk/src/open_table_connector/sdk/workbook.py) |

### RemoteWorkbookSession

| Field | Declared type |
| --- | --- |
| `connector` | `Any` |
| `profile` | `str` |
| `uri` | `TableURI` |

| Public member | Signature or access |
| --- | --- |
| `verify` | `(self) -> 'OperationResult[dict[str, Any]]'` |
| `worksheet` | `property (read-only)` |
| `write` | `(self, **_: 'Any') -> 'OperationResult[dict[str, Any]]'` |

### WorkbookAccess

| Public member | Signature or access |
| --- | --- |
| `copy` | `(self, source: 'str \| TableURI', *, to: 'str \| TableURI \| None' = None, title: 'str \| None' = None, limits: 'Any' = None)` |
| `create` | `(self, uri: 'str \| TableURI', *, profile: 'str \| None' = None, limits: 'Any' = None, failure_directory: 'Any' = None)` |
| `open` | `(self, uri: 'str \| TableURI', *, limits: 'Any' = None, profile: 'str' = 'general/1.0')` |

## open_table_connector.sdk.layout

| Name | Kind | Definition |
| --- | --- | --- |
| `TableLayoutSession` | class | `(table, connector, payload: 'Mapping[str, Any]') -> 'None'` [source](../../packages/sdk/src/open_table_connector/sdk/layout.py) |

### TableLayoutSession

| Public member | Signature or access |
| --- | --- |
| `capabilities` | `property (read-only)` |
| `close` | `(self)` |
| `config` | `(self, **kwargs)` |
| `range` | `(self, address: 'str')` |
| `read_config` | `(self, *, rows: 'Sequence[int]', columns: 'Sequence[str]', view_fields=None)` |
| `verify` | `(self, expected=None)` |
| `worksheet` | `property (read-only)` |
| `write` | `(self, **kwargs)` |

## open_table_connector.sdk.recipes

| Name | Kind | Definition |
| --- | --- | --- |
| `apply_recipe` | function | `(client, target, recipe: 'LayoutRecipe', options: 'ExecutionOptions')` [source](../../packages/sdk/src/open_table_connector/sdk/recipes.py) |
| `export_recipe` | function | `(client, target, selectors: 'Sequence[Mapping[str, object]]', *, allow_incomplete: 'bool' = False)` [source](../../packages/sdk/src/open_table_connector/sdk/recipes.py) |

## open_table_connector.sdk.snapshots

| Name | Kind | Definition |
| --- | --- | --- |
| `capture_workbook_snapshot` | function | `(client, target: 'TargetSelector \| str', directory) -> 'OperationResult[WorkbookSnapshot]'` [source](../../packages/sdk/src/open_table_connector/sdk/snapshots.py) |

## open_table_connector.sdk.discovery

| Name | Kind | Definition |
| --- | --- | --- |
| `OPERATION_CATALOG_GROUP` | constant | `'open_table_connector.operation_catalogs.v1'`  |
| `OPERATION_HANDLER_GROUP` | constant | `'open_table_connector.operation_handlers.v1'`  |
| `OperationCatalog` | class | `(descriptors: 'Iterable[OperationDescriptor]' = ()) -> 'None'` [source](../../packages/sdk/src/open_table_connector/sdk/discovery.py) |
| `discover_operation_descriptors` | function | `(entries: 'Iterable[EntryPoint] \| None' = None) -> 'tuple[OperationDescriptor, ...]'` [source](../../packages/sdk/src/open_table_connector/sdk/discovery.py) |
| `resolve_capabilities` | function | `(client, target: 'TargetSelector \| str', *, catalog: 'OperationCatalog \| None' = None) -> 'OperationResult[CapabilityObservation]'` [source](../../packages/sdk/src/open_table_connector/sdk/discovery.py) |

### OperationCatalog

| Public member | Signature or access |
| --- | --- |
| `default` | `() -> 'OperationCatalog'` |
| `describe` | `(self, namespace: 'str \| None' = None, operation_id: 'str \| None' = None, version: 'str \| None' = None) -> 'tuple[OperationDescriptor, ...]'` |
| `get` | `(self, namespace: 'str', operation_id: 'str', version: 'str') -> 'OperationDescriptor \| None'` |
| `register` | `(self, descriptor: 'OperationDescriptor') -> 'None'` |

## open_table_connector.sdk.operations

| Name | Kind | Definition |
| --- | --- | --- |
| `Handler` | constant | `collections.abc.Callable[[typing.Any, open_table_connector.contract.operations.OperationRequest, open_table_connector.contract.operations.ExecutionOptions], typing.Union[open_table_connector.sdk.result.OperationResult[object], object]]`  |
| `discover_operation_handlers` | function | `() -> 'tuple[tuple[str, str, str, Handler], ...]'` [source](../../packages/sdk/src/open_table_connector/sdk/operations.py) |
| `execute_operation` | function | `(client, request: 'OperationRequest', options: 'ExecutionOptions', *, catalog: 'OperationCatalog \| None' = None) -> 'OperationResult[object]'` [source](../../packages/sdk/src/open_table_connector/sdk/operations.py) |
| `register_operation_handler` | function | `(namespace: 'str', operation_id: 'str', version: 'str', handler: 'Handler') -> 'None'` [source](../../packages/sdk/src/open_table_connector/sdk/operations.py) |

## open_table_connector.otc

| Name | Kind | Definition |
| --- | --- | --- |
| `A1Rectangle` | class | `(worksheet_name: 'str \| None', start_address: 'str', end_address: 'str', start_column: 'int', start_row: 'int', end_column: 'int', end_row: 'int') -> None` [source](../../packages/formulas/src/open_table_connector/formulas/ranges.py) |
| `AbortDisposition` | enum | `(value, names=None, *, module=None, qualname=None, type=None, start=1, boundary=None)` [source](../../packages/sdk/src/open_table_connector/sdk/temporal.py) |
| `AggregateFunction` | enum | `(value, names=None, *, module=None, qualname=None, type=None, start=1, boundary=None)` [source](../../packages/timeseries/src/open_table_connector/timeseries/plan.py) |
| `AggregateMeasure` | class | `(output_field: 'str', function: 'AggregateFunction', value_field: 'str \| None') -> None` [source](../../packages/timeseries/src/open_table_connector/timeseries/plan.py) |
| `ArtifactAccess` | class | `(client)` [source](../../packages/sdk/src/open_table_connector/sdk/artifacts.py) |
| `BaseModeDestination` | class | `(container: 'TableURI \| str', table_name: 'str') -> None` [source](../../packages/sdk/src/open_table_connector/sdk/model.py) |
| `BaseModeTableAddress` | class | `(container: 'TableURI \| str', table_id: 'str') -> None` [source](../../packages/sdk/src/open_table_connector/sdk/model.py) |
| `CalculationState` | enum | `(value, names=None, *, module=None, qualname=None, type=None, start=1, boundary=None)` [source](../../packages/formulas/src/open_table_connector/formulas/observations.py) |
| `CalculationTrigger` | enum | `(value, names=None, *, module=None, qualname=None, type=None, start=1, boundary=None)` [source](../../packages/formulas/src/open_table_connector/formulas/observations.py) |
| `CalendarBucket` | class | `(count: 'int', unit: 'CalendarUnit', timezone: 'str', week_start: 'int', origin: 'str', offset_ns: 'int' = 0) -> None` [source](../../packages/timeseries/src/open_table_connector/timeseries/plan.py) |
| `CapabilitySet` | class | `(capability_ids: 'tuple[str, ...]', modes: 'tuple[TableMode, ...]' = (), details: 'Mapping[str, Any]' = <factory>) -> None` [source](../../packages/sdk/src/open_table_connector/sdk/table.py) |
| `Client` | class | `(*, registry: 'ConnectorRegistry') -> 'None'` [source](../../packages/sdk/src/open_table_connector/sdk/client.py) |
| `ClientConfig` | class | `(providers: 'Mapping[str, ProviderConfig]' = <factory>, credentials: 'Mapping[str, Mapping[str, CredentialBinding]]' = <factory>) -> None` [source](../../packages/sdk/src/open_table_connector/sdk/config.py) |
| `CommitState` | enum | `(value, names=None, *, module=None, qualname=None, type=None, start=1, boundary=None)` [source](../../packages/sdk/src/open_table_connector/sdk/result.py) |
| `ConfiguredPlugin` | class | `(descriptor: 'PluginDescriptor', config: 'ProviderConfig') -> None` [source](../../packages/sdk/src/open_table_connector/sdk/registry.py) |
| `ConnectorRegistry` | class | `(connectors: 'Iterable[TableConnector] \| None' = None, *, resolver: 'CredentialResolver \| None' = None, environ: 'Mapping[str, str] \| None' = None, transports: 'Mapping[str, Any] \| None' = None) -> 'None'` [source](../../packages/sdk/src/open_table_connector/sdk/registry.py) |
| `CredentialBinding` | class | `(env: 'str') -> None` [source](../../packages/sdk/src/open_table_connector/sdk/config.py) |
| `CredentialLease` | class | `(values: 'Mapping[str, str]') -> 'None'` [source](../../packages/sdk/src/open_table_connector/sdk/credentials.py) |
| `CredentialResolver` | class | `(*args, **kwargs)` [source](../../packages/sdk/src/open_table_connector/sdk/credentials.py) |
| `DatabaseTableAddress` | class | `(database: 'TableURI \| str', name: 'QualifiedTableName') -> None` [source](../../packages/sdk/src/open_table_connector/sdk/model.py) |
| `DirectDestination` | class | `(uri: 'TableURI \| str') -> None` [source](../../packages/sdk/src/open_table_connector/sdk/model.py) |
| `DirectTableAddress` | class | `(uri: 'TableURI \| str') -> None` [source](../../packages/sdk/src/open_table_connector/sdk/model.py) |
| `EXCEL_A1` | constant | `'excel-a1'`  |
| `EnvironmentCredentialResolver` | class | `(config: 'ClientConfig', environ: 'Mapping[str, str]') -> 'None'` [source](../../packages/sdk/src/open_table_connector/sdk/credentials.py) |
| `ErrorCode` | enum | `(value, names=None, *, module=None, qualname=None, type=None, start=1, boundary=None)` [source](../../packages/sdk/src/open_table_connector/sdk/result.py) |
| `ErrorInfo` | class | `(code: 'ErrorCode', message: 'str', safe_details: 'Mapping[str, Any]' = <factory>, reconciliation: 'ReconciliationReference \| None' = None) -> None` [source](../../packages/sdk/src/open_table_connector/sdk/result.py) |
| `ExistingTableAddress` | constant | `open_table_connector.sdk.model.DirectTableAddress \| open_table_connector.sdk.model.DatabaseTableAddress \| open_table_connector.sdk.model.BaseModeTableAddress \| open_table_connector.sdk.model.SheetModeTableAddress`  |
| `FEISHU_BITABLE` | constant | `'feishu-bitable'`  |
| `FIELD_READ` | constant | `CapabilityIdentity(capability_id='formula.field.read', capability_version='1.0')`  |
| `FIELD_RECALCULATE` | constant | `CapabilityIdentity(capability_id='formula.field.recalculate', capability_version='1.0')`  |
| `FIELD_SET` | constant | `CapabilityIdentity(capability_id='formula.field.set', capability_version='1.0')`  |
| `FIELD_VALUES_READ` | constant | `CapabilityIdentity(capability_id='formula.field.values.read', capability_version='1.0')`  |
| `FieldFormulaObservation` | class | `(table_uri: 'TableURI \| str', field_id: 'str', field_name: 'str', expression: 'FormulaExpression', result_type: 'str \| None', observed_revision: 'str') -> None` [source](../../packages/formulas/src/open_table_connector/formulas/observations.py) |
| `FieldFormulaTarget` | class | `(table: '_TTable', field: 'FieldRef') -> None` [source](../../packages/formulas/src/open_table_connector/formulas/model.py) |
| `FieldFormulaValueObservation` | class | `(table_uri: 'TableURI \| str', field_id: 'str', field_name: 'str', values: 'tuple[FormulaRecordValue, ...]', calculation_state: 'CalculationState', calculation_trigger: 'CalculationTrigger', dependency_scope: 'str', observed_revision: 'str') -> None` [source](../../packages/formulas/src/open_table_connector/formulas/observations.py) |
| `FieldFormulaView` | class | `(client: 'Client', *, owner_token: 'object', connector_id: 'str', extension: 'FormulaConnectorExtension', table_binding: 'TableBinding', binding: 'FieldFormulaBinding[Table]') -> 'None'` [source](../../packages/sdk/src/open_table_connector/sdk/formula.py) |
| `FieldRecalculationScope` | enum | `(value, names=None, *, module=None, qualname=None, type=None, start=1, boundary=None)` [source](../../packages/formulas/src/open_table_connector/formulas/model.py) |
| `FieldRef` | class | `(name: 'str \| None' = None, field_id: 'str \| None' = None) -> None` [source](../../packages/formulas/src/open_table_connector/formulas/model.py) |
| `FillMode` | enum | `(value, names=None, *, module=None, qualname=None, type=None, start=1, boundary=None)` [source](../../packages/timeseries/src/open_table_connector/timeseries/plan.py) |
| `FillRule` | class | `(field: 'str', mode: 'FillMode', value: 'JsonScalar') -> None` [source](../../packages/timeseries/src/open_table_connector/timeseries/plan.py) |
| `FixedBucket` | class | `(width_ns: 'int', origin: 'str', offset_ns: 'int' = 0) -> None` [source](../../packages/timeseries/src/open_table_connector/timeseries/plan.py) |
| `FormulaCapabilityDetails` | class | `(target_kind: 'str', dialects: 'tuple[str, ...]', max_cells_per_operation: 'int \| None', max_expression_bytes: 'int', recalculation_scopes: 'tuple[str, ...]', calculation_states: 'tuple[CalculationState, ...]', mutation_atomicity: 'MutationAtomicity', revision_enforcement: 'RevisionEnforcement', idempotency_strength: 'IdempotencyStrength') -> None` [source](../../packages/formulas/src/open_table_connector/formulas/observations.py) |
| `FormulaCapabilitySet` | class | `(capabilities: 'tuple[CapabilityIdentity, ...]', details: 'FormulaCapabilityDetails') -> None` [source](../../packages/formulas/src/open_table_connector/formulas/observations.py) |
| `FormulaCell` | class | `(address: 'str', expression: 'FormulaExpression') -> None` [source](../../packages/formulas/src/open_table_connector/formulas/observations.py) |
| `FormulaError` | class | `(signature unavailable; see source)` [source](../../packages/formulas/src/open_table_connector/formulas/errors.py) |
| `FormulaErrorValue` | class | `(code: 'str') -> None` [source](../../packages/formulas/src/open_table_connector/formulas/observations.py) |
| `FormulaExpression` | class | `(text: 'str', dialect: 'str') -> None` [source](../../packages/formulas/src/open_table_connector/formulas/model.py) |
| `FormulaMutation` | class | `(target_kind: 'str', affected_count: 'int', formula_observation: 'GridFormulaObservation \| FieldFormulaObservation', revision_before: 'str \| None', revision_after: 'str') -> None` [source](../../packages/formulas/src/open_table_connector/formulas/observations.py) |
| `FormulaRecordValue` | class | `(record_id: 'str', value: 'FormulaValue') -> None` [source](../../packages/formulas/src/open_table_connector/formulas/observations.py) |
| `FormulaResourceLimits` | class | `(max_cells: 'int \| None' = None, max_records: 'int \| None' = None, max_response_bytes: 'int \| None' = None, timeout_seconds: 'float \| None' = None, max_expression_bytes: 'int \| None' = None) -> None` [source](../../packages/formulas/src/open_table_connector/formulas/model.py) |
| `FormulaValue` | class | `(kind: 'str', value: 'object' = None, logical_type: 'str \| None' = None) -> None` [source](../../packages/formulas/src/open_table_connector/formulas/observations.py) |
| `FormulaValueCell` | class | `(address: 'str', value: 'FormulaValue') -> None` [source](../../packages/formulas/src/open_table_connector/formulas/observations.py) |
| `GOOGLE_SHEETS_A1` | constant | `'google-sheets-a1'`  |
| `GRID_READ` | constant | `CapabilityIdentity(capability_id='formula.grid.read', capability_version='1.0')`  |
| `GRID_RECALCULATE` | constant | `CapabilityIdentity(capability_id='formula.grid.recalculate', capability_version='1.0')`  |
| `GRID_SET` | constant | `CapabilityIdentity(capability_id='formula.grid.set', capability_version='1.0')`  |
| `GRID_VALUES_READ` | constant | `CapabilityIdentity(capability_id='formula.grid.values.read', capability_version='1.0')`  |
| `GridFormulaObservation` | class | `(worksheet_id: 'str', requested_range: 'str', formulas: 'tuple[FormulaCell, ...]', observed_revision: 'str') -> None` [source](../../packages/formulas/src/open_table_connector/formulas/observations.py) |
| `GridFormulaTarget` | class | `(grid: 'TableURI \| str', worksheet: 'WorksheetRef') -> None` [source](../../packages/formulas/src/open_table_connector/formulas/model.py) |
| `GridFormulaValueObservation` | class | `(worksheet_id: 'str', requested_range: 'str', values: 'tuple[FormulaValueCell, ...]', calculation_state: 'CalculationState', calculation_trigger: 'CalculationTrigger', dependency_scope: 'str', observed_revision: 'str') -> None` [source](../../packages/formulas/src/open_table_connector/formulas/observations.py) |
| `GridFormulaView` | class | `(client: 'Client', *, owner_token: 'object', connector_id: 'str', extension: 'FormulaConnectorExtension', binding: 'GridFormulaBinding') -> 'None'` [source](../../packages/sdk/src/open_table_connector/sdk/formula.py) |
| `GridRecalculationScope` | enum | `(value, names=None, *, module=None, qualname=None, type=None, start=1, boundary=None)` [source](../../packages/formulas/src/open_table_connector/formulas/model.py) |
| `IdempotencyStrength` | enum | `(value, names=None, *, module=None, qualname=None, type=None, start=1, boundary=None)` [source](../../packages/formulas/src/open_table_connector/formulas/observations.py) |
| `LegacyConnectorAdapterBridge` | class | `(adapter: 'ConnectorAdapter') -> 'None'` [source](../../packages/sdk/src/open_table_connector/sdk/connector.py) |
| `MATERIALIZE_CREATE_CAPABILITY` | constant | `CapabilityIdentity(capability_id='table.materialize.create', capability_version='1.0')`  |
| `MAYBE_BASE` | constant | `'maybe-base'`  |
| `MAYBE_SHEET_A1` | constant | `'maybe-sheet-a1'`  |
| `ManagedSnapshot` | class | `(logical_target: 'TableURI', stage_id: 'str', snapshot_id: 'str', snapshot_reference: 'str', descriptor_hash: 'str', committed_at: 'str', _binding: 'TableBinding', _owner_client_id: 'str', retention_expires_at: 'str \| None' = None) -> None` [source](../../packages/sdk/src/open_table_connector/sdk/temporal.py) |
| `ManagedSnapshotState` | class | `(snapshot: 'ManagedSnapshot', schema: 'pa.Schema') -> None` [source](../../packages/sdk/src/open_table_connector/sdk/temporal.py) |
| `ManagedStage` | class | `(logical_target: 'TableURI', physical_target: 'TableURI', stage_id: 'str', idempotency_key: 'str', descriptor_hash: 'str', artifact_hash: 'str', staged_at: 'str', _binding: 'TableBinding', _owner_client_id: 'str', lease_expires_at: 'str \| None' = None) -> None` [source](../../packages/sdk/src/open_table_connector/sdk/temporal.py) |
| `MaterializationRequest` | class | `(source: 'pl.DataFrame', destination: 'TableDestination', profile: 'str', idempotency_key: 'str') -> None` [source](../../packages/sdk/src/open_table_connector/sdk/materialization.py) |
| `MutationAtomicity` | enum | `(value, names=None, *, module=None, qualname=None, type=None, start=1, boundary=None)` [source](../../packages/formulas/src/open_table_connector/formulas/observations.py) |
| `NativeSql` | class | `(client: 'Client', target: 'str \| TableURI') -> 'None'` [source](../../packages/sdk/src/open_table_connector/sdk/sql.py) |
| `NativeSqlResourceLimits` | class | `(max_rows: 'int' = 100000, max_bytes: 'int' = 134217728, max_duration_ms: 'int' = 30000) -> None` [source](../../packages/sdk/src/open_table_connector/sdk/sql.py) |
| `OPERATION_CATALOG_GROUP` | constant | `'open_table_connector.operation_catalogs.v1'`  |
| `OPERATION_HANDLER_GROUP` | constant | `'open_table_connector.operation_handlers.v1'`  |
| `OTCError` | class | `(message: 'str', result: 'OperationResult[Any]') -> 'None'` [source](../../packages/sdk/src/open_table_connector/sdk/result.py) |
| `OperationCatalog` | class | `(descriptors: 'Iterable[OperationDescriptor]' = ()) -> 'None'` [source](../../packages/sdk/src/open_table_connector/sdk/discovery.py) |
| `OperationResult` | class | `(value: 'T \| None', outcome: 'Outcome', commit: 'CommitState', verification: 'VerificationState', receipts: 'tuple[Receipt, ...]', continuation: 'str \| None' = None, warnings: 'tuple[OperationWarning, ...]' = (), error: 'ErrorInfo \| None' = None) -> None` [source](../../packages/sdk/src/open_table_connector/sdk/result.py) |
| `OperationWarning` | class | `(code: 'str', message: 'str', safe_details: 'Mapping[str, Any]' = <factory>) -> None` [source](../../packages/sdk/src/open_table_connector/sdk/result.py) |
| `Outcome` | enum | `(value, names=None, *, module=None, qualname=None, type=None, start=1, boundary=None)` [source](../../packages/sdk/src/open_table_connector/sdk/result.py) |
| `PORTABLE_TABLE_PROFILE_V1` | constant | `'otc.portable-table/v1'`  |
| `PolarsPlanMapper` | class | `()` [source](../../packages/sdk/src/open_table_connector/sdk/sql.py) |
| `PortablePredicate` | class | `(expression: 'str \| None' = None, parameters: 'Mapping[str, Any]' = <factory>, kind: 'PredicateKind' = <PredicateKind.SQL: 'sql'>) -> None` [source](../../packages/sdk/src/open_table_connector/sdk/predicates.py) |
| `PredicateKind` | enum | `(value, names=None, *, module=None, qualname=None, type=None, start=1, boundary=None)` [source](../../packages/sdk/src/open_table_connector/sdk/predicates.py) |
| `QualifiedTableName` | class | `(table: 'str', schema: 'str \| None' = None, catalog: 'str \| None' = None) -> None` [source](../../packages/sdk/src/open_table_connector/sdk/model.py) |
| `Query` | class | `(lane: 'QueryLane', statement: 'str', sources: 'Mapping[str, object]', parameters: 'Mapping[str, Any]' = <factory>, limits: 'object' = <factory>, _definition: 'object \| None' = None) -> None` [source](../../packages/sdk/src/open_table_connector/sdk/query.py) |
| `QueryLane` | enum | `(value, names=None, *, module=None, qualname=None, type=None, start=1, boundary=None)` [source](../../packages/sdk/src/open_table_connector/sdk/query.py) |
| `RecalculationObservation` | class | `(target_kind: 'str', requested_scope: 'str', effective_scope: 'str', revision_before: 'str \| None', revision_after: 'str \| None', provider_status: 'str', calculation_state: 'CalculationState', verification: 'str', value_observation: 'GridFormulaValueObservation \| FieldFormulaValueObservation \| None') -> None` [source](../../packages/formulas/src/open_table_connector/formulas/observations.py) |
| `Receipt` | class | `(kind: 'str', operation: 'str', connector_id: 'str \| None' = None, capability: 'str \| None' = None, safe_target: 'TableURI \| None' = None, mode: 'TableMode \| None' = None, details: 'Mapping[str, Any]' = <factory>) -> None` [source](../../packages/sdk/src/open_table_connector/sdk/result.py) |
| `ReconciliationReference` | class | `(operation_id: 'str', connector_id: 'str \| None' = None, idempotency_key: 'str \| None' = None, expires_at: 'str \| None' = None) -> None` [source](../../packages/sdk/src/open_table_connector/sdk/result.py) |
| `RevisionEnforcement` | enum | `(value, names=None, *, module=None, qualname=None, type=None, start=1, boundary=None)` [source](../../packages/formulas/src/open_table_connector/formulas/observations.py) |
| `SchemaPolicy` | enum | `(value, names=None, *, module=None, qualname=None, type=None, start=1, boundary=None)` [source](../../packages/sdk/src/open_table_connector/sdk/model.py) |
| `SheetModeDestination` | class | `(grid: 'TableURI \| str', anchor: 'str', header: 'bool', worksheet: 'str \| None' = None) -> None` [source](../../packages/sdk/src/open_table_connector/sdk/model.py) |
| `SheetModeTableAddress` | class | `(grid: 'TableURI \| str', table_id: 'str') -> None` [source](../../packages/sdk/src/open_table_connector/sdk/model.py) |
| `SheetRangeSource` | class | `(grid: 'TableURI \| str', cell_range: 'str', header: 'bool', schema: 'pl.Schema \| None', schema_policy: 'SchemaPolicy', observed_revision: 'str \| None' = None, _owner_token: 'object \| None' = None) -> None` [source](../../packages/sdk/src/open_table_connector/sdk/model.py) |
| `SqlResourceLimits` | class | `(max_source_rows: 'int' = 1000000, max_source_bytes: 'int' = 268435456, max_total_input_rows: 'int' = 2000000, max_total_input_bytes: 'int' = 536870912, max_intermediate_rows: 'int' = 2000000, max_intermediate_bytes: 'int' = 536870912, max_output_rows: 'int' = 100000, max_output_bytes: 'int' = 134217728, max_duration_ms: 'int' = 30000) -> None` [source](../../packages/sdk/src/open_table_connector/sdk/query.py) |
| `Table` | class | `(client: 'Client', binding: 'TableBinding') -> 'None'` [source](../../packages/sdk/src/open_table_connector/sdk/table.py) |
| `TableBinding` | class | `(uri: 'TableURI', mode: 'TableMode', schema: 'pl.Schema \| None', observed_revision: 'str \| None', connector_id: 'str', profile: 'str \| None' = None, row_count: 'int \| None' = None, schema_fingerprint: 'str \| None' = None, content_fingerprint: 'str \| None' = None, address: 'ExistingTableAddress \| None' = None, schema_observed: 'bool' = True, layout_binding: 'Mapping[str, Any] \| None' = None) -> None` [source](../../packages/sdk/src/open_table_connector/sdk/table.py) |
| `TableConnector` | class | `(*args, **kwargs)` [source](../../packages/sdk/src/open_table_connector/sdk/connector.py) |
| `TableDestination` | constant | `open_table_connector.sdk.model.DirectDestination \| open_table_connector.sdk.model.BaseModeDestination \| open_table_connector.sdk.model.SheetModeDestination`  |
| `TableInspection` | class | `(uri: 'TableURI', mode: 'TableMode', schema: 'pl.Schema', row_count: 'int \| None' = None, observed_revision: 'str \| None' = None, facts: 'Mapping[str, Any]' = <factory>) -> None` [source](../../packages/sdk/src/open_table_connector/sdk/table.py) |
| `TableLayoutSession` | class | `(table, connector, payload: 'Mapping[str, Any]') -> 'None'` [source](../../packages/sdk/src/open_table_connector/sdk/layout.py) |
| `TableMode` | enum | `(value, names=None, *, module=None, qualname=None, type=None, start=1, boundary=None)` [source](../../packages/sdk/src/open_table_connector/sdk/model.py) |
| `TableTransaction` | class | `(table: 'Table', *, idempotency_key: 'str \| None' = None) -> 'None'` [source](../../packages/sdk/src/open_table_connector/sdk/table.py) |
| `TemporalConnectorExtension` | class | `(*args, **kwargs)` [source](../../packages/sdk/src/open_table_connector/sdk/temporal.py) |
| `TemporalResourceLimits` | class | `(max_rows: 'int' = 100000, max_bytes: 'int' = 134217728, max_duration_ms: 'int' = 30000) -> None` [source](../../packages/sdk/src/open_table_connector/sdk/temporal.py) |
| `TemporalTableDescriptor` | class | `(time_field: 'str', timezone: 'str', precision: 'TimestampPrecision', series_key_fields: 'tuple[str, ...]', tag_fields: 'tuple[str, ...]', value_fields: 'tuple[str, ...]', ingestion_time_field: 'str \| None', duplicate_policy: 'DuplicatePolicy', ordering: 'TemporalOrdering') -> None` [source](../../packages/timeseries/src/open_table_connector/timeseries/descriptor.py) |
| `TimeSeriesView` | class | `(table: 'Table', descriptor: 'TemporalTableDescriptor') -> 'None'` [source](../../packages/sdk/src/open_table_connector/sdk/temporal.py) |
| `VerificationState` | enum | `(value, names=None, *, module=None, qualname=None, type=None, start=1, boundary=None)` [source](../../packages/sdk/src/open_table_connector/sdk/result.py) |
| `WorkbookAccess` | class | `(client: 'Client') -> 'None'` [source](../../packages/sdk/src/open_table_connector/sdk/workbook.py) |
| `WorksheetRef` | class | `(name: 'str \| None' = None, worksheet_id: 'str \| None' = None) -> None` [source](../../packages/formulas/src/open_table_connector/formulas/model.py) |
| `all_rows` | function | `() -> 'PortablePredicate'` [source](../../packages/sdk/src/open_table_connector/sdk/predicates.py) |
| `apply_credential_overrides` | function | `(config: 'ClientConfig', overrides: 'Mapping[str, str]') -> 'ClientConfig'` [source](../../packages/sdk/src/open_table_connector/sdk/credentials.py) |
| `capture_workbook_snapshot` | function | `(client, target: 'TargetSelector \| str', directory) -> 'OperationResult[WorkbookSnapshot]'` [source](../../packages/sdk/src/open_table_connector/sdk/snapshots.py) |
| `close_default_client` | function | `() -> 'None'` [source](../../packages/sdk/src/open_table_connector/otc/__init__.py) |
| `collect` | function | `(source: 'object')` [source](../../packages/sdk/src/open_table_connector/otc/__init__.py) |
| `configure` | function | `(client: '_sdk.Client') -> '_sdk.Client'` [source](../../packages/sdk/src/open_table_connector/otc/__init__.py) |
| `discover_configured_plugins` | function | `(config: 'ClientConfig', *, entries: 'Iterable[EntryPoint] \| None' = None) -> 'tuple[ConfiguredPlugin, ...]'` [source](../../packages/sdk/src/open_table_connector/sdk/registry.py) |
| `discover_descriptors` | function | `(entries: 'Iterable[EntryPoint] \| None' = None) -> 'tuple[PluginDescriptor, ...]'` [source](../../packages/sdk/src/open_table_connector/sdk/registry.py) |
| `discover_operation_descriptors` | function | `(entries: 'Iterable[EntryPoint] \| None' = None) -> 'tuple[OperationDescriptor, ...]'` [source](../../packages/sdk/src/open_table_connector/sdk/discovery.py) |
| `discover_operation_handlers` | function | `() -> 'tuple[tuple[str, str, str, Handler], ...]'` [source](../../packages/sdk/src/open_table_connector/sdk/operations.py) |
| `execute_operation` | function | `(client, request: 'OperationRequest', options: 'ExecutionOptions', *, catalog: 'OperationCatalog \| None' = None) -> 'OperationResult[object]'` [source](../../packages/sdk/src/open_table_connector/sdk/operations.py) |
| `load_client_config` | function | `(explicit: 'str \| Path \| None' = None, *, environ: 'Mapping[str, str] \| None' = None, home: 'Path \| None' = None) -> 'ClientConfig'` [source](../../packages/sdk/src/open_table_connector/sdk/config.py) |
| `materialize` | function | `(source: 'object', *, to: 'str \| _sdk.TableDestination')` [source](../../packages/sdk/src/open_table_connector/otc/__init__.py) |
| `open` | function | `(target: 'str \| Any')` [source](../../packages/sdk/src/open_table_connector/otc/__init__.py) |
| `parse_credential_overrides` | function | `(values: 'Sequence[str]') -> 'Mapping[str, str]'` [source](../../packages/sdk/src/open_table_connector/sdk/credentials.py) |
| `read` | function | `(target: 'str \| Any')` [source](../../packages/sdk/src/open_table_connector/otc/__init__.py) |
| `register_operation_handler` | function | `(namespace: 'str', operation_id: 'str', version: 'str', handler: 'Handler') -> 'None'` [source](../../packages/sdk/src/open_table_connector/sdk/operations.py) |
| `resolve_capabilities` | function | `(client, target: 'TargetSelector \| str', *, catalog: 'OperationCatalog \| None' = None) -> 'OperationResult[CapabilityObservation]'` [source](../../packages/sdk/src/open_table_connector/sdk/discovery.py) |
| `resolve_config_path` | function | `(explicit: 'str \| Path \| None', environ: 'Mapping[str, str]', *, home: 'Path \| None' = None) -> 'Path \| None'` [source](../../packages/sdk/src/open_table_connector/sdk/config.py) |
| `sql` | function | `(statement: 'str', *, sources: 'dict[str, object]', parameters: 'dict[str, Any] \| None' = None, limits: 'SqlResourceLimits \| None' = None) -> 'Query'` [source](../../packages/sdk/src/open_table_connector/sdk/sql.py) |
| `time_series` | function | `(source: 'object', descriptor: '_sdk.TemporalTableDescriptor')` [source](../../packages/sdk/src/open_table_connector/otc/__init__.py) |

### A1Rectangle

| Field | Declared type |
| --- | --- |
| `end_address` | `str` |
| `end_column` | `int` |
| `end_row` | `int` |
| `start_address` | `str` |
| `start_column` | `int` |
| `start_row` | `int` |
| `worksheet_name` | `str \| None` |

| Public member | Signature or access |
| --- | --- |
| `cell_count` | `property (read-only)` |
| `height` | `property (read-only)` |
| `parse` | `(selector: 'str') -> 'A1Rectangle'` |
| `require_unbound_selector` | `(self, selector: 'str') -> 'A1Rectangle'` |
| `width` | `property (read-only)` |

### AbortDisposition

| Member | Wire value |
| --- | --- |
| `ABORTED` | `aborted` |
| `ALREADY_ABORTED` | `already_aborted` |
| `ALREADY_COMMITTED` | `already_committed` |
| `EXPIRED` | `expired` |

### AggregateFunction

| Member | Wire value |
| --- | --- |
| `COUNT` | `count` |
| `MIN` | `min` |
| `MAX` | `max` |
| `SUM` | `sum` |
| `AVG` | `avg` |
| `FIRST` | `first` |
| `LAST` | `last` |

### AggregateMeasure

| Field | Declared type |
| --- | --- |
| `function` | `AggregateFunction` |
| `output_field` | `str` |
| `value_field` | `str \| None` |

| Public member | Signature or access |
| --- | --- |
| `to_wire` | `(self) -> 'dict[str, object]'` |

### ArtifactAccess

| Public member | Signature or access |
| --- | --- |
| `export` | `(self, request)` |
| `view` | `(self, request)` |
| `watch` | `(self, request)` |

### BaseModeDestination

| Field | Declared type |
| --- | --- |
| `container` | `TableURI \| str` |
| `table_name` | `str` |

| Public member | Signature or access |
| --- | --- |
| `from_wire` | `(payload: 'Mapping[str, Any]') -> 'BaseModeDestination'` |
| `to_wire` | `(self) -> 'dict[str, Any]'` |

### BaseModeTableAddress

| Field | Declared type |
| --- | --- |
| `container` | `TableURI \| str` |
| `table_id` | `str` |

| Public member | Signature or access |
| --- | --- |
| `from_wire` | `(payload: 'Mapping[str, Any]') -> 'BaseModeTableAddress'` |
| `to_wire` | `(self) -> 'dict[str, Any]'` |

### CalculationState

| Member | Wire value |
| --- | --- |
| `PROVIDER_CURRENT` | `provider_current` |
| `CACHED` | `cached` |
| `UNKNOWN` | `unknown` |

### CalculationTrigger

| Member | Wire value |
| --- | --- |
| `EXPLICIT_RECALCULATION` | `explicit_recalculation` |
| `MUTATION` | `mutation` |
| `PROVIDER_READ` | `provider_read` |
| `STORED_CACHE` | `stored_cache` |

### CalendarBucket

| Field | Declared type |
| --- | --- |
| `count` | `int` |
| `offset_ns` | `int` |
| `origin` | `str` |
| `timezone` | `str` |
| `unit` | `CalendarUnit` |
| `week_start` | `int` |

| Public member | Signature or access |
| --- | --- |
| `to_wire` | `(self) -> 'dict[str, object]'` |

### CapabilitySet

| Field | Declared type |
| --- | --- |
| `capability_ids` | `tuple[str, ...]` |
| `details` | `Mapping[str, Any]` |
| `modes` | `tuple[TableMode, ...]` |

| Public member | Signature or access |
| --- | --- |
| `supports` | `(self, capability_id: 'str') -> 'bool'` |

### Client

| Public member | Signature or access |
| --- | --- |
| `artifacts` | `(self)` |
| `bind_sheet_range` | `(self, *, grid: 'TableURI \| str', cell_range: 'str', header: 'bool', schema: 'pl.Schema \| None' = None, schema_policy: 'SchemaPolicy' = <SchemaPolicy.VALIDATE_DECLARED: 'validate_declared'>) -> 'OperationResult[SheetRangeSource]'` |
| `close` | `(self) -> 'None'` |
| `collect` | `(self, source: 'object') -> 'OperationResult[pl.DataFrame]'` |
| `copy_workbook` | `(self, source: 'str \| TableURI', *, to: 'str \| TableURI \| None' = None, title: 'str \| None' = None, limits: 'Any' = None)` |
| `formulas` | `(self, target)` |
| `from_config` | `(config: 'ClientConfig \| str \| Path', *, descriptors: 'Iterable[PluginDescriptor] \| None' = None, resolver: 'CredentialResolver \| None' = None, environ: 'dict[str, str] \| None' = None, transports: 'dict[str, Any] \| None' = None) -> 'Client'` |
| `materialize` | `(self, source: 'object', *, to: 'str \| TableDestination', profile: 'str \| None' = None, idempotency_key: 'str \| None' = None)` |
| `native_sql` | `(self, target: 'str \| TableURI') -> 'NativeSql'` |
| `open` | `(self, target: 'str \| TableURI \| ExistingTableAddress', *, schema: 'pl.Schema \| None' = None, metadata_only: 'bool' = False)` |
| `reconcile_materialization` | `(self, reference: 'ReconciliationReference', *, destination: 'BaseModeDestination')` |
| `sql` | `(self, statement: 'str', *, sources: 'dict[str, object]', parameters: 'dict[str, Any] \| None' = None, limits: 'SqlResourceLimits \| None' = None) -> 'OperationResult[pl.DataFrame]'` |
| `workbook` | `property (read-only)` |

### ClientConfig

| Field | Declared type |
| --- | --- |
| `credentials` | `Mapping[str, Mapping[str, CredentialBinding]]` |
| `providers` | `Mapping[str, ProviderConfig]` |

| Public member | Signature or access |
| --- | --- |
| `empty` | `() -> 'ClientConfig'` |

### CommitState

| Member | Wire value |
| --- | --- |
| `NOT_APPLICABLE` | `not_applicable` |
| `NOT_STARTED` | `not_started` |
| `NOT_COMMITTED` | `not_committed` |
| `COMMITTED` | `committed` |
| `PARTIAL` | `partial` |
| `UNKNOWN` | `unknown` |

### ConfiguredPlugin

| Field | Declared type |
| --- | --- |
| `config` | `ProviderConfig` |
| `descriptor` | `PluginDescriptor` |

### ConnectorRegistry

| Public member | Signature or access |
| --- | --- |
| `close` | `(self) -> 'None'` |
| `connector_for` | `(self, target: 'str \| object') -> 'TableConnector'` |
| `descriptor_for` | `(self, target: 'str \| object') -> 'PluginDescriptor'` |
| `from_descriptors` | `(descriptors: 'Iterable[PluginDescriptor]', config: 'ClientConfig', *, resolver: 'CredentialResolver \| None' = None, environ: 'Mapping[str, str] \| None' = None, transports: 'Mapping[str, Any] \| None' = None) -> 'ConnectorRegistry'` |
| `list` | `(self) -> 'tuple[PluginDescriptor, ...]'` |
| `register` | `(self, connector: 'TableConnector') -> 'None'` |

### CredentialBinding

| Field | Declared type |
| --- | --- |
| `env` | `str` |

### CredentialLease

| Public member | Signature or access |
| --- | --- |
| `dispose` | `(self) -> 'None'` |
| `values` | `property (read-only)` |

### CredentialResolver

| Public member | Signature or access |
| --- | --- |
| `resolve` | `(self, provider: 'ProviderConfig') -> 'CredentialLease'` |

### DatabaseTableAddress

| Field | Declared type |
| --- | --- |
| `database` | `TableURI \| str` |
| `name` | `QualifiedTableName` |

| Public member | Signature or access |
| --- | --- |
| `from_wire` | `(payload: 'Mapping[str, Any]') -> 'DatabaseTableAddress'` |
| `to_wire` | `(self) -> 'dict[str, Any]'` |

### DirectDestination

| Field | Declared type |
| --- | --- |
| `uri` | `TableURI \| str` |

| Public member | Signature or access |
| --- | --- |
| `from_wire` | `(payload: 'Mapping[str, Any]') -> 'DirectDestination'` |
| `to_wire` | `(self) -> 'dict[str, Any]'` |

### DirectTableAddress

| Field | Declared type |
| --- | --- |
| `uri` | `TableURI \| str` |

| Public member | Signature or access |
| --- | --- |
| `from_wire` | `(payload: 'Mapping[str, Any]') -> 'DirectTableAddress'` |
| `to_wire` | `(self) -> 'dict[str, Any]'` |

### EnvironmentCredentialResolver

| Public member | Signature or access |
| --- | --- |
| `resolve` | `(self, provider: 'ProviderConfig') -> 'CredentialLease'` |

### ErrorCode

| Member | Wire value |
| --- | --- |
| `INVALID_TARGET` | `invalid_target` |
| `INVALID_FORMULA` | `invalid_formula` |
| `INVALID_SCHEMA` | `invalid_schema` |
| `INVALID_PREDICATE` | `invalid_predicate` |
| `INVALID_SQL` | `invalid_sql` |
| `INVALID_DESCRIPTOR` | `invalid_descriptor` |
| `INVALID_CONFIGURATION` | `invalid_configuration` |
| `UNSUPPORTED_CAPABILITY` | `unsupported_capability` |
| `UNSUPPORTED_MODE` | `unsupported_mode` |
| `AUTHENTICATION` | `authentication` |
| `AUTHORIZATION` | `authorization` |
| `DESTINATION_EXISTS` | `destination_exists` |
| `TARGET_NOT_FOUND` | `target_not_found` |
| `STALE_REVISION` | `stale_revision` |
| `KEY_CONFLICT` | `key_conflict` |
| `DUPLICATE_UPDATE_KEY` | `duplicate_update_key` |
| `MISSING_UPDATE_KEY` | `missing_update_key` |
| `IDEMPOTENCY_CONFLICT` | `idempotency_conflict` |
| `RESOURCE_LIMIT` | `resource_limit` |
| `TIMEOUT` | `timeout` |
| `CANCELLED` | `cancelled` |
| `SNAPSHOT_UNAVAILABLE` | `snapshot_unavailable` |
| `EXECUTION_FAILED` | `execution_failed` |
| `PARTIAL_EFFECT` | `partial_effect` |
| `UNCERTAIN_MUTATION` | `uncertain_mutation` |
| `RECONCILIATION_UNAVAILABLE` | `reconciliation_unavailable` |
| `READBACK_MISMATCH` | `readback_mismatch` |
| `PROTOCOL_FAILURE` | `protocol_failure` |
| `ARTIFACT_INTEGRITY` | `artifact_integrity` |
| `CLIENT_CLOSED` | `client_closed` |
| `CLIENT_AFFINITY_MISMATCH` | `client_affinity_mismatch` |

### ErrorInfo

| Field | Declared type |
| --- | --- |
| `code` | `ErrorCode` |
| `message` | `str` |
| `reconciliation` | `ReconciliationReference \| None` |
| `safe_details` | `Mapping[str, Any]` |

| Public member | Signature or access |
| --- | --- |
| `from_wire` | `(payload: 'Mapping[str, Any]') -> 'ErrorInfo'` |
| `to_wire` | `(self) -> 'dict[str, Any]'` |

### FieldFormulaObservation

| Field | Declared type |
| --- | --- |
| `expression` | `FormulaExpression` |
| `field_id` | `str` |
| `field_name` | `str` |
| `observed_revision` | `str` |
| `result_type` | `str \| None` |
| `table_uri` | `TableURI \| str` |

| Public member | Signature or access |
| --- | --- |
| `from_wire` | `(payload: 'Mapping[str, Any]') -> 'FieldFormulaObservation'` |
| `to_wire` | `(self) -> 'dict[str, object]'` |

### FieldFormulaTarget

| Field | Declared type |
| --- | --- |
| `field` | `FieldRef` |
| `table` | `_TTable` |

### FieldFormulaValueObservation

| Field | Declared type |
| --- | --- |
| `calculation_state` | `CalculationState` |
| `calculation_trigger` | `CalculationTrigger` |
| `dependency_scope` | `str` |
| `field_id` | `str` |
| `field_name` | `str` |
| `observed_revision` | `str` |
| `table_uri` | `TableURI \| str` |
| `values` | `tuple[FormulaRecordValue, ...]` |

| Public member | Signature or access |
| --- | --- |
| `from_wire` | `(payload: 'Mapping[str, Any]') -> 'FieldFormulaValueObservation'` |
| `to_wire` | `(self) -> 'dict[str, object]'` |

### FieldFormulaView

| Public member | Signature or access |
| --- | --- |
| `read` | `(self) -> 'OperationResult[FieldFormulaObservation]'` |
| `read_values` | `(self, *, limits: 'FormulaResourceLimits \| None' = None) -> 'OperationResult[FieldFormulaValueObservation]'` |
| `recalculate` | `(self, *, scope: 'FieldRecalculationScope', expected_revision: 'str \| None' = None, idempotency_key: 'str \| None' = None) -> 'OperationResult[RecalculationObservation]'` |
| `set` | `(self, expression: 'FormulaExpression', *, expected_revision: 'str \| None' = None, idempotency_key: 'str \| None' = None) -> 'OperationResult[FormulaMutation]'` |

### FieldRecalculationScope

| Member | Wire value |
| --- | --- |
| `FIELD` | `field` |
| `TABLE` | `table` |

### FieldRef

| Field | Declared type |
| --- | --- |
| `field_id` | `str \| None` |
| `name` | `str \| None` |

### FillMode

| Member | Wire value |
| --- | --- |
| `NULL` | `null` |
| `CONSTANT` | `constant` |
| `LOCF` | `locf` |
| `LINEAR` | `linear` |

### FillRule

| Field | Declared type |
| --- | --- |
| `field` | `str` |
| `mode` | `FillMode` |
| `value` | `JsonScalar` |

| Public member | Signature or access |
| --- | --- |
| `to_wire` | `(self) -> 'dict[str, object]'` |

### FixedBucket

| Field | Declared type |
| --- | --- |
| `offset_ns` | `int` |
| `origin` | `str` |
| `width_ns` | `int` |

| Public member | Signature or access |
| --- | --- |
| `to_wire` | `(self) -> 'dict[str, object]'` |

### FormulaCapabilityDetails

| Field | Declared type |
| --- | --- |
| `calculation_states` | `tuple[CalculationState, ...]` |
| `dialects` | `tuple[str, ...]` |
| `idempotency_strength` | `IdempotencyStrength` |
| `max_cells_per_operation` | `int \| None` |
| `max_expression_bytes` | `int` |
| `mutation_atomicity` | `MutationAtomicity` |
| `recalculation_scopes` | `tuple[str, ...]` |
| `revision_enforcement` | `RevisionEnforcement` |
| `target_kind` | `str` |

| Public member | Signature or access |
| --- | --- |
| `from_wire` | `(payload: 'Mapping[str, Any]') -> 'FormulaCapabilityDetails'` |
| `to_wire` | `(self) -> 'dict[str, object]'` |

### FormulaCapabilitySet

| Field | Declared type |
| --- | --- |
| `capabilities` | `tuple[CapabilityIdentity, ...]` |
| `details` | `FormulaCapabilityDetails` |

| Public member | Signature or access |
| --- | --- |
| `from_wire` | `(payload: 'Mapping[str, Any]') -> 'FormulaCapabilitySet'` |
| `to_wire` | `(self) -> 'dict[str, object]'` |

### FormulaCell

| Field | Declared type |
| --- | --- |
| `address` | `str` |
| `expression` | `FormulaExpression` |

| Public member | Signature or access |
| --- | --- |
| `from_wire` | `(payload: 'Mapping[str, Any]') -> 'FormulaCell'` |
| `to_wire` | `(self) -> 'dict[str, object]'` |

### FormulaError

### FormulaErrorValue

| Field | Declared type |
| --- | --- |
| `code` | `str` |

| Public member | Signature or access |
| --- | --- |
| `from_wire` | `(payload: 'Mapping[str, Any]') -> 'FormulaErrorValue'` |
| `to_wire` | `(self) -> 'dict[str, str]'` |

### FormulaExpression

| Field | Declared type |
| --- | --- |
| `dialect` | `str` |
| `text` | `str` |

| Public member | Signature or access |
| --- | --- |
| `byte_count` | `property (read-only)` |
| `from_wire` | `(payload: 'Mapping[str, Any]') -> 'FormulaExpression'` |
| `sha256` | `property (read-only)` |
| `to_wire` | `(self) -> 'dict[str, str]'` |

### FormulaMutation

| Field | Declared type |
| --- | --- |
| `affected_count` | `int` |
| `formula_observation` | `GridFormulaObservation \| FieldFormulaObservation` |
| `revision_after` | `str` |
| `revision_before` | `str \| None` |
| `target_kind` | `str` |

| Public member | Signature or access |
| --- | --- |
| `from_wire` | `(payload: 'Mapping[str, Any]') -> 'FormulaMutation'` |
| `to_wire` | `(self) -> 'dict[str, object]'` |

### FormulaRecordValue

| Field | Declared type |
| --- | --- |
| `record_id` | `str` |
| `value` | `FormulaValue` |

| Public member | Signature or access |
| --- | --- |
| `from_wire` | `(payload: 'Mapping[str, Any]') -> 'FormulaRecordValue'` |
| `to_wire` | `(self) -> 'dict[str, object]'` |

### FormulaResourceLimits

| Field | Declared type |
| --- | --- |
| `max_cells` | `int \| None` |
| `max_expression_bytes` | `int \| None` |
| `max_records` | `int \| None` |
| `max_response_bytes` | `int \| None` |
| `timeout_seconds` | `float \| None` |

### FormulaValue

| Field | Declared type |
| --- | --- |
| `kind` | `str` |
| `logical_type` | `str \| None` |
| `value` | `object` |

| Public member | Signature or access |
| --- | --- |
| `from_python` | `(value: 'object') -> 'FormulaValue'` |
| `from_wire` | `(payload: 'Mapping[str, Any]') -> 'FormulaValue'` |
| `logical` | `(logical_type: 'str', value: 'str \| int \| float') -> 'FormulaValue'` |
| `provider_error` | `(value: 'FormulaErrorValue') -> 'FormulaValue'` |
| `to_python` | `(self) -> 'object'` |
| `to_wire` | `(self) -> 'dict[str, object]'` |

### FormulaValueCell

| Field | Declared type |
| --- | --- |
| `address` | `str` |
| `value` | `FormulaValue` |

| Public member | Signature or access |
| --- | --- |
| `from_wire` | `(payload: 'Mapping[str, Any]') -> 'FormulaValueCell'` |
| `to_wire` | `(self) -> 'dict[str, object]'` |

### GridFormulaObservation

| Field | Declared type |
| --- | --- |
| `formulas` | `tuple[FormulaCell, ...]` |
| `observed_revision` | `str` |
| `requested_range` | `str` |
| `worksheet_id` | `str` |

| Public member | Signature or access |
| --- | --- |
| `from_wire` | `(payload: 'Mapping[str, Any]') -> 'GridFormulaObservation'` |
| `to_wire` | `(self) -> 'dict[str, object]'` |

### GridFormulaTarget

| Field | Declared type |
| --- | --- |
| `grid` | `TableURI \| str` |
| `worksheet` | `WorksheetRef` |

### GridFormulaValueObservation

| Field | Declared type |
| --- | --- |
| `calculation_state` | `CalculationState` |
| `calculation_trigger` | `CalculationTrigger` |
| `dependency_scope` | `str` |
| `observed_revision` | `str` |
| `requested_range` | `str` |
| `values` | `tuple[FormulaValueCell, ...]` |
| `worksheet_id` | `str` |

| Public member | Signature or access |
| --- | --- |
| `from_wire` | `(payload: 'Mapping[str, Any]') -> 'GridFormulaValueObservation'` |
| `to_wire` | `(self) -> 'dict[str, object]'` |

### GridFormulaView

| Public member | Signature or access |
| --- | --- |
| `read` | `(self, cell_range: 'str', *, limits: 'FormulaResourceLimits \| None' = None) -> 'OperationResult[GridFormulaObservation]'` |
| `read_values` | `(self, cell_range: 'str', *, limits: 'FormulaResourceLimits \| None' = None) -> 'OperationResult[GridFormulaValueObservation]'` |
| `recalculate` | `(self, *, scope: 'GridRecalculationScope', cell_range: 'str \| None' = None, expected_revision: 'str \| None' = None, idempotency_key: 'str \| None' = None, limits: 'FormulaResourceLimits \| None' = None) -> 'OperationResult[RecalculationObservation]'` |
| `set` | `(self, cell_range: 'str', expression: 'FormulaExpression \| str', *, dialect: 'str \| None' = None, expected_revision: 'str \| None' = None, idempotency_key: 'str \| None' = None, limits: 'FormulaResourceLimits \| None' = None) -> 'OperationResult[FormulaMutation]'` |

### GridRecalculationScope

| Member | Wire value |
| --- | --- |
| `RANGE` | `range` |
| `WORKSHEET` | `worksheet` |
| `WORKBOOK` | `workbook` |

### IdempotencyStrength

| Member | Wire value |
| --- | --- |
| `PROVIDER` | `provider` |
| `HOST_LEDGER` | `host_ledger` |
| `RECONCILED` | `reconciled` |

### LegacyConnectorAdapterBridge

| Public member | Signature or access |
| --- | --- |
| `begin_transaction` | `(self, binding: 'TableBinding') -> 'object'` |
| `bind_sheet_range` | `(self, source: 'SheetRangeSource') -> 'OperationResult[SheetRangeSource]'` |
| `capabilities_for` | `(self, binding: 'TableBinding') -> 'OperationResult[CapabilitySet]'` |
| `close` | `(self) -> 'None'` |
| `create_table` | `(self, source: 'object \| MaterializationRequest', destination: 'TableDestination \| None' = None) -> 'OperationResult[TableBinding]'` |
| `delete_rows` | `(self, binding: 'TableBinding', *, where, parameters: 'Mapping[str, Any] \| None' = None) -> 'OperationResult[int]'` |
| `drop_table` | `(self, binding: 'TableBinding') -> 'OperationResult[None]'` |
| `formula_extension_for` | `(self) -> 'FormulaConnectorExtension'` |
| `insert_rows` | `(self, binding: 'TableBinding', frame: 'pl.DataFrame') -> 'OperationResult[int]'` |
| `inspect_table` | `(self, binding: 'TableBinding') -> 'OperationResult[TableInspection]'` |
| `open_table` | `(self, address: 'object') -> 'OperationResult[TableBinding]'` |
| `read_sheet_range` | `(self, source: 'SheetRangeSource') -> 'OperationResult[ArrowTableCarrier]'` |
| `read_table` | `(self, binding: 'TableBinding', *, limit: 'int \| None' = None, continuation: 'str \| None' = None) -> 'OperationResult[ArrowTableCarrier]'` |
| `spreadsheet_provider` | `(self)` |
| `update_rows` | `(self, binding: 'TableBinding', frame: 'pl.DataFrame', *, keys: 'tuple[str, ...]') -> 'OperationResult[int]'` |

### ManagedSnapshot

| Field | Declared type |
| --- | --- |
| `committed_at` | `str` |
| `descriptor_hash` | `str` |
| `logical_target` | `TableURI` |
| `retention_expires_at` | `str \| None` |
| `snapshot_id` | `str` |
| `snapshot_reference` | `str` |
| `stage_id` | `str` |

### ManagedSnapshotState

| Field | Declared type |
| --- | --- |
| `schema` | `pa.Schema` |
| `snapshot` | `ManagedSnapshot` |

### ManagedStage

| Field | Declared type |
| --- | --- |
| `artifact_hash` | `str` |
| `descriptor_hash` | `str` |
| `idempotency_key` | `str` |
| `lease_expires_at` | `str \| None` |
| `logical_target` | `TableURI` |
| `physical_target` | `TableURI` |
| `stage_id` | `str` |
| `staged_at` | `str` |

### MaterializationRequest

| Field | Declared type |
| --- | --- |
| `destination` | `TableDestination` |
| `idempotency_key` | `str` |
| `profile` | `str` |
| `source` | `pl.DataFrame` |

| Public member | Signature or access |
| --- | --- |
| `content_fingerprint` | `property (read-only)` |
| `row_count` | `property (read-only)` |
| `schema_fingerprint` | `property (read-only)` |

### MutationAtomicity

| Member | Wire value |
| --- | --- |
| `ATOMIC` | `atomic` |
| `PARTIAL_REPORTED` | `partial_reported` |
| `UNKNOWN` | `unknown` |

### NativeSql

| Public member | Signature or access |
| --- | --- |
| `execute` | `(self, statement: 'str', *, parameters: 'Sequence[Any] \| None' = None, limits: 'NativeSqlResourceLimits \| None' = None, idempotency_key: 'str') -> 'OperationResult[int]'` |
| `query` | `(self, statement: 'str', *, parameters: 'Sequence[Any] \| None' = None, limits: 'NativeSqlResourceLimits \| None' = None) -> 'OperationResult[pl.DataFrame]'` |

### NativeSqlResourceLimits

| Field | Declared type |
| --- | --- |
| `max_bytes` | `int` |
| `max_duration_ms` | `int` |
| `max_rows` | `int` |

| Public member | Signature or access |
| --- | --- |
| `to_wire` | `(self) -> 'dict[str, int]'` |

### OTCError

### OperationCatalog

| Public member | Signature or access |
| --- | --- |
| `default` | `() -> 'OperationCatalog'` |
| `describe` | `(self, namespace: 'str \| None' = None, operation_id: 'str \| None' = None, version: 'str \| None' = None) -> 'tuple[OperationDescriptor, ...]'` |
| `get` | `(self, namespace: 'str', operation_id: 'str', version: 'str') -> 'OperationDescriptor \| None'` |
| `register` | `(self, descriptor: 'OperationDescriptor') -> 'None'` |

### OperationResult

| Field | Declared type |
| --- | --- |
| `commit` | `CommitState` |
| `continuation` | `str \| None` |
| `error` | `ErrorInfo \| None` |
| `outcome` | `Outcome` |
| `receipts` | `tuple[Receipt, ...]` |
| `value` | `T \| None` |
| `verification` | `VerificationState` |
| `warnings` | `tuple[OperationWarning, ...]` |

| Public member | Signature or access |
| --- | --- |
| `from_wire` | `(payload: 'Mapping[str, Any]', *, value_decoder: 'Callable[[Any], T] \| None' = None) -> 'OperationResult[T]'` |
| `require_value` | `(self) -> 'T'` |
| `to_wire` | `(self, value_encoder: 'Callable[[T], Any] \| None' = None) -> 'dict[str, Any]'` |
| `with_results` | `(self) -> 'OperationResult[T]'` |

### OperationWarning

| Field | Declared type |
| --- | --- |
| `code` | `str` |
| `message` | `str` |
| `safe_details` | `Mapping[str, Any]` |

| Public member | Signature or access |
| --- | --- |
| `from_wire` | `(payload: 'Mapping[str, Any]') -> 'OperationWarning'` |
| `to_wire` | `(self) -> 'dict[str, Any]'` |

### Outcome

| Member | Wire value |
| --- | --- |
| `SUCCEEDED` | `succeeded` |
| `PLANNED` | `planned` |
| `REJECTED` | `rejected` |
| `FAILED` | `failed` |
| `PARTIAL` | `partial` |
| `UNKNOWN` | `unknown` |

### PolarsPlanMapper

| Public member | Signature or access |
| --- | --- |
| `execute` | `(self, query: 'Query', frames: 'dict[str, pl.DataFrame]') -> 'pl.DataFrame'` |

### PortablePredicate

| Field | Declared type |
| --- | --- |
| `expression` | `str \| None` |
| `kind` | `PredicateKind` |
| `parameters` | `Mapping[str, Any]` |

| Public member | Signature or access |
| --- | --- |
| `from_wire` | `(payload: 'Mapping[str, Any]') -> 'PortablePredicate'` |
| `to_wire` | `(self) -> 'dict[str, Any]'` |

### PredicateKind

| Member | Wire value |
| --- | --- |
| `SQL` | `sql` |
| `ALL_ROWS` | `all_rows` |

### QualifiedTableName

| Field | Declared type |
| --- | --- |
| `catalog` | `str \| None` |
| `schema` | `str \| None` |
| `table` | `str` |

| Public member | Signature or access |
| --- | --- |
| `from_wire` | `(payload: 'Mapping[str, Any]') -> 'QualifiedTableName'` |
| `to_wire` | `(self) -> 'dict[str, str \| None]'` |

### Query

| Field | Declared type |
| --- | --- |
| `lane` | `QueryLane` |
| `limits` | `object` |
| `parameters` | `Mapping[str, Any]` |
| `sources` | `Mapping[str, object]` |
| `statement` | `str` |

| Public member | Signature or access |
| --- | --- |
| `definition_hash` | `property (read-only)` |
| `plan_hash` | `property (read-only)` |

### QueryLane

| Member | Wire value |
| --- | --- |
| `RELATIONAL` | `relational` |
| `TEMPORAL` | `temporal` |

### RecalculationObservation

| Field | Declared type |
| --- | --- |
| `calculation_state` | `CalculationState` |
| `effective_scope` | `str` |
| `provider_status` | `str` |
| `requested_scope` | `str` |
| `revision_after` | `str \| None` |
| `revision_before` | `str \| None` |
| `target_kind` | `str` |
| `value_observation` | `GridFormulaValueObservation \| FieldFormulaValueObservation \| None` |
| `verification` | `str` |

| Public member | Signature or access |
| --- | --- |
| `from_wire` | `(payload: 'Mapping[str, Any]') -> 'RecalculationObservation'` |
| `to_wire` | `(self) -> 'dict[str, object]'` |

### Receipt

| Field | Declared type |
| --- | --- |
| `capability` | `str \| None` |
| `connector_id` | `str \| None` |
| `details` | `Mapping[str, Any]` |
| `kind` | `str` |
| `mode` | `TableMode \| None` |
| `operation` | `str` |
| `safe_target` | `TableURI \| None` |

| Public member | Signature or access |
| --- | --- |
| `from_wire` | `(payload: 'Mapping[str, Any]') -> 'Receipt'` |
| `to_wire` | `(self) -> 'dict[str, Any]'` |

### ReconciliationReference

| Field | Declared type |
| --- | --- |
| `connector_id` | `str \| None` |
| `expires_at` | `str \| None` |
| `idempotency_key` | `str \| None` |
| `operation_id` | `str` |

| Public member | Signature or access |
| --- | --- |
| `from_wire` | `(payload: 'Mapping[str, Any]') -> 'ReconciliationReference'` |
| `to_wire` | `(self) -> 'dict[str, str \| None]'` |

### RevisionEnforcement

| Member | Wire value |
| --- | --- |
| `ATOMIC` | `atomic` |
| `CHECKED` | `checked` |
| `UNAVAILABLE` | `unavailable` |

### SchemaPolicy

| Member | Wire value |
| --- | --- |
| `VALIDATE_DECLARED` | `validate_declared` |
| `INFER_COMPLETE` | `infer_complete` |

### SheetModeDestination

| Field | Declared type |
| --- | --- |
| `anchor` | `str` |
| `grid` | `TableURI \| str` |
| `header` | `bool` |
| `worksheet` | `str \| None` |

| Public member | Signature or access |
| --- | --- |
| `from_wire` | `(payload: 'Mapping[str, Any]') -> 'SheetModeDestination'` |
| `to_wire` | `(self) -> 'dict[str, Any]'` |

### SheetModeTableAddress

| Field | Declared type |
| --- | --- |
| `grid` | `TableURI \| str` |
| `table_id` | `str` |

| Public member | Signature or access |
| --- | --- |
| `from_wire` | `(payload: 'Mapping[str, Any]') -> 'SheetModeTableAddress'` |
| `to_wire` | `(self) -> 'dict[str, Any]'` |

### SheetRangeSource

| Field | Declared type |
| --- | --- |
| `cell_range` | `str` |
| `grid` | `TableURI \| str` |
| `header` | `bool` |
| `observed_revision` | `str \| None` |
| `schema` | `pl.Schema \| None` |
| `schema_policy` | `SchemaPolicy` |

| Public member | Signature or access |
| --- | --- |
| `from_wire` | `(payload: 'Mapping[str, Any]') -> 'SheetRangeSource'` |
| `to_wire` | `(self) -> 'dict[str, Any]'` |

### SqlResourceLimits

| Field | Declared type |
| --- | --- |
| `max_duration_ms` | `int` |
| `max_intermediate_bytes` | `int` |
| `max_intermediate_rows` | `int` |
| `max_output_bytes` | `int` |
| `max_output_rows` | `int` |
| `max_source_bytes` | `int` |
| `max_source_rows` | `int` |
| `max_total_input_bytes` | `int` |
| `max_total_input_rows` | `int` |

| Public member | Signature or access |
| --- | --- |
| `to_wire` | `(self) -> 'dict[str, int]'` |

### Table

| Public member | Signature or access |
| --- | --- |
| `address` | `property (read-only)` |
| `capabilities` | `(self)` |
| `connector_id` | `property (read-only)` |
| `delete` | `(self, *, where, parameters: 'Mapping[str, Any] \| None' = None)` |
| `drop` | `(self)` |
| `insert` | `(self, frame: 'pl.DataFrame')` |
| `inspect` | `(self)` |
| `layout` | `(self)` |
| `mode` | `property (read-only)` |
| `observed_revision` | `property (read-only)` |
| `read` | `(self)` |
| `read_page` | `(self, *, limit: 'int', continuation: 'str \| None' = None)` |
| `schema` | `property (read-only)` |
| `time_series` | `(self, descriptor: 'TemporalTableDescriptor')` |
| `transaction` | `(self, *, idempotency_key: 'str \| None' = None) -> 'TableTransaction'` |
| `update` | `(self, frame: 'pl.DataFrame', *, keys: 'tuple[str, ...]')` |
| `uri` | `property (read-only)` |

### TableBinding

| Field | Declared type |
| --- | --- |
| `address` | `ExistingTableAddress \| None` |
| `connector_id` | `str` |
| `content_fingerprint` | `str \| None` |
| `layout_binding` | `Mapping[str, Any] \| None` |
| `mode` | `TableMode` |
| `observed_revision` | `str \| None` |
| `profile` | `str \| None` |
| `row_count` | `int \| None` |
| `schema` | `pl.Schema \| None` |
| `schema_fingerprint` | `str \| None` |
| `schema_observed` | `bool` |
| `uri` | `TableURI` |

### TableConnector

| Field | Declared type |
| --- | --- |
| `capabilities` | `tuple[object, ...]` |
| `handles_paths` | `bool` |
| `hosts` | `tuple[str, ...]` |
| `identity` | `object` |
| `local` | `bool` |
| `materialization` | `tuple[MaterializationCapability, ...]` |
| `modes` | `tuple[TableMode, ...]` |
| `schemes` | `tuple[str, ...]` |

| Public member | Signature or access |
| --- | --- |
| `begin_transaction` | `(self, binding: 'TableBinding') -> 'object'` |
| `capabilities_for` | `(self, binding: 'TableBinding') -> 'OperationResult[CapabilitySet]'` |
| `close` | `(self) -> 'None'` |
| `create_table` | `(self, source: 'object \| MaterializationRequest', destination: 'TableDestination \| None' = None) -> 'OperationResult[TableBinding]'` |
| `delete_rows` | `(self, binding: 'TableBinding', *, where, parameters: 'Mapping[str, Any] \| None' = None) -> 'OperationResult[int]'` |
| `drop_table` | `(self, binding: 'TableBinding') -> 'OperationResult[None]'` |
| `insert_rows` | `(self, binding: 'TableBinding', frame: 'pl.DataFrame') -> 'OperationResult[int]'` |
| `inspect_table` | `(self, binding: 'TableBinding') -> 'OperationResult[TableInspection]'` |
| `open_table` | `(self, address: 'object') -> 'OperationResult[TableBinding]'` |
| `read_table` | `(self, binding: 'TableBinding', *, limit: 'int \| None' = None, continuation: 'str \| None' = None) -> 'OperationResult[ArrowTableCarrier]'` |
| `update_rows` | `(self, binding: 'TableBinding', frame: 'pl.DataFrame', *, keys: 'tuple[str, ...]') -> 'OperationResult[int]'` |

### TableInspection

| Field | Declared type |
| --- | --- |
| `facts` | `Mapping[str, Any]` |
| `mode` | `TableMode` |
| `observed_revision` | `str \| None` |
| `row_count` | `int \| None` |
| `schema` | `pl.Schema` |
| `uri` | `TableURI` |

### TableLayoutSession

| Public member | Signature or access |
| --- | --- |
| `capabilities` | `property (read-only)` |
| `close` | `(self)` |
| `config` | `(self, **kwargs)` |
| `range` | `(self, address: 'str')` |
| `read_config` | `(self, *, rows: 'Sequence[int]', columns: 'Sequence[str]', view_fields=None)` |
| `verify` | `(self, expected=None)` |
| `worksheet` | `property (read-only)` |
| `write` | `(self, **kwargs)` |

### TableMode

| Member | Wire value |
| --- | --- |
| `BASE_MODE` | `base-mode` |
| `SHEET_MODE` | `sheet-mode` |

### TableTransaction

| Public member | Signature or access |
| --- | --- |
| `abort` | `(self)` |
| `commit` | `(self)` |
| `delete` | `(self, *, where, parameters: 'Mapping[str, Any] \| None' = None)` |
| `insert` | `(self, frame: 'pl.DataFrame')` |
| `update` | `(self, frame: 'pl.DataFrame', *, keys: 'tuple[str, ...]')` |

### TemporalConnectorExtension

| Public member | Signature or access |
| --- | --- |
| `abort_stage` | `(self, binding: 'TableBinding', descriptor: 'TemporalTableDescriptor', stage: 'ManagedStage') -> 'ManagedAbortReceipt'` |
| `append_rows` | `(self, binding: 'TableBinding', descriptor: 'TemporalTableDescriptor', frame: 'pl.DataFrame', *, idempotency_key: 'str') -> 'OperationResult[int]'` |
| `commit_stage` | `(self, binding: 'TableBinding', descriptor: 'TemporalTableDescriptor', stage: 'ManagedStage') -> 'ManagedCommitReceipt'` |
| `current_snapshot` | `(self, binding: 'TableBinding', descriptor: 'TemporalTableDescriptor') -> 'ManagedCurrentResult \| None'` |
| `descriptor_hash_for` | `(self, binding: 'TableBinding', descriptor: 'TemporalTableDescriptor') -> 'str'` |
| `executor_for` | `(self, binding: 'TableBinding', descriptor: 'TemporalTableDescriptor') -> 'object'` |
| `readback_snapshot` | `(self, binding: 'TableBinding', descriptor: 'TemporalTableDescriptor', snapshot: 'ManagedSnapshot') -> 'ManagedReadbackResult'` |
| `stage_rows` | `(self, binding: 'TableBinding', descriptor: 'TemporalTableDescriptor', frame: 'pl.DataFrame', *, idempotency_key: 'str') -> 'ManagedStageReceipt'` |
| `upsert_rows` | `(self, binding: 'TableBinding', descriptor: 'TemporalTableDescriptor', frame: 'pl.DataFrame', *, idempotency_key: 'str') -> 'OperationResult[int]'` |

### TemporalResourceLimits

| Field | Declared type |
| --- | --- |
| `max_bytes` | `int` |
| `max_duration_ms` | `int` |
| `max_rows` | `int` |

| Public member | Signature or access |
| --- | --- |
| `to_bounds` | `(self) -> 'ResourceBounds'` |

### TemporalTableDescriptor

| Field | Declared type |
| --- | --- |
| `duplicate_policy` | `DuplicatePolicy` |
| `ingestion_time_field` | `str \| None` |
| `ordering` | `TemporalOrdering` |
| `precision` | `TimestampPrecision` |
| `series_key_fields` | `tuple[str, ...]` |
| `tag_fields` | `tuple[str, ...]` |
| `time_field` | `str` |
| `timezone` | `str` |
| `value_fields` | `tuple[str, ...]` |

| Public member | Signature or access |
| --- | --- |
| `declared_fields` | `property (read-only)` |
| `to_wire` | `(self) -> 'dict[str, object]'` |

### TimeSeriesView

| Public member | Signature or access |
| --- | --- |
| `aggregate` | `(self, start: 'str', end: 'str', *, bucket: 'FixedBucket \| CalendarBucket', group_by: 'tuple[str, ...]' = (), measures: 'tuple[AggregateMeasure, ...]', tag_predicates: 'tuple[TagPredicate, ...]' = (), snapshot_reference: 'str \| None' = None, limits: 'TemporalResourceLimits \| None' = None) -> 'Query'` |
| `append` | `(self, frame: 'pl.DataFrame', *, idempotency_key: 'str') -> 'OperationResult[int]'` |
| `as_of` | `(self, at: 'str', *, columns: 'tuple[str, ...] \| None' = None, tag_predicates: 'tuple[TagPredicate, ...]' = (), snapshot_reference: 'str \| None' = None, limits: 'TemporalResourceLimits \| None' = None) -> 'Query'` |
| `gap_fill` | `(self, start: 'str', end: 'str', *, bucket: 'FixedBucket \| CalendarBucket', group_by: 'tuple[str, ...]' = (), measures: 'tuple[AggregateMeasure, ...]', fills: 'tuple[FillRule, ...]', tag_predicates: 'tuple[TagPredicate, ...]' = (), snapshot_reference: 'str \| None' = None, limits: 'TemporalResourceLimits \| None' = None) -> 'Query'` |
| `latest` | `(self, *, at_or_before: 'str \| None' = None, columns: 'tuple[str, ...] \| None' = None, tag_predicates: 'tuple[TagPredicate, ...]' = (), snapshot_reference: 'str \| None' = None, limits: 'TemporalResourceLimits \| None' = None) -> 'Query'` |
| `scan_range` | `(self, start: 'str', end: 'str', *, columns: 'tuple[str, ...] \| None' = None, tag_predicates: 'tuple[TagPredicate, ...]' = (), snapshot_reference: 'str \| None' = None, limits: 'TemporalResourceLimits \| None' = None) -> 'Query'` |
| `sql` | `(self, statement: 'str', *, parameters: 'Mapping[str \| int, Any]', snapshot_reference: 'str \| None' = None, limits: 'TemporalResourceLimits \| None' = None) -> 'Query'` |
| `upsert` | `(self, frame: 'pl.DataFrame', *, idempotency_key: 'str') -> 'OperationResult[int]'` |

### VerificationState

| Member | Wire value |
| --- | --- |
| `NOT_APPLICABLE` | `not_applicable` |
| `PASSED` | `passed` |
| `FAILED` | `failed` |
| `SKIPPED` | `skipped` |
| `UNAVAILABLE` | `unavailable` |

### WorkbookAccess

| Public member | Signature or access |
| --- | --- |
| `copy` | `(self, source: 'str \| TableURI', *, to: 'str \| TableURI \| None' = None, title: 'str \| None' = None, limits: 'Any' = None)` |
| `create` | `(self, uri: 'str \| TableURI', *, profile: 'str \| None' = None, limits: 'Any' = None, failure_directory: 'Any' = None)` |
| `open` | `(self, uri: 'str \| TableURI', *, limits: 'Any' = None, profile: 'str' = 'general/1.0')` |

### WorksheetRef

| Field | Declared type |
| --- | --- |
| `name` | `str \| None` |
| `worksheet_id` | `str \| None` |

## open_table_connector.contract

| Name | Kind | Definition |
| --- | --- | --- |
| `AdapterEndpoint` | class | `(raw: 'str', uri: 'TableURI \| None' = None, path: 'Path \| None' = None, is_stdio: 'bool' = False) -> None` [source](../../packages/contract/src/open_table_connector/contract/adapters.py) |
| `AdapterFormat` | enum | `(value, names=None, *, module=None, qualname=None, type=None, start=1, boundary=None)` [source](../../packages/contract/src/open_table_connector/contract/adapters.py) |
| `AdapterOptions` | class | `(from_format: 'AdapterFormat' = <AdapterFormat.AUTO: 'auto'>, output_format: 'AdapterFormat' = <AdapterFormat.AUTO: 'auto'>, to_format: 'AdapterFormat' = <AdapterFormat.AUTO: 'auto'>, limit: 'int \| None' = None, timeout: 'float \| int \| None' = None, sheet: 'str \| None' = None, range: 'str \| None' = None, field_names: 'tuple[str, ...]' = (), if_exists: 'str' = 'error', target: 'str \| None' = None) -> None` [source](../../packages/contract/src/open_table_connector/contract/adapters.py) |
| `ArrowReadResult` | class | `(table: 'pa.Table', receipt: 'NeutralReceipt') -> None` [source](../../packages/contract/src/open_table_connector/contract/read.py) |
| `ArrowTableReader` | class | `(*args, **kwargs)` [source](../../packages/contract/src/open_table_connector/contract/read.py) |
| `BOUNDED_ARROW_TABLE_READ_CAPABILITY` | constant | `CapabilityIdentity(capability_id='table.read.arrow.bounded', capability_version='2.0')`  |
| `BaseConvention` | class | `(record_id_field: 'str \| None' = None, key_fields: 'tuple[str, ...]' = (), ordinal_snapshot_id: 'str \| None' = None) -> None` [source](../../packages/contract/src/open_table_connector/contract/coordinates.py) |
| `BaseCoordinate` | class | `(record_id: 'str \| None' = None, key: 'Mapping[str, Scalar]' = <factory>, ordinal: 'int \| None' = None, snapshot_id: 'str \| None' = None) -> None` [source](../../packages/contract/src/open_table_connector/contract/coordinates.py) |
| `BaseTableBindingAdapter` | class | `(*args, **kwargs)` [source](../../packages/contract/src/open_table_connector/contract/adapters.py) |
| `BoundedArrowTableReadResult` | class | `(table: 'pa.Table', receipt: 'BoundedReadReceipt') -> None` [source](../../packages/contract/src/open_table_connector/contract/bounded_reads.py) |
| `BoundedArrowTableReader` | class | `(*args, **kwargs)` [source](../../packages/contract/src/open_table_connector/contract/bounded_reads.py) |
| `BoundedReadReceipt` | class | `(connector: 'ConnectorIdentity', safe_uri: 'TableURI', mode: 'TableMode', source_snapshot_reference: 'str \| None', schema_fingerprint: 'str', emitted_content_fingerprint: 'str', coordinate_convention: 'BaseConvention', rows_emitted: 'int', batches_emitted: 'int', extent: 'ReadExtent', next_token: 'str \| None' = None, operation_id: 'str' = 'bounded-read', schema_version: 'str' = 'otc.bounded-read-receipt/v2') -> None` [source](../../packages/contract/src/open_table_connector/contract/bounded_reads.py) |
| `BoundedTableReadRequest` | class | `(uri: 'TableURI', resource_limits: 'ResourceLimits' = <factory>, max_output_rows: 'int' = 1) -> None` [source](../../packages/contract/src/open_table_connector/contract/bounded_reads.py) |
| `CAPABILITY_TABLE_MATERIALIZE_CREATE` | constant | `'table.materialize.create'`  |
| `CAPABILITY_TABLE_READ_ARROW` | constant | `'table.read.arrow'`  |
| `CAPABILITY_TABLE_WRITE` | constant | `'table.write'`  |
| `CLI_CONFIG_DIRECTORY` | constant | `'open-table-connector'`  |
| `CLI_CONFIG_ENV` | constant | `'OTC_CONFIG'`  |
| `CLI_CONFIG_FILENAME` | constant | `'config.toml'`  |
| `CLI_CONFIG_SCHEMA_VERSION` | constant | `'otc.cli-config/v1'`  |
| `CLI_PLUGIN_GROUP` | constant | `'open_table_connector.cli_adapters'`  |
| `CREDENTIAL_ACCESS_TOKEN` | constant | `'access_token'`  |
| `CREDENTIAL_TENANT_ACCESS_TOKEN` | constant | `'tenant_access_token'`  |
| `CapabilityIdentity` | class | `(capability_id: 'str', capability_version: 'str') -> None` [source](../../packages/contract/src/open_table_connector/contract/identity.py) |
| `CapabilityManifest` | class | `(connector: 'ConnectorIdentity', capabilities: 'tuple[CapabilityIdentity, ...]', modes: 'tuple[TableMode, ...]', uri_schemes: 'tuple[str, ...]', materialization: 'tuple[MaterializationCapability, ...]' = ()) -> None` [source](../../packages/contract/src/open_table_connector/contract/capabilities.py) |
| `CapabilityObservation` | class | `(target: 'TargetSelector', provider: 'str', provider_version: 'str \| None', resolution: 'str', operations: 'tuple[OperationDescriptor, ...]') -> None` [source](../../packages/contract/src/open_table_connector/contract/operations.py) |
| `ConfigScalar` | constant | `str \| int \| float \| bool`  |
| `ConfigValue` | constant | `str \| int \| float \| bool \| tuple[str \| int \| float \| bool, ...]`  |
| `ConnectorAdapter` | class | `(*args, **kwargs)` [source](../../packages/contract/src/open_table_connector/contract/adapters.py) |
| `ConnectorError` | class | `(code: 'ConnectorErrorCode', message: 'str', safe_details: 'Mapping[str, Any]' = <factory>) -> None` [source](../../packages/contract/src/open_table_connector/contract/errors.py) |
| `ConnectorErrorCode` | enum | `(value, names=None, *, module=None, qualname=None, type=None, start=1, boundary=None)` [source](../../packages/contract/src/open_table_connector/contract/errors.py) |
| `ConnectorIdentity` | class | `(connector_id: 'str', connector_version: 'str', contract_version: 'str') -> None` [source](../../packages/contract/src/open_table_connector/contract/identity.py) |
| `ExecutionOptions` | class | `(dry_run: 'bool' = False, allow_partial: 'bool' = False, expected_revision: 'str \| None' = None, idempotency_key: 'str \| None' = None, failure_directory: 'str \| None' = None) -> None` [source](../../packages/contract/src/open_table_connector/contract/operations.py) |
| `ExecutionRequest` | class | `(uri: 'TableURI', statement: 'str', parameters: 'tuple[Any, ...]' = (), resource_limits: 'ResourceLimits' = <factory>) -> None` [source](../../packages/contract/src/open_table_connector/contract/execution.py) |
| `ExecutionResult` | class | `(operation_id: 'str', status: 'str', affected_rows: 'int \| None', receipt: 'NeutralReceipt \| None' = None, artifacts: 'Mapping[str, str]' = <factory>) -> None` [source](../../packages/contract/src/open_table_connector/contract/execution.py) |
| `FORMAT_AUTO` | constant | `'auto'`  |
| `FORMAT_TABLE` | constant | `'table'`  |
| `HOST_GOOGLE_DOCS` | constant | `'docs.google.com'`  |
| `HOST_MAYBE` | constant | `'www.maybe.ai'`  |
| `IF_EXISTS_APPEND` | constant | `'append'`  |
| `IF_EXISTS_ERROR` | constant | `'error'`  |
| `IF_EXISTS_REPLACE` | constant | `'replace'`  |
| `InspectRequest` | class | `(uri: 'TableURI', resource_limits: 'ResourceLimits' = <factory>) -> None` [source](../../packages/contract/src/open_table_connector/contract/inspect.py) |
| `MaterializationCapability` | class | `(capability: 'CapabilityIdentity', profiles: 'tuple[str, ...]', modes: 'tuple[TableMode, ...]') -> None` [source](../../packages/contract/src/open_table_connector/contract/capabilities.py) |
| `NeutralReceipt` | class | `(connector: 'ConnectorIdentity', capability: 'CapabilityIdentity', operation_id: 'str', safe_uri: 'TableURI', mode: 'TableMode', source_revision: 'str', schema_fingerprint: 'str', content_fingerprint: 'str', coordinate_convention: 'BaseConvention \| SheetConvention', row_count: 'int \| None', batch_count: 'int \| None', vendor_receipt_ref: 'str \| None' = None) -> None` [source](../../packages/contract/src/open_table_connector/contract/receipts.py) |
| `OPERATION_CATALOG_GROUP` | constant | `'open_table_connector.operation_catalogs.v1'`  |
| `OPERATION_HANDLER_GROUP` | constant | `'open_table_connector.operation_handlers.v1'`  |
| `OPTION_LIVE_MATERIALIZATION_EVIDENCE` | constant | `'live_materialization_evidence'`  |
| `OPTION_TIMEOUT_SECONDS` | constant | `'timeout_seconds'`  |
| `OperationDescriptor` | class | `(schema: 'str', operation_id: 'str', version: 'str', target_kind: 'str', arguments_schema: 'Mapping[str, Any]', capability: 'str', effects: 'tuple[str, ...]', limits: 'Mapping[str, Any]' = <factory>, examples: 'tuple[Mapping[str, Any], ...]' = (), result_schema: 'Mapping[str, Any]' = <factory>) -> None` [source](../../packages/contract/src/open_table_connector/contract/operations.py) |
| `OperationRequest` | class | `(namespace: 'str', operation_id: 'str', version: 'str', target: 'TargetSelector \| None', arguments: 'Mapping[str, Any]') -> None` [source](../../packages/contract/src/open_table_connector/contract/operations.py) |
| `PACKAGE_NAMESPACE` | constant | `'open_table_connector'`  |
| `PORTABLE_TABLE_PROFILE_V1` | constant | `'otc.portable-table/v1'`  |
| `PROCESS_PLUGIN_GROUP` | constant | `'open_table_connector.process_handlers'`  |
| `PROVIDER_CSV` | constant | `'csv'`  |
| `PROVIDER_DBT` | constant | `'dbt'`  |
| `PROVIDER_EXCEL` | constant | `'excel'`  |
| `PROVIDER_FEISHU_BITABLE` | constant | `'feishu_bitable'`  |
| `PROVIDER_GOOGLE_SHEETS` | constant | `'google_sheets'`  |
| `PROVIDER_IDS` | constant | `('csv', 'json', 'jsonl', 'excel', 'local_files', 'sqlite', 'postgres', 'google_sheets', 'feishu_bitable', 'maybe_sheet', 'dbt', 'md')`  |
| `PROVIDER_JSON` | constant | `'json'`  |
| `PROVIDER_JSONL` | constant | `'jsonl'`  |
| `PROVIDER_LOCAL_FILES` | constant | `'local_files'`  |
| `PROVIDER_MAYBE_SHEET` | constant | `'maybe_sheet'`  |
| `PROVIDER_PLUGIN_GROUP` | constant | `'open_table_connector.providers'`  |
| `PROVIDER_POSTGRES` | constant | `'postgres'`  |
| `PROVIDER_SQLITE` | constant | `'sqlite'`  |
| `PluginDescriptor` | class | `(name: 'str', identity: 'ConnectorIdentity', schemes: 'tuple[str, ...]', factory: 'PluginFactory', hosts: 'tuple[str, ...]' = (), capabilities: 'tuple[CapabilityIdentity, ...]' = (), modes: 'tuple[TableMode, ...]' = (), materialization: 'tuple[MaterializationCapability, ...]' = (), local: 'bool' = False, handles_paths: 'bool' = False, runtime_metadata: 'bool' = False) -> None` [source](../../packages/contract/src/open_table_connector/contract/plugins.py) |
| `PluginFactory` | constant | `collections.abc.Callable[..., typing.Any]`  |
| `PolarsReadResult` | class | `(frame: 'pl.DataFrame', receipt: 'NeutralReceipt') -> None` [source](../../packages/contract/src/open_table_connector/contract/read.py) |
| `PolarsTableReader` | class | `(*args, **kwargs)` [source](../../packages/contract/src/open_table_connector/contract/read.py) |
| `PreparedOperation` | class | `(operation_id: 'str', statement: 'str', parameters: 'tuple[Any, ...]' = (), target: 'TableURI \| None' = None, resource_limits: 'ResourceLimits' = <factory>) -> None` [source](../../packages/contract/src/open_table_connector/contract/execution.py) |
| `ProviderConfig` | class | `(provider_id: 'str', enabled: 'bool' = True, credential_reference: 'str \| None' = None, environment: 'Mapping[str, str]' = <factory>, options: 'Mapping[str, ConfigValue]' = <factory>) -> None` [source](../../packages/contract/src/open_table_connector/contract/adapters.py) |
| `ProviderFactoryContext` | class | `(config: 'ProviderConfig', environment: 'Mapping[str, str]' = <factory>, credentials: 'Mapping[str, str]' = <factory>, transports: 'Mapping[str, Any]' = <factory>) -> None` [source](../../packages/contract/src/open_table_connector/contract/adapters.py) |
| `ReadExtent` | enum | `(value, names=None, *, module=None, qualname=None, type=None, start=1, boundary=None)` [source](../../packages/contract/src/open_table_connector/contract/bounded_reads.py) |
| `ResolveContext` | class | `(resource_limits: 'ResourceLimits' = <factory>, credentials: 'Any' = None) -> None` [source](../../packages/contract/src/open_table_connector/contract/resolve.py) |
| `ResolvedTable` | class | `(uri: 'TableURI', mode: 'TableMode', resource: 'Any') -> None` [source](../../packages/contract/src/open_table_connector/contract/resolve.py) |
| `ResourceLimits` | class | `(max_rows: 'int \| None' = None, max_bytes: 'int \| None' = None, timeout_seconds: 'int \| None' = None) -> None` [source](../../packages/contract/src/open_table_connector/contract/resolve.py) |
| `SCHEME_FEISHU` | constant | `'feishu'`  |
| `SCHEME_FILE` | constant | `'file'`  |
| `SCHEME_GSHEETS` | constant | `'gsheets'`  |
| `SCHEME_HTTPS` | constant | `'https'`  |
| `SCHEME_MANAGED_XLSX` | constant | `'managed+xlsx'`  |
| `SCHEME_MD` | constant | `'md'`  |
| `SCHEME_POSTGRESQL` | constant | `'postgresql'`  |
| `SCHEME_XLSX` | constant | `'xlsx'`  |
| `SETTING_BINARY` | constant | `'binary'`  |
| `SETTING_ENDPOINT` | constant | `'endpoint'`  |
| `Scalar` | constant | `str \| int \| float \| bool \| decimal.Decimal \| datetime.date \| datetime.datetime`  |
| `SheetConvention` | class | `(sheet: 'str \| int', header_rows: 'int' = 1, first_data_row: 'int' = 2) -> None` [source](../../packages/contract/src/open_table_connector/contract/coordinates.py) |
| `SheetCoordinate` | class | `(sheet: 'str \| int', row: 'int', column: 'str \| int \| None' = None) -> None` [source](../../packages/contract/src/open_table_connector/contract/coordinates.py) |
| `SqlExecutor` | class | `(*args, **kwargs)` [source](../../packages/contract/src/open_table_connector/contract/execution.py) |
| `StepExecutor` | class | `(*args, **kwargs)` [source](../../packages/contract/src/open_table_connector/contract/execution.py) |
| `TableCoordinate` | constant | `open_table_connector.contract.coordinates.BaseCoordinate \| open_table_connector.contract.coordinates.SheetCoordinate`  |
| `TableInspection` | class | `(safe_uri: 'TableURI', mode: 'TableMode', columns: 'tuple[str, ...]', schema_fingerprint: 'str', row_count: 'int \| None', coordinate_convention: 'BaseConvention \| SheetConvention', facts: 'Mapping[str, Any]' = <factory>) -> None` [source](../../packages/contract/src/open_table_connector/contract/inspect.py) |
| `TableInspector` | class | `(*args, **kwargs)` [source](../../packages/contract/src/open_table_connector/contract/inspect.py) |
| `TableMode` | enum | `(value, names=None, *, module=None, qualname=None, type=None, start=1, boundary=None)` [source](../../packages/contract/src/open_table_connector/contract/capabilities.py) |
| `TableReadRequest` | class | `(uri: 'TableURI', resource_limits: 'ResourceLimits' = <factory>) -> None` [source](../../packages/contract/src/open_table_connector/contract/read.py) |
| `TableURI` | class | `(value: 'str') -> None` [source](../../packages/contract/src/open_table_connector/contract/uri.py) |
| `TableWriteRequest` | class | `(uri: 'TableURI', frame: 'pl.DataFrame', if_exists: 'str' = 'error', table: 'str \| None' = None) -> None` [source](../../packages/contract/src/open_table_connector/contract/storage.py) |
| `TableWriteResult` | class | `(receipt: 'NeutralReceipt', affected_rows: 'int') -> None` [source](../../packages/contract/src/open_table_connector/contract/storage.py) |
| `TableWriter` | class | `(*args, **kwargs)` [source](../../packages/contract/src/open_table_connector/contract/storage.py) |
| `TargetSelector` | class | `(uri: 'str', sheet: 'str \| None' = None, object_id: 'str \| None' = None) -> None` [source](../../packages/contract/src/open_table_connector/contract/operations.py) |
| `TransactionalStore` | class | `(*args, **kwargs)` [source](../../packages/contract/src/open_table_connector/contract/storage.py) |
| `URIResolver` | class | `(*args, **kwargs)` [source](../../packages/contract/src/open_table_connector/contract/resolve.py) |
| `WritePreflightAdapter` | class | `(*args, **kwargs)` [source](../../packages/contract/src/open_table_connector/contract/adapters.py) |
| `XDG_CONFIG_HOME_ENV` | constant | `'XDG_CONFIG_HOME'`  |
| `parse_adapter_endpoint` | function | `(value: 'str') -> 'AdapterEndpoint'` [source](../../packages/contract/src/open_table_connector/contract/adapters.py) |
| `parse_adapter_format` | function | `(value: 'str \| None') -> 'AdapterFormat'` [source](../../packages/contract/src/open_table_connector/contract/adapters.py) |

### AdapterEndpoint

| Field | Declared type |
| --- | --- |
| `is_stdio` | `bool` |
| `path` | `Path \| None` |
| `raw` | `str` |
| `uri` | `TableURI \| None` |

### AdapterFormat

| Member | Wire value |
| --- | --- |
| `AUTO` | `auto` |
| `CSV` | `csv` |
| `EXCEL` | `excel` |
| `JSON` | `json` |
| `JSONL` | `jsonl` |
| `TABLE` | `table` |

### AdapterOptions

| Field | Declared type |
| --- | --- |
| `field_names` | `tuple[str, ...]` |
| `from_format` | `AdapterFormat` |
| `if_exists` | `str` |
| `limit` | `int \| None` |
| `output_format` | `AdapterFormat` |
| `range` | `str \| None` |
| `sheet` | `str \| None` |
| `target` | `str \| None` |
| `timeout` | `float \| int \| None` |
| `to_format` | `AdapterFormat` |

### ArrowReadResult

| Field | Declared type |
| --- | --- |
| `receipt` | `NeutralReceipt` |
| `table` | `pa.Table` |

### ArrowTableReader

| Public member | Signature or access |
| --- | --- |
| `read_arrow` | `(self, request: 'TableReadRequest') -> 'ArrowReadResult'` |

### BaseConvention

| Field | Declared type |
| --- | --- |
| `key_fields` | `tuple[str, ...]` |
| `ordinal_snapshot_id` | `str \| None` |
| `record_id_field` | `str \| None` |

| Public member | Signature or access |
| --- | --- |
| `mode` | `property (read-only)` |

### BaseCoordinate

| Field | Declared type |
| --- | --- |
| `key` | `Mapping[str, Scalar]` |
| `ordinal` | `int \| None` |
| `record_id` | `str \| None` |
| `snapshot_id` | `str \| None` |

| Public member | Signature or access |
| --- | --- |
| `from_wire` | `(payload: 'Mapping[str, Any]') -> "'BaseCoordinate'"` |
| `identity_kind` | `property (read-only)` |
| `to_wire` | `(self) -> 'dict[str, Any]'` |

### BaseTableBindingAdapter

| Public member | Signature or access |
| --- | --- |
| `bind_base_table` | `(self, endpoint: 'AdapterEndpoint', table_id: 'str') -> 'AdapterEndpoint'` |

### BoundedArrowTableReadResult

| Field | Declared type |
| --- | --- |
| `receipt` | `BoundedReadReceipt` |
| `table` | `pa.Table` |

### BoundedArrowTableReader

| Public member | Signature or access |
| --- | --- |
| `read_arrow_bounded` | `(self, request: 'BoundedTableReadRequest') -> 'BoundedArrowTableReadResult'` |

### BoundedReadReceipt

| Field | Declared type |
| --- | --- |
| `batches_emitted` | `int` |
| `connector` | `ConnectorIdentity` |
| `coordinate_convention` | `BaseConvention` |
| `emitted_content_fingerprint` | `str` |
| `extent` | `ReadExtent` |
| `mode` | `TableMode` |
| `next_token` | `str \| None` |
| `operation_id` | `str` |
| `rows_emitted` | `int` |
| `safe_uri` | `TableURI` |
| `schema_fingerprint` | `str` |
| `schema_version` | `str` |
| `source_snapshot_reference` | `str \| None` |

| Public member | Signature or access |
| --- | --- |
| `to_wire` | `(self) -> 'dict[str, Any]'` |

### BoundedTableReadRequest

| Field | Declared type |
| --- | --- |
| `max_output_rows` | `int` |
| `resource_limits` | `ResourceLimits` |
| `uri` | `TableURI` |

### CapabilityIdentity

| Field | Declared type |
| --- | --- |
| `capability_id` | `str` |
| `capability_version` | `str` |

| Public member | Signature or access |
| --- | --- |
| `from_wire` | `(payload: 'Mapping[str, Any]') -> 'CapabilityIdentity'` |
| `parse` | `(value: 'str') -> 'CapabilityIdentity'` |
| `to_reference` | `(self) -> 'str'` |
| `to_wire` | `(self) -> 'dict[str, str]'` |

### CapabilityManifest

| Field | Declared type |
| --- | --- |
| `capabilities` | `tuple[CapabilityIdentity, ...]` |
| `connector` | `ConnectorIdentity` |
| `materialization` | `tuple[MaterializationCapability, ...]` |
| `modes` | `tuple[TableMode, ...]` |
| `uri_schemes` | `tuple[str, ...]` |

| Public member | Signature or access |
| --- | --- |
| `from_wire` | `(payload: 'Mapping[str, Any]') -> 'CapabilityManifest'` |
| `to_wire` | `(self) -> 'dict[str, Any]'` |

### CapabilityObservation

| Field | Declared type |
| --- | --- |
| `operations` | `tuple[OperationDescriptor, ...]` |
| `provider` | `str` |
| `provider_version` | `str \| None` |
| `resolution` | `str` |
| `target` | `TargetSelector` |

| Public member | Signature or access |
| --- | --- |
| `from_wire` | `(payload: 'Mapping[str, Any]') -> 'CapabilityObservation'` |
| `to_wire` | `(self) -> 'dict[str, Any]'` |

### ConnectorAdapter

| Field | Declared type |
| --- | --- |
| `capabilities` | `tuple[CapabilityIdentity, ...]` |
| `hosts` | `tuple[str, ...]` |
| `identity` | `ConnectorIdentity` |
| `modes` | `tuple[TableMode, ...]` |
| `schemes` | `tuple[str, ...]` |

| Public member | Signature or access |
| --- | --- |
| `inspect` | `(self, endpoint: 'AdapterEndpoint', options: 'AdapterOptions') -> 'TableInspection'` |
| `read` | `(self, endpoint: 'AdapterEndpoint', options: 'AdapterOptions') -> 'ArrowReadResult'` |
| `write` | `(self, endpoint: 'AdapterEndpoint', table: 'pa.Table', options: 'AdapterOptions') -> 'TableWriteResult'` |

### ConnectorError

| Field | Declared type |
| --- | --- |
| `code` | `ConnectorErrorCode` |
| `message` | `str` |
| `safe_details` | `Mapping[str, Any]` |

| Public member | Signature or access |
| --- | --- |
| `authentication` | `(message: 'str', *, safe_details: 'Mapping[str, Any] \| None' = None) -> 'ConnectorError'` |
| `configuration` | `(message: 'str', *, safe_details: 'Mapping[str, Any] \| None' = None) -> 'ConnectorError'` |
| `to_wire` | `(self) -> 'dict[str, Any]'` |

### ConnectorErrorCode

| Member | Wire value |
| --- | --- |
| `INVALID_URI` | `invalid_uri` |
| `UNSUPPORTED_CAPABILITY` | `unsupported_capability` |
| `AUTHENTICATION` | `authentication` |
| `CONFLICT` | `conflict` |
| `TIMEOUT` | `timeout` |
| `CANCELLED` | `cancelled` |
| `EXECUTION_FAILED` | `execution_failed` |
| `READBACK_MISMATCH` | `readback_mismatch` |
| `PROTOCOL_INVALID` | `protocol_invalid` |
| `PROTOCOL_VERSION_UNSUPPORTED` | `protocol_version_unsupported` |
| `RESOURCE_LIMIT_EXCEEDED` | `resource_limit_exceeded` |
| `SNAPSHOT_UNAVAILABLE` | `snapshot_unavailable` |
| `IDEMPOTENCY_CONFLICT` | `idempotency_conflict` |
| `VISIBILITY_INCOMPLETE` | `visibility_incomplete` |
| `CONFIGURATION` | `configuration` |

### ConnectorIdentity

| Field | Declared type |
| --- | --- |
| `connector_id` | `str` |
| `connector_version` | `str` |
| `contract_version` | `str` |

| Public member | Signature or access |
| --- | --- |
| `from_wire` | `(payload: 'Mapping[str, Any]') -> 'ConnectorIdentity'` |
| `to_wire` | `(self) -> 'dict[str, str]'` |

### ExecutionOptions

| Field | Declared type |
| --- | --- |
| `allow_partial` | `bool` |
| `dry_run` | `bool` |
| `expected_revision` | `str \| None` |
| `failure_directory` | `str \| None` |
| `idempotency_key` | `str \| None` |

| Public member | Signature or access |
| --- | --- |
| `from_wire` | `(payload: 'Mapping[str, Any]') -> 'ExecutionOptions'` |
| `to_wire` | `(self) -> 'dict[str, Any]'` |

### ExecutionRequest

| Field | Declared type |
| --- | --- |
| `parameters` | `tuple[Any, ...]` |
| `resource_limits` | `ResourceLimits` |
| `statement` | `str` |
| `uri` | `TableURI` |

### ExecutionResult

| Field | Declared type |
| --- | --- |
| `affected_rows` | `int \| None` |
| `artifacts` | `Mapping[str, str]` |
| `operation_id` | `str` |
| `receipt` | `NeutralReceipt \| None` |
| `status` | `str` |

### InspectRequest

| Field | Declared type |
| --- | --- |
| `resource_limits` | `ResourceLimits` |
| `uri` | `TableURI` |

### MaterializationCapability

| Field | Declared type |
| --- | --- |
| `capability` | `CapabilityIdentity` |
| `modes` | `tuple[TableMode, ...]` |
| `profiles` | `tuple[str, ...]` |

| Public member | Signature or access |
| --- | --- |
| `from_wire` | `(payload: 'Mapping[str, Any]') -> 'MaterializationCapability'` |
| `to_wire` | `(self) -> 'dict[str, Any]'` |

### NeutralReceipt

| Field | Declared type |
| --- | --- |
| `batch_count` | `int \| None` |
| `capability` | `CapabilityIdentity` |
| `connector` | `ConnectorIdentity` |
| `content_fingerprint` | `str` |
| `coordinate_convention` | `BaseConvention \| SheetConvention` |
| `mode` | `TableMode` |
| `operation_id` | `str` |
| `row_count` | `int \| None` |
| `safe_uri` | `TableURI` |
| `schema_fingerprint` | `str` |
| `source_revision` | `str` |
| `vendor_receipt_ref` | `str \| None` |

| Public member | Signature or access |
| --- | --- |
| `from_wire` | `(payload: 'Mapping[str, Any]') -> "'NeutralReceipt'"` |
| `to_wire` | `(self) -> 'dict[str, Any]'` |

### OperationDescriptor

| Field | Declared type |
| --- | --- |
| `arguments_schema` | `Mapping[str, Any]` |
| `capability` | `str` |
| `effects` | `tuple[str, ...]` |
| `examples` | `tuple[Mapping[str, Any], ...]` |
| `limits` | `Mapping[str, Any]` |
| `operation_id` | `str` |
| `result_schema` | `Mapping[str, Any]` |
| `schema` | `str` |
| `target_kind` | `str` |
| `version` | `str` |

| Public member | Signature or access |
| --- | --- |
| `from_wire` | `(payload: 'Mapping[str, Any]') -> 'OperationDescriptor'` |
| `to_wire` | `(self) -> 'dict[str, Any]'` |

### OperationRequest

| Field | Declared type |
| --- | --- |
| `arguments` | `Mapping[str, Any]` |
| `namespace` | `str` |
| `operation_id` | `str` |
| `target` | `TargetSelector \| None` |
| `version` | `str` |

| Public member | Signature or access |
| --- | --- |
| `from_wire` | `(payload: 'Mapping[str, Any]') -> 'OperationRequest'` |
| `to_wire` | `(self) -> 'dict[str, Any]'` |

### PluginDescriptor

| Field | Declared type |
| --- | --- |
| `capabilities` | `tuple[CapabilityIdentity, ...]` |
| `factory` | `PluginFactory` |
| `handles_paths` | `bool` |
| `hosts` | `tuple[str, ...]` |
| `identity` | `ConnectorIdentity` |
| `local` | `bool` |
| `materialization` | `tuple[MaterializationCapability, ...]` |
| `modes` | `tuple[TableMode, ...]` |
| `name` | `str` |
| `runtime_metadata` | `bool` |
| `schemes` | `tuple[str, ...]` |

| Public member | Signature or access |
| --- | --- |
| `route_keys` | `(self) -> 'tuple[tuple[str, str \| None], ...]'` |

### PolarsReadResult

| Field | Declared type |
| --- | --- |
| `frame` | `pl.DataFrame` |
| `receipt` | `NeutralReceipt` |

### PolarsTableReader

| Public member | Signature or access |
| --- | --- |
| `read_polars` | `(self, request: 'TableReadRequest') -> 'PolarsReadResult'` |

### PreparedOperation

| Field | Declared type |
| --- | --- |
| `operation_id` | `str` |
| `parameters` | `tuple[Any, ...]` |
| `resource_limits` | `ResourceLimits` |
| `statement` | `str` |
| `target` | `TableURI \| None` |

### ProviderConfig

| Field | Declared type |
| --- | --- |
| `credential_reference` | `str \| None` |
| `enabled` | `bool` |
| `environment` | `Mapping[str, str]` |
| `options` | `Mapping[str, ConfigValue]` |
| `provider_id` | `str` |

### ProviderFactoryContext

| Field | Declared type |
| --- | --- |
| `config` | `ProviderConfig` |
| `credentials` | `Mapping[str, str]` |
| `environment` | `Mapping[str, str]` |
| `transports` | `Mapping[str, Any]` |

### ReadExtent

| Member | Wire value |
| --- | --- |
| `COMPLETE` | `complete` |
| `TRUNCATED` | `truncated` |

### ResolveContext

| Field | Declared type |
| --- | --- |
| `credentials` | `Any` |
| `resource_limits` | `ResourceLimits` |

### ResolvedTable

| Field | Declared type |
| --- | --- |
| `mode` | `TableMode` |
| `resource` | `Any` |
| `uri` | `TableURI` |

### ResourceLimits

| Field | Declared type |
| --- | --- |
| `max_bytes` | `int \| None` |
| `max_rows` | `int \| None` |
| `timeout_seconds` | `int \| None` |

### SheetConvention

| Field | Declared type |
| --- | --- |
| `first_data_row` | `int` |
| `header_rows` | `int` |
| `sheet` | `str \| int` |

| Public member | Signature or access |
| --- | --- |
| `mode` | `property (read-only)` |

### SheetCoordinate

| Field | Declared type |
| --- | --- |
| `column` | `str \| int \| None` |
| `row` | `int` |
| `sheet` | `str \| int` |

| Public member | Signature or access |
| --- | --- |
| `to_wire` | `(self) -> 'dict[str, Any]'` |

### SqlExecutor

| Public member | Signature or access |
| --- | --- |
| `execute` | `(self, request: 'ExecutionRequest') -> 'ExecutionResult'` |

### StepExecutor

| Public member | Signature or access |
| --- | --- |
| `prepare` | `(self, request: 'ExecutionRequest') -> 'PreparedOperation'` |
| `run` | `(self, operation: 'PreparedOperation') -> 'ExecutionResult'` |

### TableInspection

| Field | Declared type |
| --- | --- |
| `columns` | `tuple[str, ...]` |
| `coordinate_convention` | `BaseConvention \| SheetConvention` |
| `facts` | `Mapping[str, Any]` |
| `mode` | `TableMode` |
| `row_count` | `int \| None` |
| `safe_uri` | `TableURI` |
| `schema_fingerprint` | `str` |

### TableInspector

| Public member | Signature or access |
| --- | --- |
| `inspect` | `(self, request: 'InspectRequest') -> 'TableInspection'` |

### TableMode

| Member | Wire value |
| --- | --- |
| `BASE` | `base` |
| `SHEET` | `sheet` |

### TableReadRequest

| Field | Declared type |
| --- | --- |
| `resource_limits` | `ResourceLimits` |
| `uri` | `TableURI` |

### TableURI

| Field | Declared type |
| --- | --- |
| `value` | `str` |

| Public member | Signature or access |
| --- | --- |
| `from_wire` | `(payload: 'Mapping[str, Any]') -> 'TableURI'` |
| `scheme` | `property (read-only)` |
| `to_wire` | `(self) -> 'dict[str, str]'` |

### TableWriteRequest

| Field | Declared type |
| --- | --- |
| `frame` | `pl.DataFrame` |
| `if_exists` | `str` |
| `table` | `str \| None` |
| `uri` | `TableURI` |

### TableWriteResult

| Field | Declared type |
| --- | --- |
| `affected_rows` | `int` |
| `receipt` | `NeutralReceipt` |

### TableWriter

| Public member | Signature or access |
| --- | --- |
| `write` | `(self, request: 'TableWriteRequest') -> 'TableWriteResult'` |

### TargetSelector

| Field | Declared type |
| --- | --- |
| `object_id` | `str \| None` |
| `sheet` | `str \| None` |
| `uri` | `str` |

| Public member | Signature or access |
| --- | --- |
| `from_wire` | `(payload: 'Mapping[str, Any]') -> 'TargetSelector'` |
| `to_wire` | `(self) -> 'dict[str, Any]'` |

### TransactionalStore

| Public member | Signature or access |
| --- | --- |
| `abort` | `(self) -> 'None'` |
| `begin` | `(self, uri: 'TableURI') -> 'None'` |
| `commit` | `(self) -> 'None'` |

### URIResolver

| Public member | Signature or access |
| --- | --- |
| `resolve` | `(self, uri: 'TableURI', context: 'ResolveContext') -> 'ResolvedTable'` |

### WritePreflightAdapter

| Public member | Signature or access |
| --- | --- |
| `preflight_write` | `(self, endpoint: 'AdapterEndpoint', options: 'AdapterOptions') -> 'None'` |

## open_table_connector.spreadsheets

| Name | Kind | Definition |
| --- | --- | --- |
| `ALL_CAPABILITIES` | constant | `tuple; inspect via this named export`  |
| `ArtifactLimits` | class | `(sheets: 'int' = 128, cells: 'int' = 250000, text_bytes: 'int' = 67108864, member_bytes: 'int' = 134217728, image_pixels: 'int' = 40000000, images: 'int' = 128, image_bytes: 'int' = 16777216, total_image_bytes: 'int' = 134217728, archive_bytes: 'int' = 268435456, zip_members: 'int' = 10000, decompressed_bytes: 'int' = 536870912) -> None` [source](../../packages/spreadsheets/src/open_table_connector/spreadsheets/_limits.py) |
| `CellFormat` | class | `(kind: 'str \| None' = None, pattern: 'str \| None' = None, *, builtin_id: 'int \| None' = None, locale: 'str \| None' = None, date_system: 'str \| None' = None) -> None` [source](../../packages/spreadsheets/src/open_table_connector/spreadsheets/model.py) |
| `CellStyle` | class | `(font_size: 'float \| None' = None, bold: 'bool \| None' = None, italic: 'bool \| None' = None, foreground: 'str \| None' = None, fill: 'str \| None' = None) -> None` [source](../../packages/spreadsheets/src/open_table_connector/spreadsheets/model.py) |
| `Change` | class | `(operation_id: 'str', capability: 'CapabilityIdentity', target_key: 'str', arguments: 'Mapping[str, Any]') -> None` [source](../../packages/spreadsheets/src/open_table_connector/spreadsheets/_operations.py) |
| `ImageSpec` | class | `(mime_type: 'str', content: 'bytes', anchor: 'str') -> None` [source](../../packages/spreadsheets/src/open_table_connector/spreadsheets/model.py) |
| `LayoutCapabilityError` | class | `(signature unavailable; see source)` [source](../../packages/spreadsheets/src/open_table_connector/spreadsheets/_layout.py) |
| `LayoutRecipe` | class | `(schema: 'str', version: 'str', requirements: 'tuple[str, ...]', operations: 'tuple[RichObjectRequest, ...]') -> None` [source](../../packages/spreadsheets/src/open_table_connector/spreadsheets/recipes.py) |
| `ObjectObservation` | class | `(object_id: 'str', kind: 'str', fields: 'Mapping[str, object]', coverage: 'tuple[str, ...]', content_hash: 'str \| None' = None) -> None` [source](../../packages/spreadsheets/src/open_table_connector/spreadsheets/rich.py) |
| `RangeRef` | class | `(address: 'str') -> None` [source](../../packages/spreadsheets/src/open_table_connector/spreadsheets/model.py) |
| `RichObjectRequest` | class | `(operation_id: 'str', target_key: 'str', arguments: 'Mapping[str, object]') -> None` [source](../../packages/spreadsheets/src/open_table_connector/spreadsheets/rich.py) |
| `RichQualification` | class | `(provider_id: 'str', operation_id: 'str', options_schema: 'Mapping[str, object]', status: 'str', evidence: 'tuple[str, ...]', reason: 'str \| None' = None) -> None` [source](../../packages/spreadsheets/src/open_table_connector/spreadsheets/rich.py) |
| `SPREADSHEET_FORMULA_SET_RANGE` | constant | `CapabilityIdentity(capability_id='spreadsheet.formula.set_range', capability_version='1.0')`  |
| `SPREADSHEET_IMAGE_INSERT` | constant | `CapabilityIdentity(capability_id='spreadsheet.image.insert', capability_version='1.0')`  |
| `SPREADSHEET_RANGE_ALIGNMENT_READ` | constant | `CapabilityIdentity(capability_id='spreadsheet.range.alignment.read', capability_version='1.0')`  |
| `SPREADSHEET_RANGE_ALIGNMENT_WRITE` | constant | `CapabilityIdentity(capability_id='spreadsheet.range.alignment.write', capability_version='1.0')`  |
| `SPREADSHEET_RANGE_BORDER_READ` | constant | `CapabilityIdentity(capability_id='spreadsheet.range.border.read', capability_version='1.0')`  |
| `SPREADSHEET_RANGE_BORDER_WRITE` | constant | `CapabilityIdentity(capability_id='spreadsheet.range.border.write', capability_version='1.0')`  |
| `SPREADSHEET_RANGE_FORMAT` | constant | `CapabilityIdentity(capability_id='spreadsheet.range.format', capability_version='1.0')`  |
| `SPREADSHEET_RANGE_READ` | constant | `CapabilityIdentity(capability_id='spreadsheet.range.read', capability_version='1.0')`  |
| `SPREADSHEET_RANGE_SORT` | constant | `CapabilityIdentity(capability_id='spreadsheet.range.sort', capability_version='1.0')`  |
| `SPREADSHEET_RANGE_STYLE` | constant | `CapabilityIdentity(capability_id='spreadsheet.range.style', capability_version='1.0')`  |
| `SPREADSHEET_RANGE_STYLE_READ` | constant | `CapabilityIdentity(capability_id='spreadsheet.range.style.read', capability_version='1.0')`  |
| `SPREADSHEET_RANGE_TEXT_LAYOUT_READ` | constant | `CapabilityIdentity(capability_id='spreadsheet.range.text_layout.read', capability_version='1.0')`  |
| `SPREADSHEET_RANGE_TEXT_LAYOUT_WRITE` | constant | `CapabilityIdentity(capability_id='spreadsheet.range.text_layout.write', capability_version='1.0')`  |
| `SPREADSHEET_RANGE_WRITE` | constant | `CapabilityIdentity(capability_id='spreadsheet.range.write', capability_version='1.0')`  |
| `SPREADSHEET_WORKBOOK_COPY` | constant | `CapabilityIdentity(capability_id='spreadsheet.workbook.copy', capability_version='1.0')`  |
| `SPREADSHEET_WORKBOOK_INSPECT` | constant | `CapabilityIdentity(capability_id='spreadsheet.workbook.inspect', capability_version='1.0')`  |
| `SPREADSHEET_WORKBOOK_VERIFY` | constant | `CapabilityIdentity(capability_id='spreadsheet.workbook.verify', capability_version='1.0')`  |
| `SPREADSHEET_WORKBOOK_WRITE` | constant | `CapabilityIdentity(capability_id='spreadsheet.workbook.write', capability_version='1.0')`  |
| `SPREADSHEET_WORKSHEET_CONFIG_READ` | constant | `CapabilityIdentity(capability_id='spreadsheet.worksheet.config.read', capability_version='1.0')`  |
| `SPREADSHEET_WORKSHEET_LIST` | constant | `CapabilityIdentity(capability_id='spreadsheet.worksheet.list', capability_version='1.0')`  |
| `SpreadsheetProvider` | class | `(*args, **kwargs)` [source](../../packages/spreadsheets/src/open_table_connector/spreadsheets/_protocols.py) |
| `SpreadsheetTarget` | class | `(uri: 'str') -> None` [source](../../packages/spreadsheets/src/open_table_connector/spreadsheets/model.py) |
| `WorkbookSnapshot` | class | `(uri: 'str', source: 'TargetSelector', content_hash: 'str', captured_at: 'str', provider_revision: 'str \| None', consistency: 'str') -> None` [source](../../packages/spreadsheets/src/open_table_connector/spreadsheets/snapshots.py) |
| `WorksheetRef` | class | `(name: 'str \| None' = None, worksheet_id: 'str \| None' = None) -> None` [source](../../packages/spreadsheets/src/open_table_connector/spreadsheets/model.py) |
| `normalize_config` | function | `(arguments: 'Mapping[str, Any]', *, descriptor: 'Mapping[str, Any]') -> 'JSON'` [source](../../packages/spreadsheets/src/open_table_connector/spreadsheets/_layout.py) |
| `normalize_format` | function | `(arguments: 'Mapping[str, Any]', *, descriptor: 'Mapping[str, Any]') -> 'JSON'` [source](../../packages/spreadsheets/src/open_table_connector/spreadsheets/formats.py) |
| `normalize_style` | function | `(arguments: 'Mapping[str, Any]', *, descriptor: 'Mapping[str, Any]', baseline: 'Mapping[str, Any] \| None' = None) -> 'JSON'` [source](../../packages/spreadsheets/src/open_table_connector/spreadsheets/_layout.py) |
| `parse_recipe` | function | `(payload: 'object') -> 'LayoutRecipe'` [source](../../packages/spreadsheets/src/open_table_connector/spreadsheets/recipes.py) |
| `prepare_layout` | function | `(changes: 'Sequence[Change]', *, baseline: 'Mapping[str, Any]', descriptor: 'Mapping[str, Any]') -> 'JSON'` [source](../../packages/spreadsheets/src/open_table_connector/spreadsheets/_layout.py) |
| `qualification` | function | `(provider_id: 'str', operation_id: 'str') -> 'RichQualification'` [source](../../packages/spreadsheets/src/open_table_connector/spreadsheets/rich.py) |
| `validate_descriptor` | function | `(value: 'Mapping[str, Any]') -> 'JSON'` [source](../../packages/spreadsheets/src/open_table_connector/spreadsheets/_layout.py) |

### ArtifactLimits

| Field | Declared type |
| --- | --- |
| `archive_bytes` | `int` |
| `cells` | `int` |
| `decompressed_bytes` | `int` |
| `image_bytes` | `int` |
| `image_pixels` | `int` |
| `images` | `int` |
| `member_bytes` | `int` |
| `sheets` | `int` |
| `text_bytes` | `int` |
| `total_image_bytes` | `int` |
| `zip_members` | `int` |

### CellFormat

| Field | Declared type |
| --- | --- |
| `builtin_id` | `int \| None` |
| `date_system` | `str \| None` |
| `kind` | `str \| None` |
| `locale` | `str \| None` |
| `pattern` | `str \| None` |

### CellStyle

| Field | Declared type |
| --- | --- |
| `bold` | `bool \| None` |
| `fill` | `str \| None` |
| `font_size` | `float \| None` |
| `foreground` | `str \| None` |
| `italic` | `bool \| None` |

### Change

| Field | Declared type |
| --- | --- |
| `arguments` | `Mapping[str, Any]` |
| `capability` | `CapabilityIdentity` |
| `operation_id` | `str` |
| `target_key` | `str` |

### ImageSpec

| Field | Declared type |
| --- | --- |
| `anchor` | `str` |
| `content` | `bytes` |
| `mime_type` | `str` |
| `sha256` | `str` |

| Public member | Signature or access |
| --- | --- |
| `to_wire` | `(self) -> 'dict[str, Any]'` |

### LayoutCapabilityError

### LayoutRecipe

| Field | Declared type |
| --- | --- |
| `operations` | `tuple[RichObjectRequest, ...]` |
| `requirements` | `tuple[str, ...]` |
| `schema` | `str` |
| `version` | `str` |

| Public member | Signature or access |
| --- | --- |
| `to_wire` | `(self) -> 'dict[str, object]'` |

### ObjectObservation

| Field | Declared type |
| --- | --- |
| `content_hash` | `str \| None` |
| `coverage` | `tuple[str, ...]` |
| `fields` | `Mapping[str, object]` |
| `kind` | `str` |
| `object_id` | `str` |

### RangeRef

| Field | Declared type |
| --- | --- |
| `address` | `str` |

| Public member | Signature or access |
| --- | --- |
| `to_wire` | `(self) -> 'dict[str, str]'` |

### RichObjectRequest

| Field | Declared type |
| --- | --- |
| `arguments` | `Mapping[str, object]` |
| `operation_id` | `str` |
| `target_key` | `str` |

| Public member | Signature or access |
| --- | --- |
| `to_change` | `(self)` |

### RichQualification

| Field | Declared type |
| --- | --- |
| `evidence` | `tuple[str, ...]` |
| `operation_id` | `str` |
| `options_schema` | `Mapping[str, object]` |
| `provider_id` | `str` |
| `reason` | `str \| None` |
| `status` | `str` |

### SpreadsheetProvider

| Public member | Signature or access |
| --- | --- |
| `bind` | `(self, target: 'SpreadsheetTarget') -> 'Mapping[str, Any]'` |
| `commit` | `(self, binding: 'Mapping[str, Any]', changes: 'Iterable[Change]', *, allow_partial: 'bool', expected_revision: 'str \| None', idempotency_key: 'str \| None') -> 'Mapping[str, Any]'` |
| `observe` | `(self, binding: 'Mapping[str, Any]', selector: 'Mapping[str, Any]') -> 'Mapping[str, Any]'` |
| `preflight` | `(self, binding: 'Mapping[str, Any]', changes: 'Iterable[Change]') -> 'Mapping[str, Any]'` |

### SpreadsheetTarget

| Field | Declared type |
| --- | --- |
| `uri` | `str` |

| Public member | Signature or access |
| --- | --- |
| `from_wire` | `(payload: 'Mapping[str, Any]') -> 'SpreadsheetTarget'` |
| `to_wire` | `(self) -> 'dict[str, str]'` |

### WorkbookSnapshot

| Field | Declared type |
| --- | --- |
| `captured_at` | `str` |
| `consistency` | `str` |
| `content_hash` | `str` |
| `provider_revision` | `str \| None` |
| `source` | `TargetSelector` |
| `uri` | `str` |

### WorksheetRef

| Field | Declared type |
| --- | --- |
| `name` | `str \| None` |
| `worksheet_id` | `str \| None` |

| Public member | Signature or access |
| --- | --- |
| `to_wire` | `(self) -> 'dict[str, str \| None]'` |

## open_table_connector.formulas

| Name | Kind | Definition |
| --- | --- | --- |
| `A1Rectangle` | class | `(worksheet_name: 'str \| None', start_address: 'str', end_address: 'str', start_column: 'int', start_row: 'int', end_column: 'int', end_row: 'int') -> None` [source](../../packages/formulas/src/open_table_connector/formulas/ranges.py) |
| `ALL_CAPABILITIES` | constant | `tuple; inspect via this named export`  |
| `BoundFieldFormulaTarget` | class | `(table: '_TTable', field: 'FieldRef') -> None` [source](../../packages/formulas/src/open_table_connector/formulas/model.py) |
| `BoundGridFormulaTarget` | class | `(grid: 'TableURI \| str', worksheet: 'WorksheetRef') -> None` [source](../../packages/formulas/src/open_table_connector/formulas/model.py) |
| `CalculationState` | enum | `(value, names=None, *, module=None, qualname=None, type=None, start=1, boundary=None)` [source](../../packages/formulas/src/open_table_connector/formulas/observations.py) |
| `CalculationTrigger` | enum | `(value, names=None, *, module=None, qualname=None, type=None, start=1, boundary=None)` [source](../../packages/formulas/src/open_table_connector/formulas/observations.py) |
| `CompositeFormulaConnectorExtension` | class | `(grid: 'GridFormulaConnectorExtension \| None' = None, field: 'FieldFormulaConnectorExtension \| None' = None) -> None` [source](../../packages/formulas/src/open_table_connector/formulas/protocols.py) |
| `EXCEL_A1` | constant | `'excel-a1'`  |
| `FEISHU_BITABLE` | constant | `'feishu-bitable'`  |
| `FIELD_READ` | constant | `CapabilityIdentity(capability_id='formula.field.read', capability_version='1.0')`  |
| `FIELD_RECALCULATE` | constant | `CapabilityIdentity(capability_id='formula.field.recalculate', capability_version='1.0')`  |
| `FIELD_SET` | constant | `CapabilityIdentity(capability_id='formula.field.set', capability_version='1.0')`  |
| `FIELD_VALUES_READ` | constant | `CapabilityIdentity(capability_id='formula.field.values.read', capability_version='1.0')`  |
| `FORMULA_DIALECTS` | constant | `('google-sheets-a1', 'maybe-sheet-a1', 'excel-a1', 'maybe-base', 'feishu-bitable')`  |
| `FieldFormulaBindRequest` | class | `(target: 'FieldFormulaTarget[_TTable]') -> None` [source](../../packages/formulas/src/open_table_connector/formulas/operations.py) |
| `FieldFormulaBinding` | class | `(target: 'BoundFieldFormulaTarget[_TTable]', capabilities: 'FormulaCapabilitySet', observed_revision: 'str \| None') -> None` [source](../../packages/formulas/src/open_table_connector/formulas/operations.py) |
| `FieldFormulaConnectorExtension` | class | `(*args, **kwargs)` [source](../../packages/formulas/src/open_table_connector/formulas/protocols.py) |
| `FieldFormulaObservation` | class | `(table_uri: 'TableURI \| str', field_id: 'str', field_name: 'str', expression: 'FormulaExpression', result_type: 'str \| None', observed_revision: 'str') -> None` [source](../../packages/formulas/src/open_table_connector/formulas/observations.py) |
| `FieldFormulaReadRequest` | class | `(target: 'BoundFieldFormulaTarget[_TTable]') -> None` [source](../../packages/formulas/src/open_table_connector/formulas/operations.py) |
| `FieldFormulaRecalculateRequest` | class | `(target: 'BoundFieldFormulaTarget[_TTable]', scope: 'FieldRecalculationScope', expected_revision: 'str \| None' = None, idempotency_key: 'str \| None' = None) -> None` [source](../../packages/formulas/src/open_table_connector/formulas/operations.py) |
| `FieldFormulaSetRequest` | class | `(target: 'BoundFieldFormulaTarget[_TTable]', expression: 'FormulaExpression', expected_revision: 'str \| None' = None, idempotency_key: 'str \| None' = None) -> None` [source](../../packages/formulas/src/open_table_connector/formulas/operations.py) |
| `FieldFormulaTarget` | class | `(table: '_TTable', field: 'FieldRef') -> None` [source](../../packages/formulas/src/open_table_connector/formulas/model.py) |
| `FieldFormulaValueObservation` | class | `(table_uri: 'TableURI \| str', field_id: 'str', field_name: 'str', values: 'tuple[FormulaRecordValue, ...]', calculation_state: 'CalculationState', calculation_trigger: 'CalculationTrigger', dependency_scope: 'str', observed_revision: 'str') -> None` [source](../../packages/formulas/src/open_table_connector/formulas/observations.py) |
| `FieldFormulaValueReadRequest` | class | `(target: 'BoundFieldFormulaTarget[_TTable]', limits: 'FormulaResourceLimits \| None' = None) -> None` [source](../../packages/formulas/src/open_table_connector/formulas/operations.py) |
| `FieldRecalculationScope` | enum | `(value, names=None, *, module=None, qualname=None, type=None, start=1, boundary=None)` [source](../../packages/formulas/src/open_table_connector/formulas/model.py) |
| `FieldRef` | class | `(name: 'str \| None' = None, field_id: 'str \| None' = None) -> None` [source](../../packages/formulas/src/open_table_connector/formulas/model.py) |
| `FormulaCapabilityDetails` | class | `(target_kind: 'str', dialects: 'tuple[str, ...]', max_cells_per_operation: 'int \| None', max_expression_bytes: 'int', recalculation_scopes: 'tuple[str, ...]', calculation_states: 'tuple[CalculationState, ...]', mutation_atomicity: 'MutationAtomicity', revision_enforcement: 'RevisionEnforcement', idempotency_strength: 'IdempotencyStrength') -> None` [source](../../packages/formulas/src/open_table_connector/formulas/observations.py) |
| `FormulaCapabilitySet` | class | `(capabilities: 'tuple[CapabilityIdentity, ...]', details: 'FormulaCapabilityDetails') -> None` [source](../../packages/formulas/src/open_table_connector/formulas/observations.py) |
| `FormulaCell` | class | `(address: 'str', expression: 'FormulaExpression') -> None` [source](../../packages/formulas/src/open_table_connector/formulas/observations.py) |
| `FormulaCommitState` | enum | `(value, names=None, *, module=None, qualname=None, type=None, start=1, boundary=None)` [source](../../packages/formulas/src/open_table_connector/formulas/errors.py) |
| `FormulaConnectorExtension` | class | `(*args, **kwargs)` [source](../../packages/formulas/src/open_table_connector/formulas/protocols.py) |
| `FormulaError` | class | `(signature unavailable; see source)` [source](../../packages/formulas/src/open_table_connector/formulas/errors.py) |
| `FormulaErrorCode` | enum | `(value, names=None, *, module=None, qualname=None, type=None, start=1, boundary=None)` [source](../../packages/formulas/src/open_table_connector/formulas/errors.py) |
| `FormulaErrorValue` | class | `(code: 'str') -> None` [source](../../packages/formulas/src/open_table_connector/formulas/observations.py) |
| `FormulaExpression` | class | `(text: 'str', dialect: 'str') -> None` [source](../../packages/formulas/src/open_table_connector/formulas/model.py) |
| `FormulaExtensionErrorInfo` | class | `(code: 'FormulaErrorCode', message: 'str', safe_details: 'Mapping[str, Any]' = <factory>) -> None` [source](../../packages/formulas/src/open_table_connector/formulas/errors.py) |
| `FormulaExtensionResult` | class | `(value: '_T \| None', outcome: 'FormulaOutcome', commit: 'FormulaCommitState', verification: 'FormulaVerificationState', receipts: 'tuple[object, ...]', error: 'FormulaExtensionErrorInfo \| None' = None) -> None` [source](../../packages/formulas/src/open_table_connector/formulas/errors.py) |
| `FormulaIdempotencyDecision` | class | `(disposition: 'FormulaIdempotencyDisposition', operation_hash: 'str \| None' = None) -> None` [source](../../packages/formulas/src/open_table_connector/formulas/operations.py) |
| `FormulaIdempotencyDisposition` | enum | `(value, names=None, *, module=None, qualname=None, type=None, start=1, boundary=None)` [source](../../packages/formulas/src/open_table_connector/formulas/operations.py) |
| `FormulaIdempotencyLedger` | class | `(*, limit: 'int') -> 'None'` [source](../../packages/formulas/src/open_table_connector/formulas/operations.py) |
| `FormulaMutation` | class | `(target_kind: 'str', affected_count: 'int', formula_observation: 'GridFormulaObservation \| FieldFormulaObservation', revision_before: 'str \| None', revision_after: 'str') -> None` [source](../../packages/formulas/src/open_table_connector/formulas/observations.py) |
| `FormulaOutcome` | enum | `(value, names=None, *, module=None, qualname=None, type=None, start=1, boundary=None)` [source](../../packages/formulas/src/open_table_connector/formulas/errors.py) |
| `FormulaReceiptDetails` | class | `(target_kind: 'str', table_mode: 'str', target: 'str', selector: 'str', capability: 'str', dialect: 'str', expression_sha256: 'str \| None' = None, observation_sha256: 'str \| None' = None, value_observation_sha256: 'str \| None' = None, affected_count: 'int \| None' = None, observed_count: 'int \| None' = None, copy_fill_policy: 'str \| None' = None, calculation_state: 'str \| None' = None, calculation_trigger: 'str \| None' = None, dependency_scope: 'str \| None' = None, revision_before: 'str \| None' = None, revision_after: 'str \| None' = None, mutation_atomicity: 'str \| None' = None, revision_enforcement: 'str \| None' = None, verification: 'str \| None' = None, provider_receipt_ref: 'str \| None' = None, safe_details: 'Mapping[str, Any]' = <factory>) -> None` [source](../../packages/formulas/src/open_table_connector/formulas/receipts.py) |
| `FormulaRecordValue` | class | `(record_id: 'str', value: 'FormulaValue') -> None` [source](../../packages/formulas/src/open_table_connector/formulas/observations.py) |
| `FormulaResourceLimits` | class | `(max_cells: 'int \| None' = None, max_records: 'int \| None' = None, max_response_bytes: 'int \| None' = None, timeout_seconds: 'float \| None' = None, max_expression_bytes: 'int \| None' = None) -> None` [source](../../packages/formulas/src/open_table_connector/formulas/model.py) |
| `FormulaValue` | class | `(kind: 'str', value: 'object' = None, logical_type: 'str \| None' = None) -> None` [source](../../packages/formulas/src/open_table_connector/formulas/observations.py) |
| `FormulaValueCell` | class | `(address: 'str', value: 'FormulaValue') -> None` [source](../../packages/formulas/src/open_table_connector/formulas/observations.py) |
| `FormulaVerificationState` | enum | `(value, names=None, *, module=None, qualname=None, type=None, start=1, boundary=None)` [source](../../packages/formulas/src/open_table_connector/formulas/errors.py) |
| `GOOGLE_SHEETS_A1` | constant | `'google-sheets-a1'`  |
| `GRID_READ` | constant | `CapabilityIdentity(capability_id='formula.grid.read', capability_version='1.0')`  |
| `GRID_RECALCULATE` | constant | `CapabilityIdentity(capability_id='formula.grid.recalculate', capability_version='1.0')`  |
| `GRID_SET` | constant | `CapabilityIdentity(capability_id='formula.grid.set', capability_version='1.0')`  |
| `GRID_VALUES_READ` | constant | `CapabilityIdentity(capability_id='formula.grid.values.read', capability_version='1.0')`  |
| `GridFormulaBindRequest` | class | `(target: 'GridFormulaTarget') -> None` [source](../../packages/formulas/src/open_table_connector/formulas/operations.py) |
| `GridFormulaBinding` | class | `(target: 'BoundGridFormulaTarget', capabilities: 'FormulaCapabilitySet', observed_revision: 'str \| None') -> None` [source](../../packages/formulas/src/open_table_connector/formulas/operations.py) |
| `GridFormulaConnectorExtension` | class | `(*args, **kwargs)` [source](../../packages/formulas/src/open_table_connector/formulas/protocols.py) |
| `GridFormulaObservation` | class | `(worksheet_id: 'str', requested_range: 'str', formulas: 'tuple[FormulaCell, ...]', observed_revision: 'str') -> None` [source](../../packages/formulas/src/open_table_connector/formulas/observations.py) |
| `GridFormulaReadRequest` | class | `(target: 'BoundGridFormulaTarget', cell_range: 'str', limits: 'FormulaResourceLimits \| None' = None) -> None` [source](../../packages/formulas/src/open_table_connector/formulas/operations.py) |
| `GridFormulaRecalculateRequest` | class | `(target: 'BoundGridFormulaTarget', scope: 'GridRecalculationScope', cell_range: 'str \| None' = None, expected_revision: 'str \| None' = None, idempotency_key: 'str \| None' = None, limits: 'FormulaResourceLimits \| None' = None) -> None` [source](../../packages/formulas/src/open_table_connector/formulas/operations.py) |
| `GridFormulaSetRequest` | class | `(target: 'BoundGridFormulaTarget', cell_range: 'str', expression: 'FormulaExpression', expected_revision: 'str \| None' = None, idempotency_key: 'str \| None' = None, limits: 'FormulaResourceLimits \| None' = None) -> None` [source](../../packages/formulas/src/open_table_connector/formulas/operations.py) |
| `GridFormulaTarget` | class | `(grid: 'TableURI \| str', worksheet: 'WorksheetRef') -> None` [source](../../packages/formulas/src/open_table_connector/formulas/model.py) |
| `GridFormulaValueObservation` | class | `(worksheet_id: 'str', requested_range: 'str', values: 'tuple[FormulaValueCell, ...]', calculation_state: 'CalculationState', calculation_trigger: 'CalculationTrigger', dependency_scope: 'str', observed_revision: 'str') -> None` [source](../../packages/formulas/src/open_table_connector/formulas/observations.py) |
| `GridFormulaValueReadRequest` | class | `(target: 'BoundGridFormulaTarget', cell_range: 'str', limits: 'FormulaResourceLimits \| None' = None) -> None` [source](../../packages/formulas/src/open_table_connector/formulas/operations.py) |
| `GridRecalculationScope` | enum | `(value, names=None, *, module=None, qualname=None, type=None, start=1, boundary=None)` [source](../../packages/formulas/src/open_table_connector/formulas/model.py) |
| `IdempotencyStrength` | enum | `(value, names=None, *, module=None, qualname=None, type=None, start=1, boundary=None)` [source](../../packages/formulas/src/open_table_connector/formulas/observations.py) |
| `MAYBE_BASE` | constant | `'maybe-base'`  |
| `MAYBE_SHEET_A1` | constant | `'maybe-sheet-a1'`  |
| `MutationAtomicity` | enum | `(value, names=None, *, module=None, qualname=None, type=None, start=1, boundary=None)` [source](../../packages/formulas/src/open_table_connector/formulas/observations.py) |
| `RecalculationObservation` | class | `(target_kind: 'str', requested_scope: 'str', effective_scope: 'str', revision_before: 'str \| None', revision_after: 'str \| None', provider_status: 'str', calculation_state: 'CalculationState', verification: 'str', value_observation: 'GridFormulaValueObservation \| FieldFormulaValueObservation \| None') -> None` [source](../../packages/formulas/src/open_table_connector/formulas/observations.py) |
| `RevisionEnforcement` | enum | `(value, names=None, *, module=None, qualname=None, type=None, start=1, boundary=None)` [source](../../packages/formulas/src/open_table_connector/formulas/observations.py) |
| `WorksheetRef` | class | `(name: 'str \| None' = None, worksheet_id: 'str \| None' = None) -> None` [source](../../packages/formulas/src/open_table_connector/formulas/model.py) |
| `formula_observation_from_wire` | function | `(payload: 'Mapping[str, object]') -> 'GridFormulaObservation \| FieldFormulaObservation \| GridFormulaValueObservation \| FieldFormulaValueObservation'` [source](../../packages/formulas/src/open_table_connector/formulas/wire.py) |
| `formula_observation_hash` | function | `(observation: 'GridFormulaObservation \| FieldFormulaObservation \| GridFormulaValueObservation \| FieldFormulaValueObservation') -> 'str'` [source](../../packages/formulas/src/open_table_connector/formulas/wire.py) |
| `formula_operation_from_wire` | function | `(payload: 'Mapping[str, object]') -> 'FormulaMutation \| RecalculationObservation'` [source](../../packages/formulas/src/open_table_connector/formulas/wire.py) |

### A1Rectangle

| Field | Declared type |
| --- | --- |
| `end_address` | `str` |
| `end_column` | `int` |
| `end_row` | `int` |
| `start_address` | `str` |
| `start_column` | `int` |
| `start_row` | `int` |
| `worksheet_name` | `str \| None` |

| Public member | Signature or access |
| --- | --- |
| `cell_count` | `property (read-only)` |
| `height` | `property (read-only)` |
| `parse` | `(selector: 'str') -> 'A1Rectangle'` |
| `require_unbound_selector` | `(self, selector: 'str') -> 'A1Rectangle'` |
| `width` | `property (read-only)` |

### BoundFieldFormulaTarget

| Field | Declared type |
| --- | --- |
| `field` | `FieldRef` |
| `table` | `_TTable` |

### BoundGridFormulaTarget

| Field | Declared type |
| --- | --- |
| `grid` | `TableURI \| str` |
| `worksheet` | `WorksheetRef` |

### CalculationState

| Member | Wire value |
| --- | --- |
| `PROVIDER_CURRENT` | `provider_current` |
| `CACHED` | `cached` |
| `UNKNOWN` | `unknown` |

### CalculationTrigger

| Member | Wire value |
| --- | --- |
| `EXPLICIT_RECALCULATION` | `explicit_recalculation` |
| `MUTATION` | `mutation` |
| `PROVIDER_READ` | `provider_read` |
| `STORED_CACHE` | `stored_cache` |

### CompositeFormulaConnectorExtension

| Field | Declared type |
| --- | --- |
| `field` | `FieldFormulaConnectorExtension \| None` |
| `grid` | `GridFormulaConnectorExtension \| None` |

| Public member | Signature or access |
| --- | --- |
| `bind_field` | `(self, request: 'FieldFormulaBindRequest') -> 'FormulaExtensionResult[FieldFormulaBinding]'` |
| `bind_grid` | `(self, request: 'GridFormulaBindRequest') -> 'FormulaExtensionResult[GridFormulaBinding]'` |
| `read_field` | `(self, request: 'FieldFormulaReadRequest') -> 'FormulaExtensionResult[FieldFormulaObservation]'` |
| `read_field_values` | `(self, request: 'FieldFormulaValueReadRequest') -> 'FormulaExtensionResult[FieldFormulaValueObservation]'` |
| `read_grid` | `(self, request: 'GridFormulaReadRequest') -> 'FormulaExtensionResult[GridFormulaObservation]'` |
| `read_grid_values` | `(self, request: 'GridFormulaValueReadRequest') -> 'FormulaExtensionResult[GridFormulaValueObservation]'` |
| `recalculate_field` | `(self, request: 'FieldFormulaRecalculateRequest') -> 'FormulaExtensionResult[RecalculationObservation]'` |
| `recalculate_grid` | `(self, request: 'GridFormulaRecalculateRequest') -> 'FormulaExtensionResult[RecalculationObservation]'` |
| `set_field` | `(self, request: 'FieldFormulaSetRequest') -> 'FormulaExtensionResult[FormulaMutation]'` |
| `set_grid` | `(self, request: 'GridFormulaSetRequest') -> 'FormulaExtensionResult[FormulaMutation]'` |

### FieldFormulaBindRequest

| Field | Declared type |
| --- | --- |
| `target` | `FieldFormulaTarget[_TTable]` |

### FieldFormulaBinding

| Field | Declared type |
| --- | --- |
| `capabilities` | `FormulaCapabilitySet` |
| `observed_revision` | `str \| None` |
| `target` | `BoundFieldFormulaTarget[_TTable]` |

### FieldFormulaConnectorExtension

| Public member | Signature or access |
| --- | --- |
| `bind_field` | `(self, request: 'FieldFormulaBindRequest') -> 'FormulaExtensionResult[FieldFormulaBinding]'` |
| `read_field` | `(self, request: 'FieldFormulaReadRequest') -> 'FormulaExtensionResult[FieldFormulaObservation]'` |
| `read_field_values` | `(self, request: 'FieldFormulaValueReadRequest') -> 'FormulaExtensionResult[FieldFormulaValueObservation]'` |
| `recalculate_field` | `(self, request: 'FieldFormulaRecalculateRequest') -> 'FormulaExtensionResult[RecalculationObservation]'` |
| `set_field` | `(self, request: 'FieldFormulaSetRequest') -> 'FormulaExtensionResult[FormulaMutation]'` |

### FieldFormulaObservation

| Field | Declared type |
| --- | --- |
| `expression` | `FormulaExpression` |
| `field_id` | `str` |
| `field_name` | `str` |
| `observed_revision` | `str` |
| `result_type` | `str \| None` |
| `table_uri` | `TableURI \| str` |

| Public member | Signature or access |
| --- | --- |
| `from_wire` | `(payload: 'Mapping[str, Any]') -> 'FieldFormulaObservation'` |
| `to_wire` | `(self) -> 'dict[str, object]'` |

### FieldFormulaReadRequest

| Field | Declared type |
| --- | --- |
| `target` | `BoundFieldFormulaTarget[_TTable]` |

### FieldFormulaRecalculateRequest

| Field | Declared type |
| --- | --- |
| `expected_revision` | `str \| None` |
| `idempotency_key` | `str \| None` |
| `scope` | `FieldRecalculationScope` |
| `target` | `BoundFieldFormulaTarget[_TTable]` |

### FieldFormulaSetRequest

| Field | Declared type |
| --- | --- |
| `expected_revision` | `str \| None` |
| `expression` | `FormulaExpression` |
| `idempotency_key` | `str \| None` |
| `target` | `BoundFieldFormulaTarget[_TTable]` |

### FieldFormulaTarget

| Field | Declared type |
| --- | --- |
| `field` | `FieldRef` |
| `table` | `_TTable` |

### FieldFormulaValueObservation

| Field | Declared type |
| --- | --- |
| `calculation_state` | `CalculationState` |
| `calculation_trigger` | `CalculationTrigger` |
| `dependency_scope` | `str` |
| `field_id` | `str` |
| `field_name` | `str` |
| `observed_revision` | `str` |
| `table_uri` | `TableURI \| str` |
| `values` | `tuple[FormulaRecordValue, ...]` |

| Public member | Signature or access |
| --- | --- |
| `from_wire` | `(payload: 'Mapping[str, Any]') -> 'FieldFormulaValueObservation'` |
| `to_wire` | `(self) -> 'dict[str, object]'` |

### FieldFormulaValueReadRequest

| Field | Declared type |
| --- | --- |
| `limits` | `FormulaResourceLimits \| None` |
| `target` | `BoundFieldFormulaTarget[_TTable]` |

### FieldRecalculationScope

| Member | Wire value |
| --- | --- |
| `FIELD` | `field` |
| `TABLE` | `table` |

### FieldRef

| Field | Declared type |
| --- | --- |
| `field_id` | `str \| None` |
| `name` | `str \| None` |

### FormulaCapabilityDetails

| Field | Declared type |
| --- | --- |
| `calculation_states` | `tuple[CalculationState, ...]` |
| `dialects` | `tuple[str, ...]` |
| `idempotency_strength` | `IdempotencyStrength` |
| `max_cells_per_operation` | `int \| None` |
| `max_expression_bytes` | `int` |
| `mutation_atomicity` | `MutationAtomicity` |
| `recalculation_scopes` | `tuple[str, ...]` |
| `revision_enforcement` | `RevisionEnforcement` |
| `target_kind` | `str` |

| Public member | Signature or access |
| --- | --- |
| `from_wire` | `(payload: 'Mapping[str, Any]') -> 'FormulaCapabilityDetails'` |
| `to_wire` | `(self) -> 'dict[str, object]'` |

### FormulaCapabilitySet

| Field | Declared type |
| --- | --- |
| `capabilities` | `tuple[CapabilityIdentity, ...]` |
| `details` | `FormulaCapabilityDetails` |

| Public member | Signature or access |
| --- | --- |
| `from_wire` | `(payload: 'Mapping[str, Any]') -> 'FormulaCapabilitySet'` |
| `to_wire` | `(self) -> 'dict[str, object]'` |

### FormulaCell

| Field | Declared type |
| --- | --- |
| `address` | `str` |
| `expression` | `FormulaExpression` |

| Public member | Signature or access |
| --- | --- |
| `from_wire` | `(payload: 'Mapping[str, Any]') -> 'FormulaCell'` |
| `to_wire` | `(self) -> 'dict[str, object]'` |

### FormulaCommitState

| Member | Wire value |
| --- | --- |
| `NOT_STARTED` | `not_started` |
| `NOT_APPLICABLE` | `not_applicable` |
| `COMMITTED` | `committed` |
| `NOT_COMMITTED` | `not_committed` |
| `PARTIAL` | `partial` |
| `UNKNOWN` | `unknown` |

### FormulaConnectorExtension

| Public member | Signature or access |
| --- | --- |
| `bind_field` | `(self, request: 'FieldFormulaBindRequest') -> 'FormulaExtensionResult[FieldFormulaBinding]'` |
| `bind_grid` | `(self, request: 'GridFormulaBindRequest') -> 'FormulaExtensionResult[GridFormulaBinding]'` |
| `read_field` | `(self, request: 'FieldFormulaReadRequest') -> 'FormulaExtensionResult[FieldFormulaObservation]'` |
| `read_field_values` | `(self, request: 'FieldFormulaValueReadRequest') -> 'FormulaExtensionResult[FieldFormulaValueObservation]'` |
| `read_grid` | `(self, request: 'GridFormulaReadRequest') -> 'FormulaExtensionResult[GridFormulaObservation]'` |
| `read_grid_values` | `(self, request: 'GridFormulaValueReadRequest') -> 'FormulaExtensionResult[GridFormulaValueObservation]'` |
| `recalculate_field` | `(self, request: 'FieldFormulaRecalculateRequest') -> 'FormulaExtensionResult[RecalculationObservation]'` |
| `recalculate_grid` | `(self, request: 'GridFormulaRecalculateRequest') -> 'FormulaExtensionResult[RecalculationObservation]'` |
| `set_field` | `(self, request: 'FieldFormulaSetRequest') -> 'FormulaExtensionResult[FormulaMutation]'` |
| `set_grid` | `(self, request: 'GridFormulaSetRequest') -> 'FormulaExtensionResult[FormulaMutation]'` |

### FormulaError

### FormulaErrorCode

| Member | Wire value |
| --- | --- |
| `INVALID_TARGET` | `invalid_target` |
| `UNSUPPORTED_MODE` | `unsupported_mode` |
| `UNSUPPORTED_CAPABILITY` | `unsupported_capability` |
| `TARGET_NOT_FOUND` | `target_not_found` |
| `STALE_REVISION` | `stale_revision` |
| `IDEMPOTENCY_CONFLICT` | `idempotency_conflict` |
| `RESOURCE_LIMIT` | `resource_limit` |
| `TIMEOUT` | `timeout` |
| `CANCELLED` | `cancelled` |
| `SNAPSHOT_UNAVAILABLE` | `snapshot_unavailable` |
| `EXECUTION_FAILED` | `execution_failed` |
| `PARTIAL_EFFECT` | `partial_effect` |
| `UNCERTAIN_MUTATION` | `uncertain_mutation` |
| `READBACK_MISMATCH` | `readback_mismatch` |
| `PROTOCOL_FAILURE` | `protocol_failure` |
| `CLIENT_CLOSED` | `client_closed` |
| `CLIENT_AFFINITY_MISMATCH` | `client_affinity_mismatch` |
| `INVALID_FORMULA` | `invalid_formula` |

### FormulaErrorValue

| Field | Declared type |
| --- | --- |
| `code` | `str` |

| Public member | Signature or access |
| --- | --- |
| `from_wire` | `(payload: 'Mapping[str, Any]') -> 'FormulaErrorValue'` |
| `to_wire` | `(self) -> 'dict[str, str]'` |

### FormulaExpression

| Field | Declared type |
| --- | --- |
| `dialect` | `str` |
| `text` | `str` |

| Public member | Signature or access |
| --- | --- |
| `byte_count` | `property (read-only)` |
| `from_wire` | `(payload: 'Mapping[str, Any]') -> 'FormulaExpression'` |
| `sha256` | `property (read-only)` |
| `to_wire` | `(self) -> 'dict[str, str]'` |

### FormulaExtensionErrorInfo

| Field | Declared type |
| --- | --- |
| `code` | `FormulaErrorCode` |
| `message` | `str` |
| `safe_details` | `Mapping[str, Any]` |

| Public member | Signature or access |
| --- | --- |
| `to_wire` | `(self) -> 'dict[str, Any]'` |

### FormulaExtensionResult

| Field | Declared type |
| --- | --- |
| `commit` | `FormulaCommitState` |
| `error` | `FormulaExtensionErrorInfo \| None` |
| `outcome` | `FormulaOutcome` |
| `receipts` | `tuple[object, ...]` |
| `value` | `_T \| None` |
| `verification` | `FormulaVerificationState` |

### FormulaIdempotencyDecision

| Field | Declared type |
| --- | --- |
| `disposition` | `FormulaIdempotencyDisposition` |
| `operation_hash` | `str \| None` |

### FormulaIdempotencyDisposition

| Member | Wire value |
| --- | --- |
| `STARTED` | `started` |
| `REPLAY` | `replay` |
| `CONFLICT` | `conflict` |
| `UNKNOWN` | `unknown` |
| `IN_FLIGHT` | `in_flight` |

### FormulaIdempotencyLedger

| Public member | Signature or access |
| --- | --- |
| `begin` | `(self, *, connector_id: 'str', capability: 'str', target_hash: 'str', selector_hash: 'str', idempotency_key: 'str', payload_hash: 'str') -> 'FormulaIdempotencyDecision'` |
| `fail_known` | `(self, *, connector_id: 'str', target_hash: 'str', selector_hash: 'str', idempotency_key: 'str', payload_hash: 'str', operation_hash: 'str \| None' = None) -> 'None'` |
| `mark_unknown` | `(self, *, connector_id: 'str', target_hash: 'str', selector_hash: 'str', idempotency_key: 'str', payload_hash: 'str') -> 'None'` |
| `succeed` | `(self, *, connector_id: 'str', target_hash: 'str', selector_hash: 'str', idempotency_key: 'str', payload_hash: 'str', operation_hash: 'str') -> 'None'` |

### FormulaMutation

| Field | Declared type |
| --- | --- |
| `affected_count` | `int` |
| `formula_observation` | `GridFormulaObservation \| FieldFormulaObservation` |
| `revision_after` | `str` |
| `revision_before` | `str \| None` |
| `target_kind` | `str` |

| Public member | Signature or access |
| --- | --- |
| `from_wire` | `(payload: 'Mapping[str, Any]') -> 'FormulaMutation'` |
| `to_wire` | `(self) -> 'dict[str, object]'` |

### FormulaOutcome

| Member | Wire value |
| --- | --- |
| `SUCCEEDED` | `succeeded` |
| `PLANNED` | `planned` |
| `REJECTED` | `rejected` |
| `FAILED` | `failed` |
| `PARTIAL` | `partial` |
| `UNKNOWN` | `unknown` |

### FormulaReceiptDetails

| Field | Declared type |
| --- | --- |
| `affected_count` | `int \| None` |
| `calculation_state` | `str \| None` |
| `calculation_trigger` | `str \| None` |
| `capability` | `str` |
| `copy_fill_policy` | `str \| None` |
| `dependency_scope` | `str \| None` |
| `dialect` | `str` |
| `expression_sha256` | `str \| None` |
| `mutation_atomicity` | `str \| None` |
| `observation_sha256` | `str \| None` |
| `observed_count` | `int \| None` |
| `provider_receipt_ref` | `str \| None` |
| `revision_after` | `str \| None` |
| `revision_before` | `str \| None` |
| `revision_enforcement` | `str \| None` |
| `safe_details` | `Mapping[str, Any]` |
| `selector` | `str` |
| `table_mode` | `str` |
| `target` | `str` |
| `target_kind` | `str` |
| `value_observation_sha256` | `str \| None` |
| `verification` | `str \| None` |

| Public member | Signature or access |
| --- | --- |
| `for_field_set` | `(*, target: 'str', selector: 'str', capability: 'str', dialect: 'str', expression_sha256: 'str', observation_sha256: 'str', affected_count: 'int', revision_before: 'str \| None', revision_after: 'str', mutation_atomicity: 'str', revision_enforcement: 'str', verification: 'str') -> 'FormulaReceiptDetails'` |
| `for_field_values_read` | `(*, target: 'str', selector: 'str', capability: 'str', dialect: 'str', observation_sha256: 'str', value_observation_sha256: 'str', observed_count: 'int', revision_after: 'str \| None', calculation_state: 'str \| None', calculation_trigger: 'str \| None', dependency_scope: 'str \| None') -> 'FormulaReceiptDetails'` |
| `for_grid_read` | `(*, target: 'str', selector: 'str', capability: 'str', dialect: 'str', observation_sha256: 'str', observed_count: 'int', revision_after: 'str \| None') -> 'FormulaReceiptDetails'` |
| `for_grid_set` | `(*, target: 'str', selector: 'str', capability: 'str', dialect: 'str', expression_sha256: 'str', observation_sha256: 'str', affected_count: 'int', revision_before: 'str \| None', revision_after: 'str', mutation_atomicity: 'str', revision_enforcement: 'str', verification: 'str') -> 'FormulaReceiptDetails'` |
| `for_grid_values_read` | `(*, target: 'str', selector: 'str', capability: 'str', dialect: 'str', observation_sha256: 'str \| None', value_observation_sha256: 'str', observed_count: 'int', revision_after: 'str \| None', calculation_state: 'str \| None', calculation_trigger: 'str \| None', dependency_scope: 'str \| None') -> 'FormulaReceiptDetails'` |
| `from_wire` | `(payload: 'Mapping[str, Any]') -> 'FormulaReceiptDetails'` |
| `to_wire` | `(self) -> 'dict[str, object]'` |

### FormulaRecordValue

| Field | Declared type |
| --- | --- |
| `record_id` | `str` |
| `value` | `FormulaValue` |

| Public member | Signature or access |
| --- | --- |
| `from_wire` | `(payload: 'Mapping[str, Any]') -> 'FormulaRecordValue'` |
| `to_wire` | `(self) -> 'dict[str, object]'` |

### FormulaResourceLimits

| Field | Declared type |
| --- | --- |
| `max_cells` | `int \| None` |
| `max_expression_bytes` | `int \| None` |
| `max_records` | `int \| None` |
| `max_response_bytes` | `int \| None` |
| `timeout_seconds` | `float \| None` |

### FormulaValue

| Field | Declared type |
| --- | --- |
| `kind` | `str` |
| `logical_type` | `str \| None` |
| `value` | `object` |

| Public member | Signature or access |
| --- | --- |
| `from_python` | `(value: 'object') -> 'FormulaValue'` |
| `from_wire` | `(payload: 'Mapping[str, Any]') -> 'FormulaValue'` |
| `logical` | `(logical_type: 'str', value: 'str \| int \| float') -> 'FormulaValue'` |
| `provider_error` | `(value: 'FormulaErrorValue') -> 'FormulaValue'` |
| `to_python` | `(self) -> 'object'` |
| `to_wire` | `(self) -> 'dict[str, object]'` |

### FormulaValueCell

| Field | Declared type |
| --- | --- |
| `address` | `str` |
| `value` | `FormulaValue` |

| Public member | Signature or access |
| --- | --- |
| `from_wire` | `(payload: 'Mapping[str, Any]') -> 'FormulaValueCell'` |
| `to_wire` | `(self) -> 'dict[str, object]'` |

### FormulaVerificationState

| Member | Wire value |
| --- | --- |
| `SKIPPED` | `skipped` |
| `PASSED` | `passed` |
| `FAILED` | `failed` |
| `UNAVAILABLE` | `unavailable` |

### GridFormulaBindRequest

| Field | Declared type |
| --- | --- |
| `target` | `GridFormulaTarget` |

### GridFormulaBinding

| Field | Declared type |
| --- | --- |
| `capabilities` | `FormulaCapabilitySet` |
| `observed_revision` | `str \| None` |
| `target` | `BoundGridFormulaTarget` |

### GridFormulaConnectorExtension

| Public member | Signature or access |
| --- | --- |
| `bind_grid` | `(self, request: 'GridFormulaBindRequest') -> 'FormulaExtensionResult[GridFormulaBinding]'` |
| `read_grid` | `(self, request: 'GridFormulaReadRequest') -> 'FormulaExtensionResult[GridFormulaObservation]'` |
| `read_grid_values` | `(self, request: 'GridFormulaValueReadRequest') -> 'FormulaExtensionResult[GridFormulaValueObservation]'` |
| `recalculate_grid` | `(self, request: 'GridFormulaRecalculateRequest') -> 'FormulaExtensionResult[RecalculationObservation]'` |
| `set_grid` | `(self, request: 'GridFormulaSetRequest') -> 'FormulaExtensionResult[FormulaMutation]'` |

### GridFormulaObservation

| Field | Declared type |
| --- | --- |
| `formulas` | `tuple[FormulaCell, ...]` |
| `observed_revision` | `str` |
| `requested_range` | `str` |
| `worksheet_id` | `str` |

| Public member | Signature or access |
| --- | --- |
| `from_wire` | `(payload: 'Mapping[str, Any]') -> 'GridFormulaObservation'` |
| `to_wire` | `(self) -> 'dict[str, object]'` |

### GridFormulaReadRequest

| Field | Declared type |
| --- | --- |
| `cell_range` | `str` |
| `limits` | `FormulaResourceLimits \| None` |
| `target` | `BoundGridFormulaTarget` |

### GridFormulaRecalculateRequest

| Field | Declared type |
| --- | --- |
| `cell_range` | `str \| None` |
| `expected_revision` | `str \| None` |
| `idempotency_key` | `str \| None` |
| `limits` | `FormulaResourceLimits \| None` |
| `scope` | `GridRecalculationScope` |
| `target` | `BoundGridFormulaTarget` |

### GridFormulaSetRequest

| Field | Declared type |
| --- | --- |
| `cell_range` | `str` |
| `expected_revision` | `str \| None` |
| `expression` | `FormulaExpression` |
| `idempotency_key` | `str \| None` |
| `limits` | `FormulaResourceLimits \| None` |
| `target` | `BoundGridFormulaTarget` |

### GridFormulaTarget

| Field | Declared type |
| --- | --- |
| `grid` | `TableURI \| str` |
| `worksheet` | `WorksheetRef` |

### GridFormulaValueObservation

| Field | Declared type |
| --- | --- |
| `calculation_state` | `CalculationState` |
| `calculation_trigger` | `CalculationTrigger` |
| `dependency_scope` | `str` |
| `observed_revision` | `str` |
| `requested_range` | `str` |
| `values` | `tuple[FormulaValueCell, ...]` |
| `worksheet_id` | `str` |

| Public member | Signature or access |
| --- | --- |
| `from_wire` | `(payload: 'Mapping[str, Any]') -> 'GridFormulaValueObservation'` |
| `to_wire` | `(self) -> 'dict[str, object]'` |

### GridFormulaValueReadRequest

| Field | Declared type |
| --- | --- |
| `cell_range` | `str` |
| `limits` | `FormulaResourceLimits \| None` |
| `target` | `BoundGridFormulaTarget` |

### GridRecalculationScope

| Member | Wire value |
| --- | --- |
| `RANGE` | `range` |
| `WORKSHEET` | `worksheet` |
| `WORKBOOK` | `workbook` |

### IdempotencyStrength

| Member | Wire value |
| --- | --- |
| `PROVIDER` | `provider` |
| `HOST_LEDGER` | `host_ledger` |
| `RECONCILED` | `reconciled` |

### MutationAtomicity

| Member | Wire value |
| --- | --- |
| `ATOMIC` | `atomic` |
| `PARTIAL_REPORTED` | `partial_reported` |
| `UNKNOWN` | `unknown` |

### RecalculationObservation

| Field | Declared type |
| --- | --- |
| `calculation_state` | `CalculationState` |
| `effective_scope` | `str` |
| `provider_status` | `str` |
| `requested_scope` | `str` |
| `revision_after` | `str \| None` |
| `revision_before` | `str \| None` |
| `target_kind` | `str` |
| `value_observation` | `GridFormulaValueObservation \| FieldFormulaValueObservation \| None` |
| `verification` | `str` |

| Public member | Signature or access |
| --- | --- |
| `from_wire` | `(payload: 'Mapping[str, Any]') -> 'RecalculationObservation'` |
| `to_wire` | `(self) -> 'dict[str, object]'` |

### RevisionEnforcement

| Member | Wire value |
| --- | --- |
| `ATOMIC` | `atomic` |
| `CHECKED` | `checked` |
| `UNAVAILABLE` | `unavailable` |

### WorksheetRef

| Field | Declared type |
| --- | --- |
| `name` | `str \| None` |
| `worksheet_id` | `str \| None` |

## open_table_connector.timeseries

| Name | Kind | Definition |
| --- | --- | --- |
| `ALL_CAPABILITIES` | constant | `tuple; inspect via this named export`  |
| `AbortDisposition` | enum | `(value, names=None, *, module=None, qualname=None, type=None, start=1, boundary=None)` [source](../../packages/timeseries/src/open_table_connector/timeseries/receipts.py) |
| `AggregateFunction` | enum | `(value, names=None, *, module=None, qualname=None, type=None, start=1, boundary=None)` [source](../../packages/timeseries/src/open_table_connector/timeseries/plan.py) |
| `AggregateMeasure` | class | `(output_field: 'str', function: 'AggregateFunction', value_field: 'str \| None') -> None` [source](../../packages/timeseries/src/open_table_connector/timeseries/plan.py) |
| `ArrowArtifactReference` | class | `(relative_path: 'str', sha256: 'str', size_bytes: 'int', media_type: 'str' = 'application/vnd.apache.arrow.stream') -> None` [source](../../packages/timeseries/src/open_table_connector/timeseries/storage.py) |
| `ArrowEvidence` | class | `(table: 'pa.Table', ipc_bytes: 'bytes', schema_fingerprint: 'str', content_fingerprint: 'str') -> None` [source](../../packages/timeseries/src/open_table_connector/timeseries/evaluator.py) |
| `AsOf` | class | `(at: 'str', projection: 'tuple[str, ...]', tag_predicates: 'tuple[TagPredicate, ...]') -> None` [source](../../packages/timeseries/src/open_table_connector/timeseries/plan.py) |
| `BucketAggregate` | class | `(start: 'str', end: 'str', bucket: 'Bucket', group_by: 'tuple[str, ...]', measures: 'tuple[AggregateMeasure, ...]', tag_predicates: 'tuple[TagPredicate, ...]') -> None` [source](../../packages/timeseries/src/open_table_connector/timeseries/plan.py) |
| `CalendarBucket` | class | `(count: 'int', unit: 'CalendarUnit', timezone: 'str', week_start: 'int', origin: 'str', offset_ns: 'int' = 0) -> None` [source](../../packages/timeseries/src/open_table_connector/timeseries/plan.py) |
| `CalendarUnit` | enum | `(value, names=None, *, module=None, qualname=None, type=None, start=1, boundary=None)` [source](../../packages/timeseries/src/open_table_connector/timeseries/plan.py) |
| `DuplicatePolicy` | enum | `(value, names=None, *, module=None, qualname=None, type=None, start=1, boundary=None)` [source](../../packages/timeseries/src/open_table_connector/timeseries/descriptor.py) |
| `ExecutionLocation` | enum | `(value, names=None, *, module=None, qualname=None, type=None, start=1, boundary=None)` [source](../../packages/timeseries/src/open_table_connector/timeseries/receipts.py) |
| `FillMode` | enum | `(value, names=None, *, module=None, qualname=None, type=None, start=1, boundary=None)` [source](../../packages/timeseries/src/open_table_connector/timeseries/plan.py) |
| `FillRule` | class | `(field: 'str', mode: 'FillMode', value: 'JsonScalar') -> None` [source](../../packages/timeseries/src/open_table_connector/timeseries/plan.py) |
| `FixedBucket` | class | `(width_ns: 'int', origin: 'str', offset_ns: 'int' = 0) -> None` [source](../../packages/timeseries/src/open_table_connector/timeseries/plan.py) |
| `GapFill` | class | `(start: 'str', end: 'str', bucket: 'Bucket', group_by: 'tuple[str, ...]', measures: 'tuple[AggregateMeasure, ...]', tag_predicates: 'tuple[TagPredicate, ...]', fills: 'tuple[FillRule, ...]') -> None` [source](../../packages/timeseries/src/open_table_connector/timeseries/plan.py) |
| `Latest` | class | `(at_or_before: 'str \| None', projection: 'tuple[str, ...]', tag_predicates: 'tuple[TagPredicate, ...]') -> None` [source](../../packages/timeseries/src/open_table_connector/timeseries/plan.py) |
| `ManagedAbortReceipt` | class | `(schema_version: 'str', operation_id: 'str', logical_target: 'TableURI', stage_id: 'str', disposition: 'AbortDisposition', aborted_at: 'str') -> None` [source](../../packages/timeseries/src/open_table_connector/timeseries/receipts.py) |
| `ManagedAbortRequest` | class | `(operation_id: 'str', logical_target: 'TableURI', stage_id: 'str', credential_values: 'Mapping[str, str]' = <factory>) -> None` [source](../../packages/timeseries/src/open_table_connector/timeseries/storage.py) |
| `ManagedCommitReceipt` | class | `(schema_version: 'str', operation_id: 'str', logical_target: 'TableURI', stage_id: 'str', idempotency_key: 'str', snapshot_id: 'str', snapshot_reference: 'str', committed_at: 'str', visibility: 'VisibilityGuarantee') -> None` [source](../../packages/timeseries/src/open_table_connector/timeseries/receipts.py) |
| `ManagedCommitRequest` | class | `(operation_id: 'str', logical_target: 'TableURI', stage_id: 'str', idempotency_key: 'str', resource_bounds: 'ResourceBounds', credential_values: 'Mapping[str, str]' = <factory>) -> None` [source](../../packages/timeseries/src/open_table_connector/timeseries/storage.py) |
| `ManagedCurrentRequest` | class | `(logical_target: 'TableURI', descriptor_hash: 'str') -> None` [source](../../packages/timeseries/src/open_table_connector/timeseries/storage.py) |
| `ManagedCurrentResult` | class | `(snapshot_id: 'str', snapshot_reference: 'str', committed_at: 'str', descriptor_hash: 'str', schema: 'pa.Schema') -> None` [source](../../packages/timeseries/src/open_table_connector/timeseries/storage.py) |
| `ManagedReadbackReceipt` | class | `(schema_version: 'str', operation_id: 'str', snapshot_id: 'str', observed_at: 'str', observed_schema_hash: 'str', observed_content_hash: 'str', observed_rows: 'int', observed_bytes: 'int', observed_range: 'TimeRange \| None') -> None` [source](../../packages/timeseries/src/open_table_connector/timeseries/receipts.py) |
| `ManagedReadbackRequest` | class | `(operation_id: 'str', logical_target: 'TableURI', snapshot_id: 'str', snapshot_reference: 'str', resource_bounds: 'ResourceBounds', credential_values: 'Mapping[str, str]' = <factory>) -> None` [source](../../packages/timeseries/src/open_table_connector/timeseries/storage.py) |
| `ManagedReadbackResult` | class | `(table: 'pa.Table \| None', artifact: 'ArrowArtifactReference \| None', receipt: 'ManagedReadbackReceipt') -> None` [source](../../packages/timeseries/src/open_table_connector/timeseries/storage.py) |
| `ManagedStageReceipt` | class | `(schema_version: 'str', operation_id: 'str', logical_target: 'TableURI', physical_target: 'TableURI', stage_id: 'str', idempotency_key: 'str', artifact_hash: 'str', descriptor_hash: 'str', staged_at: 'str', visible: 'bool') -> None` [source](../../packages/timeseries/src/open_table_connector/timeseries/receipts.py) |
| `ManagedStageRequest` | class | `(operation_id: 'str', artifact: 'ArrowArtifactReference', descriptor_hash: 'str', logical_target: 'TableURI', physical_target: 'TableURI', idempotency_key: 'str', resource_bounds: 'ResourceBounds', credential_values: 'Mapping[str, str]' = <factory>) -> None` [source](../../packages/timeseries/src/open_table_connector/timeseries/storage.py) |
| `ManagedTemporalStore` | class | `(*args, **kwargs)` [source](../../packages/timeseries/src/open_table_connector/timeseries/storage.py) |
| `OrderDirection` | enum | `(value, names=None, *, module=None, qualname=None, type=None, start=1, boundary=None)` [source](../../packages/timeseries/src/open_table_connector/timeseries/plan.py) |
| `OrderKey` | class | `(field: 'str', direction: 'OrderDirection') -> None` [source](../../packages/timeseries/src/open_table_connector/timeseries/plan.py) |
| `PolarsTemporalExecutor` | class | `(source: 'TemporalSource', *, connector_identity: 'ConnectorIdentity \| None' = None) -> 'None'` [source](../../packages/timeseries/src/open_table_connector/timeseries/evaluator.py) |
| `PortableTemporalExecutor` | class | `(*args, **kwargs)` [source](../../packages/timeseries/src/open_table_connector/timeseries/storage.py) |
| `PortableTemporalPlan` | class | `(schema_version: 'str', descriptor_hash: 'str', relation: 'str', required_capabilities: 'tuple[str, ...]', resource_bounds: 'ResourceBounds', operation: 'TemporalOperation', output_order: 'tuple[OrderKey, ...]', result_row_limit: 'int \| None') -> None` [source](../../packages/timeseries/src/open_table_connector/timeseries/plan.py) |
| `PreparedTemporalQuery` | class | `(statement: 'str', parameters: 'tuple[object, ...]', residual_plan: 'PortableTemporalPlan \| None') -> None` [source](../../packages/timeseries/src/open_table_connector/timeseries/lowering.py) |
| `ResourceBounds` | class | `(max_rows: 'int', max_bytes: 'int', max_duration_ms: 'int') -> None` [source](../../packages/timeseries/src/open_table_connector/timeseries/plan.py) |
| `ScanRange` | class | `(start: 'str', end: 'str', projection: 'tuple[str, ...]', tag_predicates: 'tuple[TagPredicate, ...]') -> None` [source](../../packages/timeseries/src/open_table_connector/timeseries/plan.py) |
| `TagOperator` | enum | `(value, names=None, *, module=None, qualname=None, type=None, start=1, boundary=None)` [source](../../packages/timeseries/src/open_table_connector/timeseries/plan.py) |
| `TagPredicate` | class | `(field: 'str', operator: 'TagOperator', values: 'tuple[JsonScalar, ...]') -> None` [source](../../packages/timeseries/src/open_table_connector/timeseries/plan.py) |
| `TemporalErrorCode` | enum | `(value, names=None, *, module=None, qualname=None, type=None, start=1, boundary=None)` [source](../../packages/contract/src/open_table_connector/contract/errors.py) |
| `TemporalExecutionRequest` | class | `(target: 'TableURI', plan: 'PortableTemporalPlan', credential_reference: 'str \| None', operation_id: 'str', snapshot_reference: 'str \| None', credential_values: 'Mapping[str, str]' = <factory>) -> None` [source](../../packages/timeseries/src/open_table_connector/timeseries/storage.py) |
| `TemporalExecutionResult` | class | `(table: 'pa.Table \| None', artifact: 'ArrowArtifactReference \| None', receipt: 'TemporalReceipt \| None') -> None` [source](../../packages/timeseries/src/open_table_connector/timeseries/storage.py) |
| `TemporalExtensionError` | class | `(code: 'TemporalErrorCode', message: 'str', safe_details: 'Mapping[str, object] \| None' = None) -> 'None'` [source](../../packages/timeseries/src/open_table_connector/timeseries/storage.py) |
| `TemporalOrdering` | enum | `(value, names=None, *, module=None, qualname=None, type=None, start=1, boundary=None)` [source](../../packages/timeseries/src/open_table_connector/timeseries/descriptor.py) |
| `TemporalReceipt` | class | `(schema_version: 'str', neutral_receipt: 'NeutralReceipt', descriptor_hash: 'str', requested_range: 'TimeRange \| None', observed_range: 'TimeRange \| None', output_order: 'tuple[OrderKey, ...]', execution_location: 'ExecutionLocation', resource_bounds: 'ResourceBounds', examined_rows: 'int', examined_bytes: 'int', returned_rows: 'int', returned_bytes: 'int', elapsed_ms: 'int', snapshot_reference: 'str \| None', plan_schema_version: 'str', portable_plan_hash: 'str') -> None` [source](../../packages/timeseries/src/open_table_connector/timeseries/receipts.py) |
| `TemporalSource` | class | `(*args, **kwargs)` [source](../../packages/timeseries/src/open_table_connector/timeseries/evaluator.py) |
| `TemporalTableDescriptor` | class | `(time_field: 'str', timezone: 'str', precision: 'TimestampPrecision', series_key_fields: 'tuple[str, ...]', tag_fields: 'tuple[str, ...]', value_fields: 'tuple[str, ...]', ingestion_time_field: 'str \| None', duplicate_policy: 'DuplicatePolicy', ordering: 'TemporalOrdering') -> None` [source](../../packages/timeseries/src/open_table_connector/timeseries/descriptor.py) |
| `TimeRange` | class | `(start: 'str', end: 'str') -> None` [source](../../packages/timeseries/src/open_table_connector/timeseries/receipts.py) |
| `TimestampPrecision` | enum | `(value, names=None, *, module=None, qualname=None, type=None, start=1, boundary=None)` [source](../../packages/timeseries/src/open_table_connector/timeseries/descriptor.py) |
| `VerifiedArtifact` | class | `(data: 'bytes', table: 'pa.Table', observed_range: 'TimeRange \| None' = None) -> None` [source](../../packages/timeseries/src/open_table_connector/timeseries/artifacts.py) |
| `VisibilityGuarantee` | enum | `(value, names=None, *, module=None, qualname=None, type=None, start=1, boundary=None)` [source](../../packages/timeseries/src/open_table_connector/timeseries/receipts.py) |
| `arrow_time_bounds` | function | `(table: 'pa.Table', field: 'str', precision: 'TimestampPrecision') -> 'tuple[str, str] \| None'` [source](../../packages/timeseries/src/open_table_connector/timeseries/precision.py) |
| `build_arrow_evidence` | function | `(table: 'pa.Table') -> 'ArrowEvidence'` [source](../../packages/timeseries/src/open_table_connector/timeseries/evaluator.py) |
| `calendar_bucket_start` | function | `(timestamp: 'str', bucket: 'CalendarBucket') -> 'str'` [source](../../packages/timeseries/src/open_table_connector/timeseries/buckets.py) |
| `descriptor_from_wire` | function | `(document: 'Mapping[str, object]') -> 'TemporalTableDescriptor'` [source](../../packages/timeseries/src/open_table_connector/timeseries/descriptor.py) |
| `fixed_bucket_start` | function | `(timestamp_ns: 'int', width_ns: 'int', origin_ns: 'int', offset_ns: 'int' = 0) -> 'int'` [source](../../packages/timeseries/src/open_table_connector/timeseries/buckets.py) |
| `plan_from_wire` | function | `(document: 'Mapping[str, object]') -> 'PortableTemporalPlan'` [source](../../packages/timeseries/src/open_table_connector/timeseries/plan.py) |
| `portable_plan_hash` | function | `(plan: 'PortableTemporalPlan') -> 'str'` [source](../../packages/timeseries/src/open_table_connector/timeseries/plan.py) |
| `read_verified_artifact` | function | `(reference: 'ArrowArtifactReference', artifact_root: 'Path', bounds: 'ResourceBounds', descriptor: 'TemporalTableDescriptor \| None' = None) -> 'VerifiedArtifact'` [source](../../packages/timeseries/src/open_table_connector/timeseries/artifacts.py) |
| `storage_to_timestamp` | function | `(value: 'int', precision: 'TimestampPrecision') -> 'str'` [source](../../packages/timeseries/src/open_table_connector/timeseries/precision.py) |
| `temporal_descriptor_hash` | function | `(descriptor: 'TemporalTableDescriptor', arrow_schema: 'pa.Schema') -> 'str'` [source](../../packages/timeseries/src/open_table_connector/timeseries/descriptor.py) |
| `timestamp_to_storage` | function | `(value: 'str', precision: 'TimestampPrecision') -> 'int'` [source](../../packages/timeseries/src/open_table_connector/timeseries/precision.py) |
| `validate_plan_for_descriptor` | function | `(plan: 'PortableTemporalPlan', descriptor: 'TemporalTableDescriptor') -> 'None'` [source](../../packages/timeseries/src/open_table_connector/timeseries/plan.py) |
| `validate_stage_retry` | function | `(existing: 'ManagedStageReceipt', request: 'ManagedStageRequest') -> 'ManagedStageReceipt'` [source](../../packages/timeseries/src/open_table_connector/timeseries/storage.py) |

### AbortDisposition

| Member | Wire value |
| --- | --- |
| `REMOVED` | `removed` |
| `ALREADY_ABSENT` | `already_absent` |
| `ALREADY_COMMITTED` | `already_committed` |

### AggregateFunction

| Member | Wire value |
| --- | --- |
| `COUNT` | `count` |
| `MIN` | `min` |
| `MAX` | `max` |
| `SUM` | `sum` |
| `AVG` | `avg` |
| `FIRST` | `first` |
| `LAST` | `last` |

### AggregateMeasure

| Field | Declared type |
| --- | --- |
| `function` | `AggregateFunction` |
| `output_field` | `str` |
| `value_field` | `str \| None` |

| Public member | Signature or access |
| --- | --- |
| `to_wire` | `(self) -> 'dict[str, object]'` |

### ArrowArtifactReference

| Field | Declared type |
| --- | --- |
| `media_type` | `str` |
| `relative_path` | `str` |
| `sha256` | `str` |
| `size_bytes` | `int` |

| Public member | Signature or access |
| --- | --- |
| `to_wire` | `(self) -> 'dict[str, object]'` |

### ArrowEvidence

| Field | Declared type |
| --- | --- |
| `content_fingerprint` | `str` |
| `ipc_bytes` | `bytes` |
| `schema_fingerprint` | `str` |
| `table` | `pa.Table` |

### AsOf

| Field | Declared type |
| --- | --- |
| `at` | `str` |
| `projection` | `tuple[str, ...]` |
| `tag_predicates` | `tuple[TagPredicate, ...]` |

| Public member | Signature or access |
| --- | --- |
| `to_wire` | `(self) -> 'dict[str, object]'` |

### BucketAggregate

| Field | Declared type |
| --- | --- |
| `bucket` | `Bucket` |
| `end` | `str` |
| `group_by` | `tuple[str, ...]` |
| `measures` | `tuple[AggregateMeasure, ...]` |
| `start` | `str` |
| `tag_predicates` | `tuple[TagPredicate, ...]` |

| Public member | Signature or access |
| --- | --- |
| `to_wire` | `(self) -> 'dict[str, object]'` |

### CalendarBucket

| Field | Declared type |
| --- | --- |
| `count` | `int` |
| `offset_ns` | `int` |
| `origin` | `str` |
| `timezone` | `str` |
| `unit` | `CalendarUnit` |
| `week_start` | `int` |

| Public member | Signature or access |
| --- | --- |
| `to_wire` | `(self) -> 'dict[str, object]'` |

### CalendarUnit

| Member | Wire value |
| --- | --- |
| `DAY` | `day` |
| `WEEK` | `week` |
| `MONTH` | `month` |
| `QUARTER` | `quarter` |
| `YEAR` | `year` |

### DuplicatePolicy

| Member | Wire value |
| --- | --- |
| `PRESERVE` | `preserve` |
| `REJECT` | `reject` |
| `REPLACE_LATEST` | `replace-latest` |

### ExecutionLocation

| Member | Wire value |
| --- | --- |
| `PROVIDER` | `provider` |
| `CONNECTOR` | `connector` |

### FillMode

| Member | Wire value |
| --- | --- |
| `NULL` | `null` |
| `CONSTANT` | `constant` |
| `LOCF` | `locf` |
| `LINEAR` | `linear` |

### FillRule

| Field | Declared type |
| --- | --- |
| `field` | `str` |
| `mode` | `FillMode` |
| `value` | `JsonScalar` |

| Public member | Signature or access |
| --- | --- |
| `to_wire` | `(self) -> 'dict[str, object]'` |

### FixedBucket

| Field | Declared type |
| --- | --- |
| `offset_ns` | `int` |
| `origin` | `str` |
| `width_ns` | `int` |

| Public member | Signature or access |
| --- | --- |
| `to_wire` | `(self) -> 'dict[str, object]'` |

### GapFill

| Field | Declared type |
| --- | --- |
| `bucket` | `Bucket` |
| `end` | `str` |
| `fills` | `tuple[FillRule, ...]` |
| `group_by` | `tuple[str, ...]` |
| `measures` | `tuple[AggregateMeasure, ...]` |
| `start` | `str` |
| `tag_predicates` | `tuple[TagPredicate, ...]` |

| Public member | Signature or access |
| --- | --- |
| `to_wire` | `(self) -> 'dict[str, object]'` |

### Latest

| Field | Declared type |
| --- | --- |
| `at_or_before` | `str \| None` |
| `projection` | `tuple[str, ...]` |
| `tag_predicates` | `tuple[TagPredicate, ...]` |

| Public member | Signature or access |
| --- | --- |
| `to_wire` | `(self) -> 'dict[str, object]'` |

### ManagedAbortReceipt

| Field | Declared type |
| --- | --- |
| `aborted_at` | `str` |
| `disposition` | `AbortDisposition` |
| `logical_target` | `TableURI` |
| `operation_id` | `str` |
| `schema_version` | `str` |
| `stage_id` | `str` |

| Public member | Signature or access |
| --- | --- |
| `from_wire` | `(document: 'Mapping[str, object]') -> 'ManagedAbortReceipt'` |
| `to_wire` | `(self) -> 'dict[str, object]'` |

### ManagedAbortRequest

| Field | Declared type |
| --- | --- |
| `credential_values` | `Mapping[str, str]` |
| `logical_target` | `TableURI` |
| `operation_id` | `str` |
| `stage_id` | `str` |

### ManagedCommitReceipt

| Field | Declared type |
| --- | --- |
| `committed_at` | `str` |
| `idempotency_key` | `str` |
| `logical_target` | `TableURI` |
| `operation_id` | `str` |
| `schema_version` | `str` |
| `snapshot_id` | `str` |
| `snapshot_reference` | `str` |
| `stage_id` | `str` |
| `visibility` | `VisibilityGuarantee` |

| Public member | Signature or access |
| --- | --- |
| `from_wire` | `(document: 'Mapping[str, object]') -> 'ManagedCommitReceipt'` |
| `to_wire` | `(self) -> 'dict[str, object]'` |

### ManagedCommitRequest

| Field | Declared type |
| --- | --- |
| `credential_values` | `Mapping[str, str]` |
| `idempotency_key` | `str` |
| `logical_target` | `TableURI` |
| `operation_id` | `str` |
| `resource_bounds` | `ResourceBounds` |
| `stage_id` | `str` |

### ManagedCurrentRequest

| Field | Declared type |
| --- | --- |
| `descriptor_hash` | `str` |
| `logical_target` | `TableURI` |

### ManagedCurrentResult

| Field | Declared type |
| --- | --- |
| `committed_at` | `str` |
| `descriptor_hash` | `str` |
| `schema` | `pa.Schema` |
| `snapshot_id` | `str` |
| `snapshot_reference` | `str` |

### ManagedReadbackReceipt

| Field | Declared type |
| --- | --- |
| `observed_at` | `str` |
| `observed_bytes` | `int` |
| `observed_content_hash` | `str` |
| `observed_range` | `TimeRange \| None` |
| `observed_rows` | `int` |
| `observed_schema_hash` | `str` |
| `operation_id` | `str` |
| `schema_version` | `str` |
| `snapshot_id` | `str` |

| Public member | Signature or access |
| --- | --- |
| `from_wire` | `(document: 'Mapping[str, object]') -> 'ManagedReadbackReceipt'` |
| `to_wire` | `(self) -> 'dict[str, object]'` |

### ManagedReadbackRequest

| Field | Declared type |
| --- | --- |
| `credential_values` | `Mapping[str, str]` |
| `logical_target` | `TableURI` |
| `operation_id` | `str` |
| `resource_bounds` | `ResourceBounds` |
| `snapshot_id` | `str` |
| `snapshot_reference` | `str` |

### ManagedReadbackResult

| Field | Declared type |
| --- | --- |
| `artifact` | `ArrowArtifactReference \| None` |
| `receipt` | `ManagedReadbackReceipt` |
| `table` | `pa.Table \| None` |

### ManagedStageReceipt

| Field | Declared type |
| --- | --- |
| `artifact_hash` | `str` |
| `descriptor_hash` | `str` |
| `idempotency_key` | `str` |
| `logical_target` | `TableURI` |
| `operation_id` | `str` |
| `physical_target` | `TableURI` |
| `schema_version` | `str` |
| `stage_id` | `str` |
| `staged_at` | `str` |
| `visible` | `bool` |

| Public member | Signature or access |
| --- | --- |
| `from_wire` | `(document: 'Mapping[str, object]') -> 'ManagedStageReceipt'` |
| `to_wire` | `(self) -> 'dict[str, object]'` |

### ManagedStageRequest

| Field | Declared type |
| --- | --- |
| `artifact` | `ArrowArtifactReference` |
| `credential_values` | `Mapping[str, str]` |
| `descriptor_hash` | `str` |
| `idempotency_key` | `str` |
| `logical_target` | `TableURI` |
| `operation_id` | `str` |
| `physical_target` | `TableURI` |
| `resource_bounds` | `ResourceBounds` |

### ManagedTemporalStore

| Public member | Signature or access |
| --- | --- |
| `abort` | `(self, request: 'ManagedAbortRequest') -> 'ManagedAbortReceipt'` |
| `commit` | `(self, request: 'ManagedCommitRequest') -> 'ManagedCommitReceipt'` |
| `readback` | `(self, request: 'ManagedReadbackRequest') -> 'ManagedReadbackResult'` |
| `stage` | `(self, request: 'ManagedStageRequest') -> 'ManagedStageReceipt'` |

### OrderDirection

| Member | Wire value |
| --- | --- |
| `ASC` | `asc` |
| `DESC` | `desc` |

### OrderKey

| Field | Declared type |
| --- | --- |
| `direction` | `OrderDirection` |
| `field` | `str` |

| Public member | Signature or access |
| --- | --- |
| `to_wire` | `(self) -> 'dict[str, str]'` |

### PolarsTemporalExecutor

| Public member | Signature or access |
| --- | --- |
| `execute` | `(self, request: 'TemporalExecutionRequest') -> 'TemporalExecutionResult'` |

### PortableTemporalExecutor

| Public member | Signature or access |
| --- | --- |
| `execute` | `(self, request: 'TemporalExecutionRequest') -> 'TemporalExecutionResult'` |

### PortableTemporalPlan

| Field | Declared type |
| --- | --- |
| `descriptor_hash` | `str` |
| `operation` | `TemporalOperation` |
| `output_order` | `tuple[OrderKey, ...]` |
| `relation` | `str` |
| `required_capabilities` | `tuple[str, ...]` |
| `resource_bounds` | `ResourceBounds` |
| `result_row_limit` | `int \| None` |
| `schema_version` | `str` |

| Public member | Signature or access |
| --- | --- |
| `to_wire` | `(self) -> 'dict[str, object]'` |

### PreparedTemporalQuery

| Field | Declared type |
| --- | --- |
| `parameters` | `tuple[object, ...]` |
| `residual_plan` | `PortableTemporalPlan \| None` |
| `statement` | `str` |

### ResourceBounds

| Field | Declared type |
| --- | --- |
| `max_bytes` | `int` |
| `max_duration_ms` | `int` |
| `max_rows` | `int` |

| Public member | Signature or access |
| --- | --- |
| `to_wire` | `(self) -> 'dict[str, int]'` |

### ScanRange

| Field | Declared type |
| --- | --- |
| `end` | `str` |
| `projection` | `tuple[str, ...]` |
| `start` | `str` |
| `tag_predicates` | `tuple[TagPredicate, ...]` |

| Public member | Signature or access |
| --- | --- |
| `to_wire` | `(self) -> 'dict[str, object]'` |

### TagOperator

| Member | Wire value |
| --- | --- |
| `EQ` | `eq` |
| `IN` | `in` |

### TagPredicate

| Field | Declared type |
| --- | --- |
| `field` | `str` |
| `operator` | `TagOperator` |
| `values` | `tuple[JsonScalar, ...]` |

| Public member | Signature or access |
| --- | --- |
| `to_wire` | `(self) -> 'dict[str, object]'` |

### TemporalErrorCode

| Member | Wire value |
| --- | --- |
| `INVALID_URI` | `invalid_uri` |
| `UNSUPPORTED_CAPABILITY` | `unsupported_capability` |
| `AUTHENTICATION` | `authentication` |
| `CONFLICT` | `conflict` |
| `TIMEOUT` | `timeout` |
| `CANCELLED` | `cancelled` |
| `EXECUTION_FAILED` | `execution_failed` |
| `READBACK_MISMATCH` | `readback_mismatch` |
| `PROTOCOL_INVALID` | `protocol_invalid` |
| `PROTOCOL_VERSION_UNSUPPORTED` | `protocol_version_unsupported` |
| `RESOURCE_LIMIT_EXCEEDED` | `resource_limit_exceeded` |
| `SNAPSHOT_UNAVAILABLE` | `snapshot_unavailable` |
| `IDEMPOTENCY_CONFLICT` | `idempotency_conflict` |
| `VISIBILITY_INCOMPLETE` | `visibility_incomplete` |
| `CONFIGURATION` | `configuration` |

### TemporalExecutionRequest

| Field | Declared type |
| --- | --- |
| `credential_reference` | `str \| None` |
| `credential_values` | `Mapping[str, str]` |
| `operation_id` | `str` |
| `plan` | `PortableTemporalPlan` |
| `snapshot_reference` | `str \| None` |
| `target` | `TableURI` |

### TemporalExecutionResult

| Field | Declared type |
| --- | --- |
| `artifact` | `ArrowArtifactReference \| None` |
| `receipt` | `TemporalReceipt \| None` |
| `table` | `pa.Table \| None` |

### TemporalExtensionError

### TemporalOrdering

| Member | Wire value |
| --- | --- |
| `UNSPECIFIED` | `unspecified` |
| `NONDECREASING` | `nondecreasing` |
| `STRICT` | `strict` |

### TemporalReceipt

| Field | Declared type |
| --- | --- |
| `descriptor_hash` | `str` |
| `elapsed_ms` | `int` |
| `examined_bytes` | `int` |
| `examined_rows` | `int` |
| `execution_location` | `ExecutionLocation` |
| `neutral_receipt` | `NeutralReceipt` |
| `observed_range` | `TimeRange \| None` |
| `output_order` | `tuple[OrderKey, ...]` |
| `plan_schema_version` | `str` |
| `portable_plan_hash` | `str` |
| `requested_range` | `TimeRange \| None` |
| `resource_bounds` | `ResourceBounds` |
| `returned_bytes` | `int` |
| `returned_rows` | `int` |
| `schema_version` | `str` |
| `snapshot_reference` | `str \| None` |

| Public member | Signature or access |
| --- | --- |
| `from_wire` | `(document: 'Mapping[str, object]') -> 'TemporalReceipt'` |
| `to_wire` | `(self) -> 'dict[str, object]'` |

### TemporalSource

| Field | Declared type |
| --- | --- |
| `descriptor` | `TemporalTableDescriptor` |

| Public member | Signature or access |
| --- | --- |
| `read_bounded` | `(self, target: 'TableURI', projection: 'tuple[str, ...]', predicates: 'tuple[TagPredicate, ...]', bounds: 'ResourceBounds') -> 'pa.Table'` |

### TemporalTableDescriptor

| Field | Declared type |
| --- | --- |
| `duplicate_policy` | `DuplicatePolicy` |
| `ingestion_time_field` | `str \| None` |
| `ordering` | `TemporalOrdering` |
| `precision` | `TimestampPrecision` |
| `series_key_fields` | `tuple[str, ...]` |
| `tag_fields` | `tuple[str, ...]` |
| `time_field` | `str` |
| `timezone` | `str` |
| `value_fields` | `tuple[str, ...]` |

| Public member | Signature or access |
| --- | --- |
| `declared_fields` | `property (read-only)` |
| `to_wire` | `(self) -> 'dict[str, object]'` |

### TimeRange

| Field | Declared type |
| --- | --- |
| `end` | `str` |
| `start` | `str` |

| Public member | Signature or access |
| --- | --- |
| `from_wire` | `(document: 'Mapping[str, object]') -> 'TimeRange'` |
| `to_wire` | `(self) -> 'dict[str, str]'` |

### TimestampPrecision

| Member | Wire value |
| --- | --- |
| `SECOND` | `second` |
| `MILLISECOND` | `millisecond` |
| `MICROSECOND` | `microsecond` |
| `NANOSECOND` | `nanosecond` |

### VerifiedArtifact

| Field | Declared type |
| --- | --- |
| `data` | `bytes` |
| `observed_range` | `TimeRange \| None` |
| `table` | `pa.Table` |

### VisibilityGuarantee

| Member | Wire value |
| --- | --- |
| `ATOMIC` | `atomic` |
| `NON_ATOMIC` | `non_atomic` |

## open_table_connector.artifacts

| Name | Kind | Definition |
| --- | --- | --- |
| `ArtifactAdapter` | class | `(*args, **kwargs)` [source](../../packages/artifacts/src/open_table_connector/artifacts/protocols.py) |
| `ArtifactValue` | class | `(uri: 'str', media_type: 'str', content_hash: 'str', engine: 'str', coverage: 'tuple[str, ...]' = ()) -> None` [source](../../packages/artifacts/src/open_table_connector/artifacts/model.py) |
| `ExportRequest` | class | `(source_uri: 'str', destination_uri: 'str', engine: 'str', spec: 'Mapping[str, object]') -> None` [source](../../packages/artifacts/src/open_table_connector/artifacts/model.py) |
| `ViewRequest` | class | `(source: 'TargetSelector', mode: 'str', destination_uri: 'str \| None' = None, selector: 'Mapping[str, object]' = <factory>) -> None` [source](../../packages/artifacts/src/open_table_connector/artifacts/model.py) |
| `ViewValue` | class | `(outputs: 'tuple[Mapping[str, object], ...]', source_uri: 'str', source_hash: 'str', renderer: 'Mapping[str, object]' = <factory>) -> None` [source](../../packages/artifacts/src/open_table_connector/artifacts/model.py) |
| `WatchRequest` | class | `(action: 'str', source: 'TargetSelector \| None' = None, session_id: 'str \| None' = None, read_only_required: 'bool' = False) -> None` [source](../../packages/artifacts/src/open_table_connector/artifacts/model.py) |
| `WatchValue` | class | `(session_id: 'str', state: 'str', url: 'str \| None' = None, source_hash: 'str \| None' = None, snapshot_hash: 'str \| None' = None, editability: 'str' = 'preview_copy_only', persistence: 'str' = 'discard') -> None` [source](../../packages/artifacts/src/open_table_connector/artifacts/model.py) |
| `display_cell` | function | `(value: 'Any') -> 'str'` [source](../../packages/artifacts/src/open_table_connector/artifacts/model.py) |
| `validate_asset_path` | function | `(value: 'str') -> 'str'` [source](../../packages/artifacts/src/open_table_connector/artifacts/model.py) |

### ArtifactAdapter

| Public member | Signature or access |
| --- | --- |
| `create_table` | `(self, document_path: 'Path', rows: 'Sequence[Sequence[str]]', spec: 'Mapping[str, object]') -> 'Mapping[str, object]'` |
| `describe` | `(self) -> 'Mapping[str, object]'` |
| `observe_document` | `(self, document_path: 'Path', selectors: 'Sequence[Mapping[str, object]]') -> 'Mapping[str, object]'` |
| `render` | `(self, snapshot_path: 'Path', request: 'ViewRequest') -> 'Mapping[str, object]'` |

### ArtifactValue

| Field | Declared type |
| --- | --- |
| `content_hash` | `str` |
| `coverage` | `tuple[str, ...]` |
| `engine` | `str` |
| `media_type` | `str` |
| `uri` | `str` |

### ExportRequest

| Field | Declared type |
| --- | --- |
| `destination_uri` | `str` |
| `engine` | `str` |
| `source_uri` | `str` |
| `spec` | `Mapping[str, object]` |

### ViewRequest

| Field | Declared type |
| --- | --- |
| `destination_uri` | `str \| None` |
| `mode` | `str` |
| `selector` | `Mapping[str, object]` |
| `source` | `TargetSelector` |

### ViewValue

| Field | Declared type |
| --- | --- |
| `outputs` | `tuple[Mapping[str, object], ...]` |
| `renderer` | `Mapping[str, object]` |
| `source_hash` | `str` |
| `source_uri` | `str` |

### WatchRequest

| Field | Declared type |
| --- | --- |
| `action` | `str` |
| `read_only_required` | `bool` |
| `session_id` | `str \| None` |
| `source` | `TargetSelector \| None` |

### WatchValue

| Field | Declared type |
| --- | --- |
| `editability` | `str` |
| `persistence` | `str` |
| `session_id` | `str` |
| `snapshot_hash` | `str \| None` |
| `source_hash` | `str \| None` |
| `state` | `str` |
| `url` | `str \| None` |

## open_table_connector.officecli

| Name | Kind | Definition |
| --- | --- | --- |
| `artifact_adapter` | function | `()` [source](../../packages/officecli/src/open_table_connector/officecli/plugin.py) |

## open_table_connector.officecli.document

| Name | Kind | Definition |
| --- | --- | --- |
| `OfficeCliAdapter` | class | `(*, binary: 'str \| None' = None, browser: 'str \| None' = None)` [source](../../packages/officecli/src/open_table_connector/officecli/document.py) |

### OfficeCliAdapter

| Public member | Signature or access |
| --- | --- |
| `create_table` | `(self, document_path: 'Path', rows, spec)` |
| `describe` | `(self)` |
| `observe_document` | `(self, document_path: 'Path', selectors=())` |
| `render` | `(self, snapshot_path: 'Path', request: 'ViewRequest')` |
| `start_watch` | `(self, snapshot_path: 'Path')` |

## open_table_connector.officecli.process

| Name | Kind | Definition |
| --- | --- | --- |
| `ProcessResult` | class | `(returncode: 'int', stdout: 'str', stderr: 'str', truncated: 'bool' = False, timed_out: 'bool' = False) -> None` [source](../../packages/officecli/src/open_table_connector/officecli/process.py) |
| `run_officecli` | function | `(argv: 'Sequence[str]', *, input_json: 'object \| None', timeout_seconds: 'float' = 120.0, max_output_bytes: 'int' = 1048576) -> 'ProcessResult'` [source](../../packages/officecli/src/open_table_connector/officecli/process.py) |
| `runtime_environment` | function | `() -> 'dict[str, str]'` [source](../../packages/officecli/src/open_table_connector/officecli/process.py) |
| `stop_process` | function | `(process) -> 'None'` [source](../../packages/officecli/src/open_table_connector/officecli/process.py) |

### ProcessResult

| Field | Declared type |
| --- | --- |
| `returncode` | `int` |
| `stderr` | `str` |
| `stdout` | `str` |
| `timed_out` | `bool` |
| `truncated` | `bool` |

## open_table_connector.officecli.capabilities

| Name | Kind | Definition |
| --- | --- | --- |
| `OfficeCliCapability` | class | `(supported: 'bool', version: 'str \| None' = None, reason: 'str \| None' = None, modes: 'tuple[str, ...]' = (), formats: 'tuple[str, ...]' = ('docx', 'pptx', 'xlsx'), browser: 'str \| None' = None) -> None` [source](../../packages/officecli/src/open_table_connector/officecli/capabilities.py) |
| `check_officecli` | function | `(binary: 'str' = 'officecli', *, renderer: 'str' = 'html', browser: 'str \| None' = None) -> 'OfficeCliCapability'` [source](../../packages/officecli/src/open_table_connector/officecli/capabilities.py) |

### OfficeCliCapability

| Field | Declared type |
| --- | --- |
| `browser` | `str \| None` |
| `formats` | `tuple[str, ...]` |
| `modes` | `tuple[str, ...]` |
| `reason` | `str \| None` |
| `supported` | `bool` |
| `version` | `str \| None` |

## open_table_connector.mcp.policy

| Name | Kind | Definition |
| --- | --- | --- |
| `AccessPolicy` | class | `(allowed_roots: 'tuple[Path, ...]', allowed_provider_ids: 'tuple[str, ...]', allowed_document_origins: 'tuple[str, ...]', credential_references: 'tuple[str, ...]') -> None` [source](../../packages/mcp/src/open_table_connector/mcp/policy.py) |
| `authorize` | function | `(request: 'OperationRequest', policy: 'AccessPolicy') -> 'None'` [source](../../packages/mcp/src/open_table_connector/mcp/policy.py) |
| `load_policy` | function | `(path: 'Path') -> 'AccessPolicy'` [source](../../packages/mcp/src/open_table_connector/mcp/policy.py) |

### AccessPolicy

| Field | Declared type |
| --- | --- |
| `allowed_document_origins` | `tuple[str, ...]` |
| `allowed_provider_ids` | `tuple[str, ...]` |
| `allowed_roots` | `tuple[Path, ...]` |
| `credential_references` | `tuple[str, ...]` |

## open_table_connector.mcp.tools

| Name | Kind | Definition |
| --- | --- | --- |
| `otc_discover` | function | `(selector: 'Mapping[str, object] \| None' = None)` [source](../../packages/mcp/src/open_table_connector/mcp/tools.py) |
| `otc_execute` | function | `(request, client, policy)` [source](../../packages/mcp/src/open_table_connector/mcp/tools.py) |
| `otc_inspect` | function | `(request, client, policy)` [source](../../packages/mcp/src/open_table_connector/mcp/tools.py) |
| `result_payload` | function | `(result)` [source](../../packages/mcp/src/open_table_connector/mcp/tools.py) |

## open_table_connector.mcp.server

| Name | Kind | Definition |
| --- | --- | --- |
| `MCPHost` | class | `(client: 'object') -> None` [source](../../packages/mcp/src/open_table_connector/mcp/server.py) |
| `create_server` | function | `(*, host: 'MCPHost \| None' = None, policy: 'AccessPolicy \| None' = None) -> 'FastMCP'` [source](../../packages/mcp/src/open_table_connector/mcp/server.py) |
| `handle_request` | function | `(request, *, host: 'MCPHost \| None' = None, policy: 'AccessPolicy \| None' = None)` [source](../../packages/mcp/src/open_table_connector/mcp/server.py) |
| `main` | function | `() -> 'int'` [source](../../packages/mcp/src/open_table_connector/mcp/server.py) |

### MCPHost

| Field | Declared type |
| --- | --- |
| `client` | `object` |

## open_table_connector.process

| Name | Kind | Definition |
| --- | --- | --- |
| `ArtifactStore` | class | `(root: 'str \| os.PathLike[str]', *, ttl_seconds: 'int' = 3600, clock: 'Callable[[], float]' = <built-in function time>) -> 'None'` [source](../../packages/process/src/open_table_connector/process/artifacts.py) |
| `BoundedDiagnostics` | class | `(stream: 'TextIO', *, max_bytes: 'int' = 16384, max_bytes_per_message: 'int \| None' = None, secrets: 'Iterable[str]' = ()) -> 'None'` [source](../../packages/process/src/open_table_connector/process/server.py) |
| `ConnectorProcessEnvelope` | class | `(protocol: 'str', message_id: 'str', session_id: 'str', operation: 'ProcessOperation', connector: 'Mapping[str, str]', capability_version: 'str', resource_limits: 'ResourceBounds', credential_reference: 'str \| None', payload: 'Mapping[str, object]', artifact_references: 'tuple[ArrowArtifactReference, ...]') -> None` [source](../../packages/process/src/open_table_connector/process/envelope.py) |
| `ConnectorProcessRegistry` | class | `(registrations: 'tuple[ConnectorRegistration, ...]' = ()) -> 'None'` [source](../../packages/process/src/open_table_connector/process/registry.py) |
| `ConnectorProcessServer` | class | `(registry: 'ConnectorProcessRegistry', artifact_store: 'ArtifactStore', credential_resolver: 'CredentialResolver', clock: 'object \| None' = None, max_completed_messages: 'int' = 4096) -> 'None'` [source](../../packages/process/src/open_table_connector/process/server.py) |
| `ConnectorRegistration` | class | `(connector_id: 'str', connector_version: 'str', contract_version: 'str', portable_plan_version: 'str', capability_versions: 'Mapping[str, str]', handler: 'ProcessHandler') -> None` [source](../../packages/process/src/open_table_connector/process/registry.py) |
| `CredentialLease` | class | `(reference: 'str \| None', connector_id: 'str', values: 'Mapping[str, str]') -> 'None'` [source](../../packages/process/src/open_table_connector/process/credentials.py) |
| `CredentialResolver` | class | `(references: 'Mapping[str, Mapping[str, Mapping[str, str]]] \| None' = None) -> 'None'` [source](../../packages/process/src/open_table_connector/process/credentials.py) |
| `FrameError` | class | `(signature unavailable; see source)` [source](../../packages/process/src/open_table_connector/process/framing.py) |
| `PORTABLE_PLAN_VERSION` | constant | `'otc.portable-temporal-plan/v1'`  |
| `PORTABLE_PROVIDER_CAPABILITIES` | constant | `mappingproxy; inspect via this named export`  |
| `PROCESS_PROTOCOL` | constant | `'otc.connector-process/v1'`  |
| `ProcessError` | class | `(code: 'str', message: 'str', safe_details: 'Mapping[str, object] \| None' = None) -> 'None'` [source](../../packages/process/src/open_table_connector/process/server.py) |
| `ProcessHandler` | class | `(*args, **kwargs)` [source](../../packages/process/src/open_table_connector/process/registry.py) |
| `ProcessOperation` | enum | `(value, names=None, *, module=None, qualname=None, type=None, start=1, boundary=None)` [source](../../packages/process/src/open_table_connector/process/envelope.py) |
| `ProcessRequestContext` | class | `(envelope: 'ConnectorProcessEnvelope', artifacts: 'ArtifactStore', credentials: 'CredentialLease') -> None` [source](../../packages/process/src/open_table_connector/process/server.py) |
| `ProcessResult` | class | `(payload: 'Mapping[str, object]', artifact_references: 'tuple[ArrowArtifactReference, ...]' = ()) -> None` [source](../../packages/process/src/open_table_connector/process/server.py) |
| `TemporalProcessHandler` | class | `(*, executor: 'PortableTemporalExecutor \| None', store: 'ManagedTemporalStore \| None') -> 'None'` [source](../../packages/process/src/open_table_connector/process/timeseries.py) |
| `build_process_runtime` | function | `(config_path: 'str \| os.PathLike[str]', artifact_root: 'str \| os.PathLike[str]') -> 'tuple[ConnectorProcessRegistry, CredentialResolver]'` [source](../../packages/process/src/open_table_connector/process/bootstrap.py) |
| `read_frame` | function | `(stream: 'BinaryIO', max_frame_bytes: 'int') -> 'Mapping[str, object] \| None'` [source](../../packages/process/src/open_table_connector/process/framing.py) |
| `redact_text` | function | `(value: 'str', secrets: 'Iterable[str]' = ()) -> 'str'` [source](../../packages/process/src/open_table_connector/process/server.py) |
| `run_server` | function | `(stdin: 'BinaryIO', stdout: 'BinaryIO', stderr: 'TextIO', *, artifact_root: 'str \| os.PathLike[str]', registry: 'ConnectorProcessRegistry \| None' = None, credential_resolver: 'CredentialResolver \| None' = None, max_frame_bytes: 'int' = 16777216, max_pending_requests: 'int' = 8) -> 'int'` [source](../../packages/process/src/open_table_connector/process/server.py) |
| `temporal_registration` | function | `(provider: 'str', handler: 'TemporalProcessHandler') -> 'ConnectorRegistration'` [source](../../packages/process/src/open_table_connector/process/timeseries.py) |
| `write_frame` | function | `(stream: 'BinaryIO', envelope: 'Mapping[str, object] \| object') -> 'None'` [source](../../packages/process/src/open_table_connector/process/framing.py) |

### ArtifactStore

| Public member | Signature or access |
| --- | --- |
| `cleanup_expired` | `(self) -> 'int'` |
| `get_arrow` | `(self, reference: 'ArrowArtifactReference', bounds: 'ResourceBounds') -> 'pa.Table'` |
| `put_arrow` | `(self, table: 'pa.Table') -> 'ArrowArtifactReference'` |

### BoundedDiagnostics

| Public member | Signature or access |
| --- | --- |
| `write` | `(self, message: 'str') -> 'None'` |

### ConnectorProcessEnvelope

| Field | Declared type |
| --- | --- |
| `artifact_references` | `tuple[ArrowArtifactReference, ...]` |
| `capability_version` | `str` |
| `connector` | `Mapping[str, str]` |
| `credential_reference` | `str \| None` |
| `message_id` | `str` |
| `operation` | `ProcessOperation` |
| `payload` | `Mapping[str, object]` |
| `protocol` | `str` |
| `resource_limits` | `ResourceBounds` |
| `session_id` | `str` |

| Public member | Signature or access |
| --- | --- |
| `from_request_wire` | `(value: 'object') -> 'ConnectorProcessEnvelope'` |
| `from_response_wire` | `(value: 'object') -> 'ConnectorProcessEnvelope'` |
| `from_wire` | `(value: 'object') -> 'ConnectorProcessEnvelope'` |
| `to_wire` | `(self) -> 'dict[str, object]'` |

### ConnectorProcessRegistry

| Public member | Signature or access |
| --- | --- |
| `register` | `(self, registration: 'ConnectorRegistration') -> 'None'` |
| `resolve` | `(self, connector_id: 'str') -> 'ConnectorRegistration'` |

### ConnectorProcessServer

| Public member | Signature or access |
| --- | --- |
| `error_response` | `(self, envelope: 'ConnectorProcessEnvelope', error: 'ProcessError') -> 'ConnectorProcessEnvelope'` |
| `handle` | `(self, envelope: 'ConnectorProcessEnvelope') -> 'ConnectorProcessEnvelope'` |
| `retire_session` | `(self, session_id: 'str') -> 'None'` |

### ConnectorRegistration

| Field | Declared type |
| --- | --- |
| `capability_versions` | `Mapping[str, str]` |
| `connector_id` | `str` |
| `connector_version` | `str` |
| `contract_version` | `str` |
| `handler` | `ProcessHandler` |
| `portable_plan_version` | `str` |

### CredentialLease

| Public member | Signature or access |
| --- | --- |
| `dispose` | `(self) -> 'None'` |
| `values` | `property (read-only)` |

### CredentialResolver

| Public member | Signature or access |
| --- | --- |
| `resolve` | `(self, reference: 'str \| None', connector_id: 'str') -> 'CredentialLease'` |

### FrameError

### ProcessError

### ProcessHandler

| Public member | Signature or access |
| --- | --- |
| `handle` | `(self, context: 'object') -> 'object'` |

### ProcessOperation

| Member | Wire value |
| --- | --- |
| `HELLO` | `hello` |
| `DESCRIBE` | `describe` |
| `EXECUTE` | `execute` |
| `STAGE` | `stage` |
| `COMMIT` | `commit` |
| `READBACK` | `readback` |
| `ABORT` | `abort` |
| `CANCEL` | `cancel` |

### ProcessRequestContext

| Field | Declared type |
| --- | --- |
| `artifacts` | `ArtifactStore` |
| `credentials` | `CredentialLease` |
| `envelope` | `ConnectorProcessEnvelope` |

### ProcessResult

| Field | Declared type |
| --- | --- |
| `artifact_references` | `tuple[ArrowArtifactReference, ...]` |
| `payload` | `Mapping[str, object]` |

### TemporalProcessHandler

| Public member | Signature or access |
| --- | --- |
| `abort_session` | `(self, session_id: 'str') -> 'None'` |
| `handle` | `(self, context: 'ProcessRequestContext') -> 'ProcessResult'` |
| `has_executor` | `property (read-only)` |
| `has_store` | `property (read-only)` |

## open_table_connector.local_files

| Name | Kind | Definition |
| --- | --- | --- |
| `CAPABILITY_MANIFEST` | constant | `CapabilityManifest; inspect via this named export`  |
| `CONNECTOR_IDENTITY` | constant | `ConnectorIdentity(connector_id='local_files', connector_version='0.1.0', contract_version='1.0')`  |
| `CsvConnector` | class | `(*args, **kwargs)` [source](../../packages/local_files/src/open_table_connector/local_files/csv_connector.py) |
| `CsvManagedTemporalStore` | class | `(artifact_root: 'str \| Path', descriptor: 'TemporalTableDescriptor', *, clock=None, fault_injector=None) -> 'None'` [source](../../packages/local_files/src/open_table_connector/local_files/temporal_csv.py) |
| `CsvReadOptions` | class | `(separator: 'str' = ',', encoding: 'str' = 'utf8') -> None` [source](../../packages/local_files/src/open_table_connector/local_files/csv_connector.py) |
| `CsvTableReadRequest` | class | `(uri: 'TableURI', resource_limits: 'ResourceLimits' = <factory>, options: 'CsvReadOptions' = <factory>) -> None` [source](../../packages/local_files/src/open_table_connector/local_files/csv_connector.py) |
| `CsvTemporalExecutor` | class | `(descriptor: 'TemporalTableDescriptor', managed_store: 'CsvManagedTemporalStore \| None' = None) -> 'None'` [source](../../packages/local_files/src/open_table_connector/local_files/temporal_csv.py) |
| `ExcelConnector` | class | `(*args, **kwargs)` [source](../../packages/local_files/src/open_table_connector/local_files/excel_connector.py) |
| `ExcelFormulaExtension` | class | `(connector: 'Any \| None' = None) -> 'None'` [source](../../packages/local_files/src/open_table_connector/local_files/excel_formula.py) |
| `ExcelManagedTemporalStore` | class | `(artifact_root: 'str \| Path', descriptor: 'TemporalTableDescriptor', *, worksheet: 'str', clock=None, fault_injector=None) -> 'None'` [source](../../packages/local_files/src/open_table_connector/local_files/temporal_excel.py) |
| `ExcelReadOptions` | class | `(sheet: 'str \| None' = None, header_row: 'int' = 1) -> None` [source](../../packages/local_files/src/open_table_connector/local_files/excel_connector.py) |
| `ExcelTableReadRequest` | class | `(uri: 'TableURI', resource_limits: 'ResourceLimits' = <factory>, options: 'ExcelReadOptions' = <factory>) -> None` [source](../../packages/local_files/src/open_table_connector/local_files/excel_connector.py) |
| `ExcelTemporalExecutor` | class | `(descriptor: 'TemporalTableDescriptor', *, worksheet: 'str', managed_store: 'ExcelManagedTemporalStore \| None' = None) -> 'None'` [source](../../packages/local_files/src/open_table_connector/local_files/temporal_excel.py) |
| `JsonConnector` | class | `(*, clock: 'Callable[[], float]' = <built-in function monotonic>) -> 'None'` [source](../../packages/local_files/src/open_table_connector/local_files/json_connector.py) |
| `JsonManagedTemporalStore` | class | `(format_name: 'JsonFormat', artifact_root: 'str \| Path', descriptor: 'TemporalTableDescriptor', *, clock=None, fault_injector=None) -> 'None'` [source](../../packages/local_files/src/open_table_connector/local_files/temporal_json.py) |
| `JsonTableReadRequest` | class | `(uri: 'TableURI', resource_limits: 'ResourceLimits' = <factory>) -> None` [source](../../packages/local_files/src/open_table_connector/local_files/json_connector.py) |
| `JsonTemporalExecutor` | class | `(descriptor: 'TemporalTableDescriptor', managed_store: 'JsonManagedTemporalStore \| None' = None) -> 'None'` [source](../../packages/local_files/src/open_table_connector/local_files/temporal_json.py) |
| `LocalBoundedReader` | class | `(*, connector: 'ConnectorIdentity') -> 'None'` [source](../../packages/local_files/src/open_table_connector/local_files/bounded_reader.py) |
| `LocalFilesCliAdapter` | class | `(connector: 'object', context) -> 'None'` [source](../../packages/local_files/src/open_table_connector/local_files/cli_adapter.py) |
| `LocalFilesConnector` | class | `(resolver: 'LocalURIResolver \| None' = None) -> 'None'` [source](../../packages/local_files/src/open_table_connector/local_files/local_files_connector.py) |
| `LocalFilesSdkTemporalExtension` | class | `(connector: 'Any', binding: 'TableBinding', descriptor: 'TemporalTableDescriptor') -> 'None'` [source](../../packages/local_files/src/open_table_connector/local_files/sdk_temporal.py) |
| `LocalFormat` | enum | `(value, names=None, *, module=None, qualname=None, type=None, start=1, boundary=None)` [source](../../packages/local_files/src/open_table_connector/local_files/probe.py) |
| `LocalReadOptions` | class | `(separator: 'str' = ',', encoding: 'str' = 'utf8', sheet: 'str \| None' = None, header_row: 'int' = 1) -> None` [source](../../packages/local_files/src/open_table_connector/local_files/local_files_connector.py) |
| `LocalSpreadsheetProvider` | class | `()` [source](../../packages/local_files/src/open_table_connector/local_files/spreadsheet_workbook.py) |
| `LocalTableReadRequest` | class | `(uri: 'TableURI', resource_limits: 'ResourceLimits' = <factory>, options: 'LocalReadOptions' = <factory>) -> None` [source](../../packages/local_files/src/open_table_connector/local_files/local_files_connector.py) |
| `LocalURIResolver` | class | `()` [source](../../packages/local_files/src/open_table_connector/local_files/resolver.py) |
| `MarkdownCliAdapter` | class | `(connector: '_TextCodecConnector[_RequestT]', context) -> 'None'` [source](../../packages/local_files/src/open_table_connector/local_files/cli_adapter.py) |
| `MarkdownConnector` | class | `(*args, **kwargs)` [source](../../packages/local_files/src/open_table_connector/local_files/markdown_connector.py) |
| `MarkdownReadOptions` | class | `(encoding: 'str' = 'utf8') -> None` [source](../../packages/local_files/src/open_table_connector/local_files/markdown_connector.py) |
| `MarkdownTableReadRequest` | class | `(uri: 'TableURI', resource_limits: 'ResourceLimits' = <factory>, options: 'MarkdownReadOptions' = <factory>) -> None` [source](../../packages/local_files/src/open_table_connector/local_files/markdown_connector.py) |
| `ResolvedLocalTable` | class | `(path: 'Path', format: 'LocalFormat', sheet: 'str \| None' = None) -> None` [source](../../packages/local_files/src/open_table_connector/local_files/resolver.py) |
| `detect_format` | function | `(path: 'Path') -> 'LocalFormat'` [source](../../packages/local_files/src/open_table_connector/local_files/probe.py) |
| `encode_json_table` | function | `(table: 'pa.Table') -> 'str'` [source](../../packages/local_files/src/open_table_connector/local_files/json_codec.py) |
| `encode_jsonl_table` | function | `(table: 'pa.Table') -> 'str'` [source](../../packages/local_files/src/open_table_connector/local_files/json_codec.py) |
| `is_markdown_payload` | function | `(text: 'str') -> 'bool'` [source](../../packages/local_files/src/open_table_connector/local_files/markdown_reader.py) |
| `local_files_cli_plugin` | function | `() -> 'PluginDescriptor'` [source](../../packages/local_files/src/open_table_connector/local_files/cli_adapter.py) |
| `markdown_cli_plugin` | function | `() -> 'PluginDescriptor'` [source](../../packages/local_files/src/open_table_connector/local_files/cli_adapter.py) |
| `parse_json_table` | function | `(text: 'str', *, source: 'str') -> 'pa.Table'` [source](../../packages/local_files/src/open_table_connector/local_files/json_codec.py) |
| `parse_jsonl_table` | function | `(text: 'str', *, source: 'str') -> 'pa.Table'` [source](../../packages/local_files/src/open_table_connector/local_files/json_codec.py) |
| `read_excel_arrow` | function | `(path: 'Path', *, sheet: 'str \| None', header_row: 'int', limits: 'ResourceLimits') -> 'tuple[pa.Table, str, tuple[str, ...]]'` [source](../../packages/local_files/src/open_table_connector/local_files/excel_reader.py) |
| `read_markdown_arrow` | function | `(text: 'str', *, source: 'str') -> 'pa.Table'` [source](../../packages/local_files/src/open_table_connector/local_files/markdown_reader.py) |
| `write_excel` | function | `(table: 'pa.Table', path: 'Path', sheet: 'str \| None' = None) -> 'None'` [source](../../packages/local_files/src/open_table_connector/local_files/excel_writer.py) |
| `write_markdown_table` | function | `(headers: 'Sequence[str]', rows: 'Iterable[Sequence[str]]', stream: 'TextIO') -> 'None'` [source](../../packages/local_files/src/open_table_connector/local_files/markdown_reader.py) |

### CsvConnector

| Public member | Signature or access |
| --- | --- |
| `inspect` | `(self, request: 'InspectRequest')` |
| `read_arrow` | `(self, request: 'CsvTableReadRequest') -> 'ArrowReadResult'` |
| `read_polars` | `(self, request: 'CsvTableReadRequest') -> 'PolarsReadResult'` |
| `resolve` | `(self, uri: 'TableURI', context: 'ResolveContext') -> 'ResolvedTable'` |

### CsvManagedTemporalStore

| Public member | Signature or access |
| --- | --- |
| `abort` | `(self, request: 'ManagedAbortRequest') -> 'ManagedAbortReceipt'` |
| `commit` | `(self, request: 'ManagedCommitRequest') -> 'ManagedCommitReceipt'` |
| `descriptor` | `property (read-only)` |
| `read_snapshot` | `(self, target: 'TableURI', snapshot_reference: 'str', bounds: 'ResourceBounds') -> 'pa.Table'` |
| `readback` | `(self, request: 'ManagedReadbackRequest') -> 'ManagedReadbackResult'` |
| `recover` | `(self, target: 'TableURI') -> 'None'` |
| `resolve_snapshot` | `(self, target: 'TableURI', snapshot_reference: 'str') -> 'Path'` |
| `stage` | `(self, request: 'ManagedStageRequest') -> 'ManagedStageReceipt'` |

### CsvReadOptions

| Field | Declared type |
| --- | --- |
| `encoding` | `str` |
| `separator` | `str` |

### CsvTableReadRequest

| Field | Declared type |
| --- | --- |
| `options` | `CsvReadOptions` |
| `resource_limits` | `ResourceLimits` |
| `uri` | `TableURI` |

| Public member | Signature or access |
| --- | --- |
| `resolve_context` | `property (read-only)` |

### CsvTemporalExecutor

| Public member | Signature or access |
| --- | --- |
| `execute` | `(self, request: 'TemporalExecutionRequest') -> 'TemporalExecutionResult'` |

### ExcelConnector

| Public member | Signature or access |
| --- | --- |
| `inspect` | `(self, request: 'InspectRequest \| ExcelTableReadRequest')` |
| `read_arrow` | `(self, request: 'ExcelTableReadRequest') -> 'ArrowReadResult'` |
| `read_polars` | `(self, request: 'ExcelTableReadRequest') -> 'PolarsReadResult'` |
| `resolve` | `(self, uri: 'TableURI', context: 'ResolveContext') -> 'ResolvedTable'` |

### ExcelFormulaExtension

| Public member | Signature or access |
| --- | --- |
| `bind_grid` | `(self, request: 'otf.GridFormulaBindRequest') -> 'otf.FormulaExtensionResult[otf.GridFormulaBinding]'` |
| `read_grid` | `(self, request: 'otf.GridFormulaReadRequest') -> 'otf.FormulaExtensionResult[otf.GridFormulaObservation]'` |
| `read_grid_values` | `(self, request: 'otf.GridFormulaValueReadRequest') -> 'otf.FormulaExtensionResult[otf.GridFormulaValueObservation]'` |
| `recalculate_grid` | `(self, request: 'otf.GridFormulaRecalculateRequest') -> 'otf.FormulaExtensionResult[otf.RecalculationObservation]'` |
| `set_grid` | `(self, request: 'otf.GridFormulaSetRequest') -> 'otf.FormulaExtensionResult[otf.FormulaMutation]'` |

### ExcelManagedTemporalStore

| Public member | Signature or access |
| --- | --- |
| `abort` | `(self, request: 'ManagedAbortRequest') -> 'ManagedAbortReceipt'` |
| `capabilities` | `property (read-only)` |
| `commit` | `(self, request: 'ManagedCommitRequest') -> 'ManagedCommitReceipt'` |
| `read_snapshot` | `(self, target: 'TableURI', snapshot_reference: 'str', bounds: 'ResourceBounds') -> 'pa.Table'` |
| `readback` | `(self, request: 'ManagedReadbackRequest') -> 'ManagedReadbackResult'` |
| `recover` | `(self, target: 'TableURI') -> 'None'` |
| `resolve_snapshot` | `(self, target: 'TableURI', snapshot_reference: 'str') -> 'Path'` |
| `stage` | `(self, request: 'ManagedStageRequest') -> 'ManagedStageReceipt'` |

### ExcelReadOptions

| Field | Declared type |
| --- | --- |
| `header_row` | `int` |
| `sheet` | `str \| None` |

### ExcelTableReadRequest

| Field | Declared type |
| --- | --- |
| `options` | `ExcelReadOptions` |
| `resource_limits` | `ResourceLimits` |
| `uri` | `TableURI` |

| Public member | Signature or access |
| --- | --- |
| `resolve_context` | `property (read-only)` |

### ExcelTemporalExecutor

| Public member | Signature or access |
| --- | --- |
| `execute` | `(self, request: 'TemporalExecutionRequest') -> 'TemporalExecutionResult'` |

### JsonConnector

| Public member | Signature or access |
| --- | --- |
| `inspect` | `(self, request: 'InspectRequest')` |
| `read_arrow` | `(self, request: 'JsonTableReadRequest') -> 'ArrowReadResult'` |
| `read_polars` | `(self, request: 'JsonTableReadRequest') -> 'PolarsReadResult'` |
| `resolve` | `(self, uri: 'TableURI', context: 'ResolveContext') -> 'ResolvedTable'` |

### JsonManagedTemporalStore

| Public member | Signature or access |
| --- | --- |
| `abort` | `(self, request: 'ManagedAbortRequest') -> 'ManagedAbortReceipt'` |
| `commit` | `(self, request: 'ManagedCommitRequest') -> 'ManagedCommitReceipt'` |
| `descriptor` | `property (read-only)` |
| `read_snapshot` | `(self, target: 'TableURI', snapshot_reference: 'str', bounds: 'ResourceBounds') -> 'pa.Table'` |
| `readback` | `(self, request: 'ManagedReadbackRequest') -> 'ManagedReadbackResult'` |
| `recover` | `(self, target: 'TableURI') -> 'None'` |
| `resolve_snapshot` | `(self, target: 'TableURI', snapshot_reference: 'str') -> 'Path'` |
| `stage` | `(self, request: 'ManagedStageRequest') -> 'ManagedStageReceipt'` |

### JsonTableReadRequest

| Field | Declared type |
| --- | --- |
| `resource_limits` | `ResourceLimits` |
| `uri` | `TableURI` |

| Public member | Signature or access |
| --- | --- |
| `resolve_context` | `property (read-only)` |

### JsonTemporalExecutor

| Public member | Signature or access |
| --- | --- |
| `execute` | `(self, request: 'TemporalExecutionRequest') -> 'TemporalExecutionResult'` |

### LocalBoundedReader

| Public member | Signature or access |
| --- | --- |
| `read_arrow_bounded` | `(self, request: 'BoundedTableReadRequest') -> 'BoundedArrowTableReadResult'` |

### LocalFilesCliAdapter

| Field | Declared type |
| --- | --- |
| `hosts` | `tuple[str, ...]` |

| Public member | Signature or access |
| --- | --- |
| `formula_extension_for` | `(self)` |
| `inspect` | `(self, endpoint: 'Endpoint', options: 'AdapterOptions') -> 'TableInspection'` |
| `read` | `(self, endpoint: 'Endpoint', options: 'AdapterOptions') -> 'ArrowReadResult'` |
| `sdk_connector` | `(self)` |
| `spreadsheet_provider` | `(self)` |
| `write` | `(self, endpoint: 'Endpoint', table: 'pa.Table', options: 'AdapterOptions') -> 'TableWriteResult'` |

### LocalFilesConnector

| Field | Declared type |
| --- | --- |
| `hosts` | `tuple[str, ...]` |

| Public member | Signature or access |
| --- | --- |
| `begin_transaction` | `(self, binding: 'TableBinding') -> 'Any'` |
| `capabilities_for` | `(self, binding: 'TableBinding') -> 'OperationResult[CapabilitySet]'` |
| `close` | `(self) -> 'None'` |
| `create_table` | `(self, source: 'object', destination: 'object') -> 'OperationResult[TableBinding]'` |
| `delete_rows` | `(self, binding: 'TableBinding', *, where: 'Any', parameters: 'dict[str, Any] \| None' = None) -> 'OperationResult[int]'` |
| `drop_table` | `(self, binding: 'TableBinding') -> 'OperationResult[None]'` |
| `formula_extension_for` | `(self)` |
| `insert_rows` | `(self, binding: 'TableBinding', frame: 'pl.DataFrame') -> 'OperationResult[int]'` |
| `inspect` | `(self, request: 'InspectRequest \| LocalTableReadRequest') -> 'TableInspection'` |
| `inspect_table` | `(self, binding: 'TableBinding') -> 'OperationResult[TableInspection]'` |
| `open_table` | `(self, address: 'object') -> 'OperationResult[TableBinding]'` |
| `read_arrow` | `(self, request: 'LocalTableReadRequest') -> 'ArrowReadResult'` |
| `read_polars` | `(self, request: 'LocalTableReadRequest') -> 'PolarsReadResult'` |
| `read_table` | `(self, binding: 'TableBinding', *, limit: 'int \| None' = None, continuation: 'str \| None' = None) -> 'OperationResult[ArrowTableCarrier]'` |
| `resolve` | `(self, uri: 'TableURI', context: 'ResolveContext') -> 'ResolvedTable'` |
| `spreadsheet_provider` | `(self)` |
| `temporal_extension_for` | `(self, binding: 'TableBinding', descriptor: 'TemporalTableDescriptor') -> 'LocalFilesSdkTemporalExtension'` |
| `update_rows` | `(self, binding: 'TableBinding', frame: 'pl.DataFrame', *, keys: 'tuple[str, ...]') -> 'OperationResult[int]'` |

### LocalFilesSdkTemporalExtension

| Public member | Signature or access |
| --- | --- |
| `abort_stage` | `(self, binding: 'TableBinding', descriptor: 'TemporalTableDescriptor', stage: 'Any')` |
| `append_rows` | `(self, binding: 'TableBinding', descriptor: 'TemporalTableDescriptor', frame: 'pl.DataFrame', *, idempotency_key: 'str') -> 'OperationResult[int]'` |
| `commit_stage` | `(self, binding: 'TableBinding', descriptor: 'TemporalTableDescriptor', stage: 'Any')` |
| `current_snapshot` | `(self, binding: 'TableBinding', descriptor: 'TemporalTableDescriptor') -> 'None'` |
| `descriptor_hash_for` | `(self, binding: 'TableBinding', descriptor: 'TemporalTableDescriptor') -> 'str'` |
| `executor_for` | `(self, binding: 'TableBinding', descriptor: 'TemporalTableDescriptor') -> 'Any'` |
| `readback_snapshot` | `(self, binding: 'TableBinding', descriptor: 'TemporalTableDescriptor', snapshot: 'Any')` |
| `stage_rows` | `(self, binding: 'TableBinding', descriptor: 'TemporalTableDescriptor', frame: 'pl.DataFrame', *, idempotency_key: 'str')` |
| `upsert_rows` | `(self, binding: 'TableBinding', descriptor: 'TemporalTableDescriptor', frame: 'pl.DataFrame', *, idempotency_key: 'str') -> 'OperationResult[int]'` |

### LocalFormat

| Member | Wire value |
| --- | --- |
| `CSV` | `csv` |
| `EXCEL` | `excel` |
| `JSON` | `json` |
| `JSONL` | `jsonl` |
| `MARKDOWN` | `md` |

### LocalReadOptions

| Field | Declared type |
| --- | --- |
| `encoding` | `str` |
| `header_row` | `int` |
| `separator` | `str` |
| `sheet` | `str \| None` |

### LocalSpreadsheetProvider

| Public member | Signature or access |
| --- | --- |
| `bind` | `(self, target: 'SpreadsheetTarget')` |
| `commit` | `(self, binding, changes, *, allow_partial=False, expected_revision=None, idempotency_key=None)` |
| `observe` | `(self, binding, selector)` |
| `preflight` | `(self, binding, changes)` |
| `verify_layout` | `(self, binding, expected)` |

### LocalTableReadRequest

| Field | Declared type |
| --- | --- |
| `options` | `LocalReadOptions` |
| `resource_limits` | `ResourceLimits` |
| `uri` | `TableURI` |

| Public member | Signature or access |
| --- | --- |
| `resolve_context` | `property (read-only)` |

### LocalURIResolver

| Public member | Signature or access |
| --- | --- |
| `resolve` | `(self, uri: 'TableURI', context: 'ResolveContext') -> 'ResolvedTable'` |

### MarkdownCliAdapter

| Field | Declared type |
| --- | --- |
| `connector` | `_TextCodecConnector[_RequestT]` |
| `hosts` | `tuple[str, ...]` |

| Public member | Signature or access |
| --- | --- |
| `inspect` | `(self, endpoint: 'Endpoint', options: 'AdapterOptions') -> 'TableInspection'` |
| `read` | `(self, endpoint: 'Endpoint', options: 'AdapterOptions') -> 'ArrowReadResult'` |
| `write` | `(self, endpoint: 'Endpoint', table: 'pa.Table', options: 'AdapterOptions') -> 'TableWriteResult'` |

### MarkdownConnector

| Public member | Signature or access |
| --- | --- |
| `inspect` | `(self, request: 'InspectRequest')` |
| `read_arrow` | `(self, request: 'MarkdownTableReadRequest') -> 'ArrowReadResult'` |
| `read_polars` | `(self, request: 'MarkdownTableReadRequest') -> 'PolarsReadResult'` |
| `resolve` | `(self, uri: 'TableURI', context: 'ResolveContext') -> 'ResolvedTable'` |

### MarkdownReadOptions

| Field | Declared type |
| --- | --- |
| `encoding` | `str` |

### MarkdownTableReadRequest

| Field | Declared type |
| --- | --- |
| `options` | `MarkdownReadOptions` |
| `resource_limits` | `ResourceLimits` |
| `uri` | `TableURI` |

| Public member | Signature or access |
| --- | --- |
| `resolve_context` | `property (read-only)` |

### ResolvedLocalTable

| Field | Declared type |
| --- | --- |
| `format` | `LocalFormat` |
| `path` | `Path` |
| `sheet` | `str \| None` |

## open_table_connector.sqlite

| Name | Kind | Definition |
| --- | --- | --- |
| `CONNECTOR_IDENTITY` | constant | `ConnectorIdentity(connector_id='sqlite', connector_version='0.1.0', contract_version='1.0')`  |
| `SQLiteConnector` | class | `(connection_factory: 'Callable[[str], Any] \| None' = None) -> 'None'` [source](../../packages/sqlite/src/open_table_connector/sqlite/reader.py) |
| `SQLiteManagedTemporalStore` | class | `(database_uri: 'TableURI', artifact_root: 'str \| os.PathLike[str]', descriptor: 'TemporalTableDescriptor', *, connection_factory=None, clock=None, fault_injector=None) -> 'None'` [source](../../packages/sqlite/src/open_table_connector/sqlite/temporal.py) |
| `SQLiteReadOptions` | class | `(table: 'str \| None' = None, query: 'str \| None' = None, parameters: 'tuple[Any, ...]' = (), key_fields: 'tuple[str, ...]' = (), record_id_field: 'str \| None' = None) -> None` [source](../../packages/sqlite/src/open_table_connector/sqlite/reader.py) |
| `SQLiteSdkTemporalExtension` | class | `(connector: 'Any', binding: 'TableBinding', descriptor: 'TemporalTableDescriptor') -> 'None'` [source](../../packages/sqlite/src/open_table_connector/sqlite/sdk_temporal.py) |
| `SQLiteTableReadRequest` | class | `(uri: 'TableURI', resource_limits: 'ResourceLimits' = <factory>, options: 'SQLiteReadOptions' = <factory>) -> None` [source](../../packages/sqlite/src/open_table_connector/sqlite/reader.py) |
| `SQLiteTemporalExecutor` | class | `(descriptor: 'TemporalTableDescriptor', physical_table: 'str', *, managed_store: 'SQLiteManagedTemporalStore \| None' = None, connection_factory=None) -> 'None'` [source](../../packages/sqlite/src/open_table_connector/sqlite/temporal.py) |
| `SQLiteTransaction` | class | `(connector: 'SQLiteConnector', uri: 'TableURI', connection: 'Any') -> 'None'` [source](../../packages/sqlite/src/open_table_connector/sqlite/reader.py) |
| `TABLE_EXECUTE_CAPABILITY` | constant | `CapabilityIdentity(capability_id='table.execute', capability_version='1.0')`  |
| `TABLE_INSPECT_CAPABILITY` | constant | `CapabilityIdentity(capability_id='table.inspect', capability_version='1.0')`  |
| `TABLE_READ_ARROW_CAPABILITY` | constant | `CapabilityIdentity(capability_id='table.read.arrow', capability_version='1.0')`  |
| `TABLE_READ_POLARS_CAPABILITY` | constant | `CapabilityIdentity(capability_id='table.read.polars', capability_version='1.0')`  |
| `TABLE_WRITE_CAPABILITY` | constant | `CapabilityIdentity(capability_id='table.write', capability_version='1.0')`  |
| `lower_sqlite` | function | `(plan: 'PortableTemporalPlan', descriptor: 'TemporalTableDescriptor', physical_table: 'str') -> 'PreparedTemporalQuery'` [source](../../packages/sqlite/src/open_table_connector/sqlite/temporal.py) |

### SQLiteConnector

| Field | Declared type |
| --- | --- |
| `hosts` | `tuple[str, ...]` |

| Public member | Signature or access |
| --- | --- |
| `abort` | `(self) -> 'None'` |
| `begin` | `(self, uri: 'TableURI \| None' = None) -> 'SQLiteTransaction'` |
| `begin_for` | `(self, uri: 'TableURI') -> 'SQLiteTransaction'` |
| `begin_transaction` | `(self, binding: 'TableBinding') -> 'Any'` |
| `capabilities_for` | `(self, binding: 'TableBinding') -> 'OperationResult[CapabilitySet]'` |
| `close` | `(self) -> 'None'` |
| `commit` | `(self) -> 'None'` |
| `create_table` | `(self, source: 'object', destination: 'object') -> 'OperationResult[TableBinding]'` |
| `delete_rows` | `(self, binding: 'TableBinding', *, where: 'Any', parameters: 'dict[str, Any] \| None' = None) -> 'OperationResult[int]'` |
| `drop_table` | `(self, binding: 'TableBinding') -> 'OperationResult[None]'` |
| `execute` | `(self, request: 'ExecutionRequest') -> 'ExecutionResult'` |
| `insert_rows` | `(self, binding: 'TableBinding', frame: 'pl.DataFrame') -> 'OperationResult[int]'` |
| `inspect` | `(self, request: 'InspectRequest') -> 'TableInspection'` |
| `inspect_table` | `(self, binding: 'TableBinding') -> 'OperationResult[TableInspection]'` |
| `open_table` | `(self, address: 'object') -> 'OperationResult[TableBinding]'` |
| `read_arrow` | `(self, request: 'SQLiteTableReadRequest') -> 'ArrowReadResult'` |
| `read_native_sql` | `(self, request: 'ExecutionRequest') -> 'ArrowReadResult'` |
| `read_polars` | `(self, request: 'SQLiteTableReadRequest') -> 'PolarsReadResult'` |
| `read_table` | `(self, binding: 'TableBinding', *, limit: 'int \| None' = None, continuation: 'str \| None' = None) -> 'OperationResult[ArrowTableCarrier]'` |
| `resolve` | `(self, uri: 'TableURI', context: 'ResolveContext') -> 'ResolvedTable'` |
| `temporal_extension_for` | `(self, binding: 'TableBinding', descriptor: 'TemporalTableDescriptor') -> 'SQLiteSdkTemporalExtension'` |
| `update_rows` | `(self, binding: 'TableBinding', frame: 'pl.DataFrame', *, keys: 'tuple[str, ...]') -> 'OperationResult[int]'` |
| `write` | `(self, request: 'TableWriteRequest') -> 'TableWriteResult'` |

### SQLiteManagedTemporalStore

| Public member | Signature or access |
| --- | --- |
| `abort` | `(self, request: 'ManagedAbortRequest') -> 'ManagedAbortReceipt'` |
| `commit` | `(self, request: 'ManagedCommitRequest') -> 'ManagedCommitReceipt'` |
| `current` | `(self, request: 'ManagedCurrentRequest') -> 'ManagedCurrentResult \| None'` |
| `read_snapshot` | `(self, target: 'TableURI', snapshot_reference: 'str', bounds: 'ResourceBounds', *, snapshot_id: 'str \| None' = None) -> 'pa.Table'` |
| `readback` | `(self, request: 'ManagedReadbackRequest') -> 'ManagedReadbackResult'` |
| `stage` | `(self, request: 'ManagedStageRequest') -> 'ManagedStageReceipt'` |

### SQLiteReadOptions

| Field | Declared type |
| --- | --- |
| `key_fields` | `tuple[str, ...]` |
| `parameters` | `tuple[Any, ...]` |
| `query` | `str \| None` |
| `record_id_field` | `str \| None` |
| `table` | `str \| None` |

### SQLiteSdkTemporalExtension

| Public member | Signature or access |
| --- | --- |
| `abort_stage` | `(self, binding: 'TableBinding', descriptor: 'TemporalTableDescriptor', stage: 'Any')` |
| `append_rows` | `(self, binding: 'TableBinding', descriptor: 'TemporalTableDescriptor', frame: 'pl.DataFrame', *, idempotency_key: 'str') -> 'OperationResult[int]'` |
| `commit_stage` | `(self, binding: 'TableBinding', descriptor: 'TemporalTableDescriptor', stage: 'Any')` |
| `current_snapshot` | `(self, binding: 'TableBinding', descriptor: 'TemporalTableDescriptor')` |
| `descriptor_hash_for` | `(self, binding: 'TableBinding', descriptor: 'TemporalTableDescriptor') -> 'str'` |
| `executor_for` | `(self, binding: 'TableBinding', descriptor: 'TemporalTableDescriptor') -> 'SQLiteTemporalExecutor'` |
| `readback_snapshot` | `(self, binding: 'TableBinding', descriptor: 'TemporalTableDescriptor', snapshot: 'Any')` |
| `stage_rows` | `(self, binding: 'TableBinding', descriptor: 'TemporalTableDescriptor', frame: 'pl.DataFrame', *, idempotency_key: 'str')` |
| `upsert_rows` | `(self, binding: 'TableBinding', descriptor: 'TemporalTableDescriptor', frame: 'pl.DataFrame', *, idempotency_key: 'str') -> 'OperationResult[int]'` |

### SQLiteTableReadRequest

| Field | Declared type |
| --- | --- |
| `options` | `SQLiteReadOptions` |
| `resource_limits` | `ResourceLimits` |
| `uri` | `TableURI` |

### SQLiteTemporalExecutor

| Public member | Signature or access |
| --- | --- |
| `execute` | `(self, request: 'TemporalExecutionRequest') -> 'TemporalExecutionResult'` |

### SQLiteTransaction

| Public member | Signature or access |
| --- | --- |
| `abort` | `(self) -> 'None'` |
| `commit` | `(self) -> 'None'` |
| `execute` | `(self, request: 'ExecutionRequest') -> 'ExecutionResult'` |
| `write` | `(self, request: 'TableWriteRequest') -> 'TableWriteResult'` |

## open_table_connector.postgres

| Name | Kind | Definition |
| --- | --- | --- |
| `CONNECTOR_IDENTITY` | constant | `ConnectorIdentity(connector_id='postgres', connector_version='0.1.0', contract_version='1.0')`  |
| `PostgresConnector` | class | `(connection_factory: 'Callable[..., Any] \| None' = None) -> 'None'` [source](../../packages/postgres/src/open_table_connector/postgres/reader.py) |
| `PostgresManagedTemporalStore` | class | `(database_uri: 'TableURI', artifact_root: 'str \| os.PathLike[str]', descriptor: 'TemporalTableDescriptor', *, connection_factory=None, credentials: 'Mapping[str, object] \| None' = None, metadata_schema: 'str' = '_otc_ts', clock=None, fault_injector=None, stage_id_factory=None) -> 'None'` [source](../../packages/postgres/src/open_table_connector/postgres/temporal.py) |
| `PostgresReadOptions` | class | `(table: 'str \| None' = None, query: 'str \| None' = None, parameters: 'tuple[Any, ...]' = (), key_fields: 'tuple[str, ...]' = (), record_id_field: 'str \| None' = None) -> None` [source](../../packages/postgres/src/open_table_connector/postgres/reader.py) |
| `PostgresTableReadRequest` | class | `(uri: 'TableURI', resource_limits: 'ResourceLimits' = <factory>, options: 'PostgresReadOptions' = <factory>, credentials: 'Mapping[str, Any]' = <factory>) -> None` [source](../../packages/postgres/src/open_table_connector/postgres/reader.py) |
| `PostgresTemporalExecutor` | class | `(descriptor: 'TemporalTableDescriptor', physical_table: 'str', *, managed_store: 'PostgresManagedTemporalStore \| None' = None, connection_factory=None, credentials: 'Mapping[str, object] \| None' = None) -> 'None'` [source](../../packages/postgres/src/open_table_connector/postgres/temporal.py) |
| `PostgresTransaction` | class | `(connector: 'PostgresConnector', uri: 'TableURI', connection: 'Any') -> 'None'` [source](../../packages/postgres/src/open_table_connector/postgres/reader.py) |
| `TABLE_EXECUTE_CAPABILITY` | constant | `CapabilityIdentity(capability_id='table.execute', capability_version='1.0')`  |
| `TABLE_INSPECT_CAPABILITY` | constant | `CapabilityIdentity(capability_id='table.inspect', capability_version='1.0')`  |
| `TABLE_READ_ARROW_CAPABILITY` | constant | `CapabilityIdentity(capability_id='table.read.arrow', capability_version='1.0')`  |
| `TABLE_READ_POLARS_CAPABILITY` | constant | `CapabilityIdentity(capability_id='table.read.polars', capability_version='1.0')`  |
| `TABLE_WRITE_CAPABILITY` | constant | `CapabilityIdentity(capability_id='table.write', capability_version='1.0')`  |
| `lower_postgres` | function | `(plan: 'PortableTemporalPlan', descriptor: 'TemporalTableDescriptor', physical_table: 'str') -> 'PreparedTemporalQuery'` [source](../../packages/postgres/src/open_table_connector/postgres/temporal.py) |

### PostgresConnector

| Public member | Signature or access |
| --- | --- |
| `abort` | `(self) -> 'None'` |
| `begin` | `(self, uri: 'TableURI \| None' = None) -> 'PostgresTransaction'` |
| `commit` | `(self) -> 'None'` |
| `execute` | `(self, request: 'ExecutionRequest') -> 'ExecutionResult'` |
| `inspect` | `(self, request: 'InspectRequest') -> 'TableInspection'` |
| `read_arrow` | `(self, request: 'PostgresTableReadRequest') -> 'ArrowReadResult'` |
| `read_native_sql` | `(self, request: 'ExecutionRequest') -> 'ArrowReadResult'` |
| `read_polars` | `(self, request: 'PostgresTableReadRequest') -> 'PolarsReadResult'` |
| `resolve` | `(self, uri: 'TableURI', context: 'ResolveContext') -> 'ResolvedTable'` |
| `write` | `(self, request: 'TableWriteRequest') -> 'TableWriteResult'` |

### PostgresManagedTemporalStore

| Public member | Signature or access |
| --- | --- |
| `abort` | `(self, request: 'ManagedAbortRequest') -> 'ManagedAbortReceipt'` |
| `commit` | `(self, request: 'ManagedCommitRequest') -> 'ManagedCommitReceipt'` |
| `ensure_schema` | `(self, credentials: 'Mapping[str, object] \| None' = None) -> 'None'` |
| `read_snapshot` | `(self, target: 'TableURI', snapshot_reference: 'str', bounds: 'ResourceBounds', *, snapshot_id: 'str \| None' = None, credential_values: 'Mapping[str, object] \| None' = None) -> 'pa.Table'` |
| `readback` | `(self, request: 'ManagedReadbackRequest') -> 'ManagedReadbackResult'` |
| `stage` | `(self, request: 'ManagedStageRequest') -> 'ManagedStageReceipt'` |

### PostgresReadOptions

| Field | Declared type |
| --- | --- |
| `key_fields` | `tuple[str, ...]` |
| `parameters` | `tuple[Any, ...]` |
| `query` | `str \| None` |
| `record_id_field` | `str \| None` |
| `table` | `str \| None` |

### PostgresTableReadRequest

| Field | Declared type |
| --- | --- |
| `credentials` | `Mapping[str, Any]` |
| `options` | `PostgresReadOptions` |
| `resource_limits` | `ResourceLimits` |
| `uri` | `TableURI` |

### PostgresTemporalExecutor

| Public member | Signature or access |
| --- | --- |
| `execute` | `(self, request: 'TemporalExecutionRequest') -> 'TemporalExecutionResult'` |

### PostgresTransaction

| Public member | Signature or access |
| --- | --- |
| `abort` | `(self) -> 'None'` |
| `commit` | `(self) -> 'None'` |
| `execute` | `(self, request: 'ExecutionRequest') -> 'ExecutionResult'` |
| `write` | `(self, request: 'TableWriteRequest') -> 'TableWriteResult'` |

## open_table_connector.google_sheets

| Name | Kind | Definition |
| --- | --- | --- |
| `GOOGLE_SHEETS_MAX_RESPONSE_BYTES` | constant | `8388608`  |
| `GoogleSheetsCliAdapter` | class | `(connector: 'GoogleSheetsConnector') -> None` [source](../../packages/google_sheets/src/open_table_connector/google_sheets/cli_adapter.py) |
| `GoogleSheetsConnector` | class | `(transport: 'SheetsTransport \| None' = None, *, access_token: 'str \| None' = None, timeout: 'int' = 30, api_endpoint: 'str' = 'https://sheets.googleapis.com')` [source](../../packages/google_sheets/src/open_table_connector/google_sheets/connector.py) |
| `GoogleSheetsFormulaExtension` | class | `(connector: 'GoogleSheetsConnector \| None' = None, *, transport: 'SheetsTransport \| None' = None, access_token: 'str \| None' = None, timeout: 'int' = 30, api_endpoint: 'str' = 'https://sheets.googleapis.com') -> 'None'` [source](../../packages/google_sheets/src/open_table_connector/google_sheets/formula.py) |
| `GoogleSheetsReadOptions` | class | `(range: 'str \| None' = None, sheet: 'str \| None' = None, header_row: 'int' = 1) -> None` [source](../../packages/google_sheets/src/open_table_connector/google_sheets/connector.py) |
| `GoogleSheetsTableReadRequest` | class | `(uri: 'TableURI', resource_limits: 'ResourceLimits' = <factory>, options: 'GoogleSheetsReadOptions' = <factory>) -> None` [source](../../packages/google_sheets/src/open_table_connector/google_sheets/connector.py) |
| `google_sheets_cli_plugin` | function | `() -> 'PluginDescriptor'` [source](../../packages/google_sheets/src/open_table_connector/google_sheets/cli_adapter.py) |

### GoogleSheetsCliAdapter

| Field | Declared type |
| --- | --- |
| `capabilities` | `tuple[CapabilityIdentity, ...]` |
| `connector` | `GoogleSheetsConnector` |
| `hosts` | `tuple[str, ...]` |
| `identity` | `ConnectorIdentity` |
| `modes` | `tuple[TableMode, ...]` |
| `schemes` | `tuple[str, ...]` |

| Public member | Signature or access |
| --- | --- |
| `formula_extension_for` | `(self) -> 'CompositeFormulaConnectorExtension'` |
| `inspect` | `(self, endpoint: 'AdapterEndpoint', options: 'AdapterOptions') -> 'TableInspection'` |
| `preflight_write` | `(self, endpoint: 'AdapterEndpoint', options: 'AdapterOptions') -> 'None'` |
| `read` | `(self, endpoint: 'AdapterEndpoint', options: 'AdapterOptions') -> 'ArrowReadResult'` |
| `write` | `(self, endpoint: 'AdapterEndpoint', table: 'pa.Table', options: 'AdapterOptions') -> 'TableWriteResult'` |

### GoogleSheetsConnector

| Public member | Signature or access |
| --- | --- |
| `formula_extension_for` | `(self)` |
| `inspect` | `(self, request: 'InspectRequest')` |
| `read_arrow` | `(self, request)` |
| `read_polars` | `(self, request)` |
| `resolve` | `(self, uri: 'TableURI', context: 'ResolveContext') -> 'ResolvedTable'` |
| `workbook_create` | `(self, uri: 'str', *, profile: 'str' = 'general/1.0', limits=None)` |
| `workbook_list_worksheets` | `(self, uri: 'TableURI \| str') -> 'tuple[str, ...]'` |
| `workbook_open` | `(self, uri: 'str', *, limits=None)` |
| `workbook_read_range` | `(self, uri: 'TableURI \| str', worksheet: 'str', address: 'str') -> 'list[list[Any]]'` |
| `workbook_write_range` | `(self, uri: 'TableURI \| str', worksheet: 'str', address: 'str', values: 'list[list[Any]]') -> 'None'` |
| `write` | `(self, request: 'TableWriteRequest') -> 'TableWriteResult'` |

### GoogleSheetsFormulaExtension

| Public member | Signature or access |
| --- | --- |
| `bind_grid` | `(self, request: 'otf.GridFormulaBindRequest') -> 'otf.FormulaExtensionResult[otf.GridFormulaBinding]'` |
| `read_grid` | `(self, request: 'otf.GridFormulaReadRequest') -> 'otf.FormulaExtensionResult[otf.GridFormulaObservation]'` |
| `read_grid_values` | `(self, request: 'otf.GridFormulaValueReadRequest') -> 'otf.FormulaExtensionResult[otf.GridFormulaValueObservation]'` |
| `recalculate_grid` | `(self, request: 'otf.GridFormulaRecalculateRequest') -> 'otf.FormulaExtensionResult[otf.RecalculationObservation]'` |
| `set_grid` | `(self, request: 'otf.GridFormulaSetRequest') -> 'otf.FormulaExtensionResult[otf.FormulaMutation]'` |

### GoogleSheetsReadOptions

| Field | Declared type |
| --- | --- |
| `header_row` | `int` |
| `range` | `str \| None` |
| `sheet` | `str \| None` |

### GoogleSheetsTableReadRequest

| Field | Declared type |
| --- | --- |
| `options` | `GoogleSheetsReadOptions` |
| `resource_limits` | `ResourceLimits` |
| `uri` | `TableURI` |

## open_table_connector.maybe_sheet

| Name | Kind | Definition |
| --- | --- | --- |
| `CONNECTOR_IDENTITY` | constant | `ConnectorIdentity(connector_id='maybe_sheet', connector_version='0.1.0', contract_version='1.0')`  |
| `MaybeSheetCliAdapter` | class | `(connector: 'MaybeSheetConnector', credentials: 'dict[str, str]', timeout_seconds: 'float' = 120.0, live_materialization_evidence: 'bool' = False) -> None` [source](../../packages/maybe_sheet/src/open_table_connector/maybe_sheet/cli_adapter.py) |
| `MaybeSheetConnector` | class | `(process_client: 'ProcessClient') -> 'None'` [source](../../packages/maybe_sheet/src/open_table_connector/maybe_sheet/connector.py) |
| `MaybeSheetFieldFormulaExtension` | class | `(connector_or_process: 'MaybeSheetConnector \| ProcessClient', credentials: 'Mapping[str, str] \| None' = None, timeout: 'float \| int' = 120) -> 'None'` [source](../../packages/maybe_sheet/src/open_table_connector/maybe_sheet/field_formula.py) |
| `MaybeSheetGridFormulaExtension` | class | `(connector_or_process: 'MaybeSheetConnector \| ProcessClient', credentials: 'Mapping[str, str] \| None' = None, timeout: 'float \| int' = 120) -> 'None'` [source](../../packages/maybe_sheet/src/open_table_connector/maybe_sheet/grid_formula.py) |
| `MaybeSheetManagedTemporalStore` | class | `(process_client: 'ProcessClient', artifact_root: 'str \| os.PathLike[str]', descriptor: 'TemporalTableDescriptor', *, credentials: 'Mapping[str, str] \| None' = None) -> 'None'` [source](../../packages/maybe_sheet/src/open_table_connector/maybe_sheet/temporal.py) |
| `MaybeSheetReadRequest` | class | `(uri: 'TableURI', mode: 'TableMode', target: 'str', resource_limits: 'ResourceLimits' = <factory>, credentials: 'Mapping[str, str]' = <factory>, target_is_id: 'bool' = False) -> None` [source](../../packages/maybe_sheet/src/open_table_connector/maybe_sheet/connector.py) |
| `MaybeSheetSdkConnector` | class | `(adapter: 'Any', live_evidence: 'bool' = False) -> None` [source](../../packages/maybe_sheet/src/open_table_connector/maybe_sheet/materialization.py) |
| `MaybeSheetTemporalExecutor` | class | `(process_client: 'ProcessClient', descriptor: 'TemporalTableDescriptor', *, credential_resolver: 'Callable[[str], Mapping[str, str]] \| None' = None) -> 'None'` [source](../../packages/maybe_sheet/src/open_table_connector/maybe_sheet/temporal.py) |
| `ProcessClient` | class | `(*args, **kwargs)` [source](../../packages/maybe_sheet/src/open_table_connector/maybe_sheet/connector.py) |
| `SubprocessProcessClient` | class | `(binary: 'str' = 'mbs', timeout_seconds: 'float' = 120.0, environment: 'Mapping[str, str]' = <factory>) -> None` [source](../../packages/maybe_sheet/src/open_table_connector/maybe_sheet/process.py) |
| `TABLE_WRITE_CAPABILITY` | constant | `CapabilityIdentity(capability_id='table.write', capability_version='1.0')`  |
| `_absolute_executable` | function | `(value: 'str') -> 'str'` [source](../../packages/maybe_sheet/src/open_table_connector/maybe_sheet/process.py) |
| `maybe_sheet_cli_plugin` | function | `() -> 'PluginDescriptor'` [source](../../packages/maybe_sheet/src/open_table_connector/maybe_sheet/cli_adapter.py) |
| `probe_native_materialization` | function | `(client: 'ProcessClient') -> 'bool'` [source](../../packages/maybe_sheet/src/open_table_connector/maybe_sheet/materialization.py) |
| `probe_temporal_capabilities` | function | `(client: 'ProcessClient') -> 'frozenset[str]'` [source](../../packages/maybe_sheet/src/open_table_connector/maybe_sheet/temporal.py) |

### MaybeSheetCliAdapter

| Field | Declared type |
| --- | --- |
| `capabilities` | `tuple[CapabilityIdentity, ...]` |
| `connector` | `MaybeSheetConnector` |
| `credentials` | `dict[str, str]` |
| `hosts` | `tuple[str, ...]` |
| `identity` | `ConnectorIdentity` |
| `live_materialization_evidence` | `bool` |
| `modes` | `tuple[TableMode, ...]` |
| `schemes` | `tuple[str, ...]` |
| `timeout_seconds` | `float` |

| Public member | Signature or access |
| --- | --- |
| `bind_base_table` | `(self, endpoint: 'AdapterEndpoint', table_id: 'str') -> 'AdapterEndpoint'` |
| `formula_extension_for` | `(self) -> 'CompositeFormulaConnectorExtension'` |
| `from_context` | `(context: 'ProviderFactoryContext') -> 'MaybeSheetCliAdapter'` |
| `inspect` | `(self, endpoint: 'AdapterEndpoint', options: 'AdapterOptions') -> 'TableInspection'` |
| `preflight_write` | `(self, endpoint: 'AdapterEndpoint', options: 'AdapterOptions') -> 'None'` |
| `read` | `(self, endpoint: 'AdapterEndpoint', options: 'AdapterOptions') -> 'ArrowReadResult'` |
| `sdk_connector` | `(self)` |
| `spreadsheet_provider` | `(self)` |
| `write` | `(self, endpoint: 'AdapterEndpoint', table: 'pa.Table', options: 'AdapterOptions') -> 'TableWriteResult'` |

### MaybeSheetConnector

| Public member | Signature or access |
| --- | --- |
| `formula_extension_for` | `(self)` |
| `inspect` | `(self, request: 'MaybeSheetReadRequest')` |
| `read_arrow` | `(self, request: 'MaybeSheetReadRequest')` |
| `read_polars` | `(self, request: 'MaybeSheetReadRequest') -> 'PolarsReadResult'` |
| `spreadsheet_provider` | `(self)` |
| `write` | `(self, request: 'TableWriteRequest', *, credentials: 'Mapping[str, str] \| None' = None) -> 'TableWriteResult'` |

### MaybeSheetFieldFormulaExtension

| Public member | Signature or access |
| --- | --- |
| `bind_field` | `(self, request: 'otf.FieldFormulaBindRequest[Any]') -> 'otf.FormulaExtensionResult[otf.FieldFormulaBinding[Any]]'` |
| `read_field` | `(self, request: 'otf.FieldFormulaReadRequest[Any]') -> 'otf.FormulaExtensionResult[otf.FieldFormulaObservation]'` |
| `read_field_values` | `(self, request: 'otf.FieldFormulaValueReadRequest[Any]') -> 'otf.FormulaExtensionResult[otf.FieldFormulaValueObservation]'` |
| `recalculate_field` | `(self, request: 'otf.FieldFormulaRecalculateRequest[Any]') -> 'otf.FormulaExtensionResult[otf.RecalculationObservation]'` |
| `set_field` | `(self, request: 'otf.FieldFormulaSetRequest[Any]') -> 'otf.FormulaExtensionResult[otf.FormulaMutation]'` |

### MaybeSheetGridFormulaExtension

| Public member | Signature or access |
| --- | --- |
| `bind_grid` | `(self, request: 'otf.GridFormulaBindRequest') -> 'otf.FormulaExtensionResult[otf.GridFormulaBinding]'` |
| `read_grid` | `(self, request: 'otf.GridFormulaReadRequest') -> 'otf.FormulaExtensionResult[otf.GridFormulaObservation]'` |
| `read_grid_values` | `(self, request: 'otf.GridFormulaValueReadRequest') -> 'otf.FormulaExtensionResult[otf.GridFormulaValueObservation]'` |
| `recalculate_grid` | `(self, request: 'otf.GridFormulaRecalculateRequest') -> 'otf.FormulaExtensionResult[otf.RecalculationObservation]'` |
| `set_grid` | `(self, request: 'otf.GridFormulaSetRequest') -> 'otf.FormulaExtensionResult[otf.FormulaMutation]'` |

### MaybeSheetManagedTemporalStore

| Public member | Signature or access |
| --- | --- |
| `abort` | `(self, request: 'ManagedAbortRequest') -> 'ManagedAbortReceipt'` |
| `commit` | `(self, request: 'ManagedCommitRequest') -> 'ManagedCommitReceipt'` |
| `read_snapshot` | `(self, target: 'TableURI', snapshot_reference: 'str', bounds: 'ResourceBounds', *, snapshot_id: 'str \| None' = None) -> 'pa.Table'` |
| `readback` | `(self, request: 'ManagedReadbackRequest') -> 'ManagedReadbackResult'` |
| `stage` | `(self, request: 'ManagedStageRequest') -> 'ManagedStageReceipt'` |

### MaybeSheetReadRequest

| Field | Declared type |
| --- | --- |
| `credentials` | `Mapping[str, str]` |
| `mode` | `TableMode` |
| `resource_limits` | `ResourceLimits` |
| `target` | `str` |
| `target_is_id` | `bool` |
| `uri` | `TableURI` |

### MaybeSheetSdkConnector

| Field | Declared type |
| --- | --- |
| `adapter` | `Any` |
| `live_evidence` | `bool` |

| Public member | Signature or access |
| --- | --- |
| `capabilities` | `property (read-only)` |
| `create_table` | `(self, source: 'object', destination: 'object' = None) -> 'OperationResult[TableBinding]'` |
| `materialization` | `property (read-only)` |
| `open_table` | `(self, address: 'object') -> 'OperationResult[TableBinding]'` |
| `read_table` | `(self, binding: 'TableBinding', *, limit: 'int \| None' = None, continuation: 'str \| None' = None)` |
| `reconcile_materialization` | `(self, destination: 'BaseModeDestination', reference: 'ReconciliationReference') -> 'OperationResult[TableBinding]'` |

### MaybeSheetTemporalExecutor

| Public member | Signature or access |
| --- | --- |
| `execute` | `(self, request: 'TemporalExecutionRequest') -> 'TemporalExecutionResult'` |

### ProcessClient

| Public member | Signature or access |
| --- | --- |
| `run` | `(self, argv: 'tuple[str, ...]', *, credentials: 'Mapping[str, str] \| None' = None, stdin: 'str \| None' = None, timeout: 'float \| int \| None' = None) -> 'Mapping[str, Any]'` |

### SubprocessProcessClient

| Field | Declared type |
| --- | --- |
| `binary` | `str` |
| `environment` | `Mapping[str, str]` |
| `timeout_seconds` | `float` |

| Public member | Signature or access |
| --- | --- |
| `run` | `(self, argv: 'tuple[str, ...]', *, credentials: 'Mapping[str, str] \| None' = None, stdin: 'str \| None' = None, timeout: 'float \| int \| None' = None) -> 'Mapping[str, Any]'` |

## open_table_connector.feishu_bitable

| Name | Kind | Definition |
| --- | --- | --- |
| `FEISHU_API_ENDPOINT` | constant | `'https://open.feishu.cn/open-apis/bitable/v1'`  |
| `FEISHU_BATCH_CREATE_LIMIT` | constant | `500`  |
| `FEISHU_FORMULA_FIELD_TYPE` | constant | `20`  |
| `FEISHU_MAX_RESPONSE_BYTES` | constant | `8388608`  |
| `FEISHU_RECORD_ID_FIELD` | constant | `'_record_id'`  |
| `FeishuBitableCliAdapter` | class | `(connector: 'FeishuBitableConnector', hosts: 'tuple[str, ...]' = ()) -> None` [source](../../packages/feishu_bitable/src/open_table_connector/feishu_bitable/cli_adapter.py) |
| `FeishuBitableConnector` | class | `(transport: 'FeishuTransport \| None' = None, *, tenant_access_token: 'str \| None' = None, timeout: 'int' = 30, api_endpoint: 'str' = 'https://open.feishu.cn/open-apis/bitable/v1')` [source](../../packages/feishu_bitable/src/open_table_connector/feishu_bitable/connector.py) |
| `FeishuBitableFieldFormulaExtension` | class | `(connector_or_transport: 'FeishuBitableConnector \| FeishuTransport', *, tenant_access_token: 'str \| None' = None, timeout: 'int \| float' = 30, api_endpoint: 'str' = 'https://open.feishu.cn/open-apis/bitable/v1') -> 'None'` [source](../../packages/feishu_bitable/src/open_table_connector/feishu_bitable/formula.py) |
| `FeishuBitableFormulaExtension` | class | `(connector_or_transport: 'FeishuBitableConnector \| FeishuTransport', *, tenant_access_token: 'str \| None' = None, timeout: 'int \| float' = 30, api_endpoint: 'str' = 'https://open.feishu.cn/open-apis/bitable/v1') -> 'None'` [source](../../packages/feishu_bitable/src/open_table_connector/feishu_bitable/formula.py) |
| `FeishuBitableReadOptions` | class | `(field_names: 'tuple[str, ...]' = ()) -> None` [source](../../packages/feishu_bitable/src/open_table_connector/feishu_bitable/connector.py) |
| `FeishuBitableTableReadRequest` | class | `(uri: 'TableURI', resource_limits: 'ResourceLimits' = <factory>, options: 'FeishuBitableReadOptions' = <factory>) -> None` [source](../../packages/feishu_bitable/src/open_table_connector/feishu_bitable/connector.py) |
| `feishu_bitable_cli_plugin` | function | `() -> 'PluginDescriptor'` [source](../../packages/feishu_bitable/src/open_table_connector/feishu_bitable/cli_adapter.py) |

### FeishuBitableCliAdapter

| Field | Declared type |
| --- | --- |
| `capabilities` | `tuple[CapabilityIdentity, ...]` |
| `connector` | `FeishuBitableConnector` |
| `hosts` | `tuple[str, ...]` |
| `identity` | `ConnectorIdentity` |
| `modes` | `tuple[TableMode, ...]` |
| `schemes` | `tuple[str, ...]` |

| Public member | Signature or access |
| --- | --- |
| `formula_extension_for` | `(self)` |
| `from_context` | `(context: 'ProviderFactoryContext') -> 'FeishuBitableCliAdapter'` |
| `inspect` | `(self, endpoint: 'AdapterEndpoint', options: 'AdapterOptions') -> 'TableInspection'` |
| `preflight_write` | `(self, endpoint: 'AdapterEndpoint', options: 'AdapterOptions') -> 'None'` |
| `read` | `(self, endpoint: 'AdapterEndpoint', options: 'AdapterOptions') -> 'ArrowReadResult'` |
| `write` | `(self, endpoint: 'AdapterEndpoint', table: 'pa.Table', options: 'AdapterOptions') -> 'TableWriteResult'` |

### FeishuBitableConnector

| Public member | Signature or access |
| --- | --- |
| `formula_extension_for` | `(self)` |
| `inspect` | `(self, request: 'InspectRequest')` |
| `read_arrow` | `(self, request)` |
| `read_polars` | `(self, request)` |
| `resolve` | `(self, uri: 'TableURI', context: 'ResolveContext') -> 'ResolvedTable'` |
| `write` | `(self, request: 'TableWriteRequest') -> 'TableWriteResult'` |

### FeishuBitableFieldFormulaExtension

| Public member | Signature or access |
| --- | --- |
| `bind_field` | `(self, request: 'otf.FieldFormulaBindRequest[Any]') -> 'otf.FormulaExtensionResult[otf.FieldFormulaBinding[Any]]'` |
| `read_field` | `(self, request: 'otf.FieldFormulaReadRequest[Any]') -> 'otf.FormulaExtensionResult[otf.FieldFormulaObservation]'` |
| `read_field_values` | `(self, request: 'otf.FieldFormulaValueReadRequest[Any]') -> 'otf.FormulaExtensionResult[otf.FieldFormulaValueObservation]'` |
| `recalculate_field` | `(self, request: 'otf.FieldFormulaRecalculateRequest[Any]') -> 'otf.FormulaExtensionResult[otf.RecalculationObservation]'` |
| `set_field` | `(self, request: 'otf.FieldFormulaSetRequest[Any]') -> 'otf.FormulaExtensionResult[otf.FormulaMutation]'` |

### FeishuBitableFormulaExtension

| Public member | Signature or access |
| --- | --- |
| `bind_field` | `(self, request: 'otf.FieldFormulaBindRequest[Any]') -> 'otf.FormulaExtensionResult[otf.FieldFormulaBinding[Any]]'` |
| `read_field` | `(self, request: 'otf.FieldFormulaReadRequest[Any]') -> 'otf.FormulaExtensionResult[otf.FieldFormulaObservation]'` |
| `read_field_values` | `(self, request: 'otf.FieldFormulaValueReadRequest[Any]') -> 'otf.FormulaExtensionResult[otf.FieldFormulaValueObservation]'` |
| `recalculate_field` | `(self, request: 'otf.FieldFormulaRecalculateRequest[Any]') -> 'otf.FormulaExtensionResult[otf.RecalculationObservation]'` |
| `set_field` | `(self, request: 'otf.FieldFormulaSetRequest[Any]') -> 'otf.FormulaExtensionResult[otf.FormulaMutation]'` |

### FeishuBitableReadOptions

| Field | Declared type |
| --- | --- |
| `field_names` | `tuple[str, ...]` |

### FeishuBitableTableReadRequest

| Field | Declared type |
| --- | --- |
| `options` | `FeishuBitableReadOptions` |
| `resource_limits` | `ResourceLimits` |
| `uri` | `TableURI` |

## open_table_connector.dbt

| Name | Kind | Definition |
| --- | --- | --- |
| `CONNECTOR_IDENTITY` | constant | `ConnectorIdentity(connector_id='dbt', connector_version='0.1.0', contract_version='1.0')`  |
| `DbtCompileRequest` | class | `(project_dir: 'Path', select: 'tuple[str, ...]' = (), exclude: 'tuple[str, ...]' = (), vars: 'Mapping[str, Any]' = <factory>, target: 'str \| None' = None) -> None` [source](../../packages/dbt/src/open_table_connector/dbt/connector.py) |
| `DbtConnector` | class | `(runner: 'Callable[[tuple[str, ...], Path], Mapping[str, Any]] \| None' = None) -> 'None'` [source](../../packages/dbt/src/open_table_connector/dbt/connector.py) |
| `DbtPreparedOperation` | class | `(invocation_id: 'str', argv: 'tuple[str, ...]', project_dir: 'Path', compiled_artifacts: 'Mapping[str, bytes]', manifest_ref: 'str \| None' = None, run_argv: 'tuple[str, ...]' = (), metadata: 'Mapping[str, Any]' = <factory>) -> None` [source](../../packages/dbt/src/open_table_connector/dbt/connector.py) |
| `DbtRunResult` | class | `(invocation_id: 'str', status: 'str', run_results: 'bytes \| None' = None, artifact_refs: 'Mapping[str, str]' = <factory>) -> None` [source](../../packages/dbt/src/open_table_connector/dbt/connector.py) |

### DbtCompileRequest

| Field | Declared type |
| --- | --- |
| `exclude` | `tuple[str, ...]` |
| `project_dir` | `Path` |
| `select` | `tuple[str, ...]` |
| `target` | `str \| None` |
| `vars` | `Mapping[str, Any]` |

### DbtConnector

| Public member | Signature or access |
| --- | --- |
| `cancel` | `(self, operation: 'DbtPreparedOperation') -> 'DbtRunResult'` |
| `compile` | `(self, request: 'DbtCompileRequest') -> 'DbtPreparedOperation'` |
| `read_artifact` | `(self, operation: 'DbtPreparedOperation', name: 'str') -> 'bytes'` |
| `readback` | `(self, operation: 'DbtPreparedOperation', relation: 'str') -> 'Mapping[str, Any]'` |
| `run` | `(self, operation: 'DbtPreparedOperation') -> 'DbtRunResult'` |

### DbtPreparedOperation

| Field | Declared type |
| --- | --- |
| `argv` | `tuple[str, ...]` |
| `compiled_artifacts` | `Mapping[str, bytes]` |
| `invocation_id` | `str` |
| `manifest_ref` | `str \| None` |
| `metadata` | `Mapping[str, Any]` |
| `project_dir` | `Path` |
| `run_argv` | `tuple[str, ...]` |

| Public member | Signature or access |
| --- | --- |
| `artifact_hash` | `property (read-only)` |

### DbtRunResult

| Field | Declared type |
| --- | --- |
| `artifact_refs` | `Mapping[str, str]` |
| `invocation_id` | `str` |
| `run_results` | `bytes \| None` |
| `status` | `str` |

## open_table_connector.conformance

| Name | Kind | Definition |
| --- | --- | --- |
| `FieldFormulaCase` | class | `(set_expression: 'otf.FormulaExpression', conflicting_expression: 'otf.FormulaExpression', expected_after_set: 'otf.FieldFormulaObservation', expected_values: 'otf.FieldFormulaValueObservation \| None', recalculation_scope: 'otf.FieldRecalculationScope \| None', expected_recalculation: 'otf.RecalculationObservation \| None') -> None` [source](../../packages/conformance/src/open_table_connector/conformance/formulas.py) |
| `FormulaProviderCase` | class | `(provider_id: 'str', target_kind: 'str', dialect: 'str', static_capabilities: 'tuple[CapabilityIdentity, ...]', extension_factory: 'Callable[[], object]', grid_target_factory: 'Callable[[], otf.GridFormulaTarget] \| None' = None, field_target_factory: 'Callable[[], otf.FieldFormulaTarget[Any]] \| None' = None, grid_case: 'GridFormulaCase \| None' = None, field_case: 'FieldFormulaCase \| None' = None, supports_independent_sessions: 'bool' = True, configured_live_evidence: 'str \| None' = None, security_markers: 'tuple[str, ...]' = (), security_expression: 'otf.FormulaExpression \| None' = None, security_probe_values: 'tuple[str, ...]' = ()) -> None` [source](../../packages/conformance/src/open_table_connector/conformance/formulas.py) |
| `GridFormulaCase` | class | `(formula_range: 'str', literal_range: 'str', set_expression: 'otf.FormulaExpression', conflicting_expression: 'otf.FormulaExpression', expected_after_set: 'otf.GridFormulaObservation', expected_literal_read: 'otf.GridFormulaObservation', expected_values: 'otf.GridFormulaValueObservation \| None', recalculation_scope: 'otf.GridRecalculationScope \| None', expected_recalculation: 'otf.RecalculationObservation \| None') -> None` [source](../../packages/conformance/src/open_table_connector/conformance/formulas.py) |
| `ManagedLifecycleCase` | class | `(stage_request: 'ManagedStageRequest', commit_operation_id: 'str', readback_operation_id: 'str', abort_operation_id: 'str', resource_bounds: 'ResourceBounds') -> None` [source](../../packages/conformance/src/open_table_connector/conformance/timeseries.py) |
| `ManagedLifecycleResult` | class | `(stage: 'object', commit: 'object', readback: 'ManagedReadbackResult', abort: 'object') -> None` [source](../../packages/conformance/src/open_table_connector/conformance/timeseries.py) |
| `TemporalSemanticCase` | class | `(case_id: 'str', request: 'TemporalExecutionRequest', expected: 'pa.Table') -> None` [source](../../packages/conformance/src/open_table_connector/conformance/timeseries.py) |
| `assert_arrow_polars_equal` | function | `(table: 'pa.Table', frame: 'pl.DataFrame') -> 'None'` [source](../../packages/conformance/src/open_table_connector/conformance/assertions.py) |
| `assert_field_formula_conformance` | function | `(case: 'FormulaProviderCase') -> 'None'` [source](../../packages/conformance/src/open_table_connector/conformance/formulas.py) |
| `assert_formula_receipt_safe` | function | `(receipts: 'otf.FormulaReceiptDetails \| Sequence[object]', *, forbidden_texts: 'Iterable[str]' = ()) -> 'None'` [source](../../packages/conformance/src/open_table_connector/conformance/formulas.py) |
| `assert_framework_import_free` | function | `(root: 'Path') -> 'None'` [source](../../packages/conformance/src/open_table_connector/conformance/static_suite.py) |
| `assert_grid_formula_conformance` | function | `(case: 'FormulaProviderCase') -> 'None'` [source](../../packages/conformance/src/open_table_connector/conformance/formulas.py) |
| `assert_managed_lifecycle` | function | `(store: 'ManagedTemporalStore', case: 'ManagedLifecycleCase') -> 'ManagedLifecycleResult'` [source](../../packages/conformance/src/open_table_connector/conformance/timeseries.py) |
| `assert_read_connector_conformance` | function | `(connector: 'ArrowTableReader & PolarsTableReader', request: 'TableReadRequest') -> 'None'` [source](../../packages/conformance/src/open_table_connector/conformance/assertions.py) |
| `assert_receipt_safe` | function | `(receipt: 'NeutralReceipt') -> 'None'` [source](../../packages/conformance/src/open_table_connector/conformance/assertions.py) |
| `assert_temporal_semantics` | function | `(executor: 'PortableTemporalExecutor', case: 'TemporalSemanticCase') -> 'TemporalExecutionResult'` [source](../../packages/conformance/src/open_table_connector/conformance/timeseries.py) |
| `field_formula_case_params` | function | `(cases: 'Iterable[FormulaProviderCase]', *, capability: 'CapabilityIdentity \| None' = None, configured_live_only: 'bool' = False) -> 'tuple[Any, ...]'` [source](../../packages/conformance/src/open_table_connector/conformance/formulas.py) |
| `grid_formula_case_params` | function | `(cases: 'Iterable[FormulaProviderCase]', *, capability: 'CapabilityIdentity \| None' = None, configured_live_only: 'bool' = False) -> 'tuple[Any, ...]'` [source](../../packages/conformance/src/open_table_connector/conformance/formulas.py) |
| `load_formula_cases` | function | `(*groups: 'FormulaProviderCase \| Iterable[FormulaProviderCase]') -> 'tuple[FormulaProviderCase, ...]'` [source](../../packages/conformance/src/open_table_connector/conformance/formulas.py) |
| `load_temporal_cases` | function | `(root: 'Path') -> 'tuple[TemporalSemanticCase, ...]'` [source](../../packages/conformance/src/open_table_connector/conformance/timeseries.py) |
| `run_read_suite` | function | `(connector: 'ArrowTableReader & PolarsTableReader', requests: 'Iterable[TableReadRequest]') -> 'None'` [source](../../packages/conformance/src/open_table_connector/conformance/read_suite.py) |

### FieldFormulaCase

| Field | Declared type |
| --- | --- |
| `conflicting_expression` | `otf.FormulaExpression` |
| `expected_after_set` | `otf.FieldFormulaObservation` |
| `expected_recalculation` | `otf.RecalculationObservation \| None` |
| `expected_values` | `otf.FieldFormulaValueObservation \| None` |
| `recalculation_scope` | `otf.FieldRecalculationScope \| None` |
| `set_expression` | `otf.FormulaExpression` |

### FormulaProviderCase

| Field | Declared type |
| --- | --- |
| `configured_live_evidence` | `str \| None` |
| `dialect` | `str` |
| `extension_factory` | `Callable[[], object]` |
| `field_case` | `FieldFormulaCase \| None` |
| `field_target_factory` | `Callable[[], otf.FieldFormulaTarget[Any]] \| None` |
| `grid_case` | `GridFormulaCase \| None` |
| `grid_target_factory` | `Callable[[], otf.GridFormulaTarget] \| None` |
| `provider_id` | `str` |
| `security_expression` | `otf.FormulaExpression \| None` |
| `security_markers` | `tuple[str, ...]` |
| `security_probe_values` | `tuple[str, ...]` |
| `static_capabilities` | `tuple[CapabilityIdentity, ...]` |
| `supports_independent_sessions` | `bool` |
| `target_kind` | `str` |

### GridFormulaCase

| Field | Declared type |
| --- | --- |
| `conflicting_expression` | `otf.FormulaExpression` |
| `expected_after_set` | `otf.GridFormulaObservation` |
| `expected_literal_read` | `otf.GridFormulaObservation` |
| `expected_recalculation` | `otf.RecalculationObservation \| None` |
| `expected_values` | `otf.GridFormulaValueObservation \| None` |
| `formula_range` | `str` |
| `literal_range` | `str` |
| `recalculation_scope` | `otf.GridRecalculationScope \| None` |
| `set_expression` | `otf.FormulaExpression` |

### ManagedLifecycleCase

| Field | Declared type |
| --- | --- |
| `abort_operation_id` | `str` |
| `commit_operation_id` | `str` |
| `readback_operation_id` | `str` |
| `resource_bounds` | `ResourceBounds` |
| `stage_request` | `ManagedStageRequest` |

### ManagedLifecycleResult

| Field | Declared type |
| --- | --- |
| `abort` | `object` |
| `commit` | `object` |
| `readback` | `ManagedReadbackResult` |
| `stage` | `object` |

### TemporalSemanticCase

| Field | Declared type |
| --- | --- |
| `case_id` | `str` |
| `expected` | `pa.Table` |
| `request` | `TemporalExecutionRequest` |

export type FieldType = "string" | "integer" | "number" | "boolean" | "date" | "datetime" | "unknown";
export type Support = "supported" | "unsupported" | "unknown";
export type Outcome = "succeeded" | "rejected" | "failed" | "partial" | "unknown" | "planned";
export type Commit = "not_applicable" | "not_started" | "not_committed" | "committed" | "partial" | "unknown";
export type Verification = "passed" | "failed" | "skipped" | "unavailable" | "not_applicable";

export interface MobileField {
  id: string;
  label: string;
  type: FieldType;
  nullable: boolean;
  editable: boolean;
  read_only_reason: string | null;
}

export interface MobileRecordWire {
  record_id: string;
  record_revision: string;
  values: Record<string, unknown>;
}

export interface MobileRecord {
  recordId: string;
  recordRevision: string;
  values: Record<string, unknown>;
}

export interface MobileError {
  code: string;
  message: string;
  details: Record<string, unknown>;
  requestId?: string;
}

export interface CapabilitiesResponse {
  contract: string;
  request_id: string;
  table_uri: string;
  capability: string;
  read: { support: Support; max_page_size: number; stable_record_ids: boolean };
  record_update: { support: Support; requires_expected_revision: boolean; max_fields_per_patch: number; field_types: FieldType[] };
  limits: { max_fields: number; max_patch_bytes: number };
  source: Record<string, unknown>;
}

export interface InspectionResponse {
  contract: string;
  request_id: string;
  table_uri: string;
  mode: "base" | "sheet";
  schema_fingerprint: string;
  row_count: number;
  source_revision: string;
  coordinate_convention: Record<string, unknown>;
  fields: MobileField[];
}

export interface ReadResponse {
  contract: string;
  request_id: string;
  table_uri: string;
  mode: "base" | "sheet";
  source_revision: string;
  fields: MobileField[];
  rows: MobileRecordWire[];
  next_page_token: string | null;
}

export interface UpdateResponse {
  contract: string;
  request_id: string;
  operation_id?: string | null;
  outcome?: Outcome;
  commit?: Commit;
  verification?: Verification;
  table_revision?: string | null;
  record?: MobileRecordWire | null;
  receipts?: Array<Record<string, unknown>>;
  error?: { code: string; message: string; details: Record<string, unknown> };
}

export interface DraftState {
  baseValues: Record<string, unknown>;
  values: Record<string, unknown>;
  changedFields: string[];
  validationErrors: Record<string, string>;
  idempotencyKey?: string;
  serverRecord?: MobileRecord;
}

export type MutationState = "idle" | "saving" | "conflict" | "unknown" | "error";
export type ControllerPhase = "idle" | "loading" | "ready" | "refreshing" | "loading_more" | "error" | "read_only";

export interface MobileTableState {
  phase: ControllerPhase;
  capabilities?: CapabilitiesResponse;
  inspection?: InspectionResponse;
  fields: MobileField[];
  rows: MobileRecord[];
  nextPageToken: string | null;
  sourceRevision?: string;
  drafts: Record<string, DraftState>;
  mutationStates: Record<string, MutationState>;
  lastError?: MobileError;
}

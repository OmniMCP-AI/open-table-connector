import type {
  CapabilitiesResponse, ControllerPhase, DraftState, InspectionResponse, MobileError, MobileField,
  MobileRecord, MobileTableState, MutationState, ReadResponse, UpdateResponse,
} from "./types";
import type { CapabilitiesRequest, InspectionRequest, MobileTableTransport, ReadRequest, UpdateRequest } from "./transport";
import { validateFieldValue } from "./validation";

const CONTRACT = "otc.mobile.table/1.0" as const;

export interface MobileTableControllerOptions {
  tableUri: string;
  transport: MobileTableTransport;
  requestId?: () => string;
  idempotencyKey?: () => string;
  onStateChange?: (state: MobileTableState) => void;
}

function makeId(prefix: string): string {
  const random = typeof crypto !== "undefined" && "randomUUID" in crypto ? crypto.randomUUID() : Math.random().toString(36).slice(2);
  return `${prefix}-${random}`;
}

function normalizeRecord(row: { record_id: string; record_revision: string; values: Record<string, unknown> }): MobileRecord {
  return { recordId: row.record_id, recordRevision: row.record_revision, values: { ...row.values } };
}

function normalizeError(error: { code: string; message: string; details?: Record<string, unknown> }, requestId?: string): MobileError {
  return { code: error.code, message: error.message, details: { ...(error.details ?? {}) }, requestId };
}

function cloneDraft(draft: DraftState): DraftState {
  return {
    ...draft,
    baseValues: { ...draft.baseValues },
    values: { ...draft.values },
    changedFields: [...draft.changedFields],
    validationErrors: { ...draft.validationErrors },
    serverRecord: draft.serverRecord ? { ...draft.serverRecord, values: { ...draft.serverRecord.values } } : undefined,
  };
}

export class MobileTableController {
  public state: MobileTableState = {
    phase: "idle",
    fields: [],
    rows: [],
    nextPageToken: null,
    drafts: {},
    mutationStates: {},
  };

  private readonly options: MobileTableControllerOptions;
  private generation = 0;
  private activeRead?: Promise<void>;
  private mutationInFlight = false;

  public constructor(options: MobileTableControllerOptions) {
    this.options = options;
  }

  public async load(): Promise<void> {
    if (this.activeRead) return this.activeRead;
    const generation = this.generation;
    this.setState({ phase: "loading", lastError: undefined });
    const operation = this.loadGeneration(generation);
    this.activeRead = operation;
    try { await operation; } finally { if (this.activeRead === operation) this.activeRead = undefined; }
  }

  public async refresh(): Promise<void> {
    const prior = this.activeRead;
    this.generation += 1;
    const generation = this.generation;
    this.setState({ phase: "refreshing", rows: [], nextPageToken: null, sourceRevision: undefined, lastError: undefined });
    if (prior) await prior.catch(() => undefined);
    const operation = this.loadGeneration(generation);
    this.activeRead = operation;
    try { await operation; } finally { if (this.activeRead === operation) this.activeRead = undefined; }
  }

  public async loadMore(): Promise<void> {
    if (this.activeRead || !this.state.nextPageToken || !this.state.capabilities) return;
    const generation = this.generation;
    const operation = this.readPage(generation, this.state.nextPageToken, true);
    this.activeRead = operation;
    try { await operation; } finally { if (this.activeRead === operation) this.activeRead = undefined; }
  }

  public beginEdit(recordId: string): void {
    const row = this.state.rows.find((candidate) => candidate.recordId === recordId);
    if (!row) throw new Error(`record ${recordId} was not found`);
    const values = { ...row.values };
    this.setState({ drafts: { ...this.state.drafts, [recordId]: { baseValues: values, values: { ...values }, changedFields: [], validationErrors: {} } }, mutationStates: { ...this.state.mutationStates, [recordId]: "idle" } });
  }

  public setDraftField(recordId: string, fieldId: string, value: unknown): void {
    const draft = this.state.drafts[recordId];
    if (!draft) throw new Error(`record ${recordId} is not being edited`);
    const field = this.state.fields.find((candidate) => candidate.id === fieldId);
    if (!field) throw new Error(`field ${fieldId} was not found`);
    const validationError = validateFieldValue(field, value);
    const nextErrors = { ...draft.validationErrors };
    if (validationError) nextErrors[fieldId] = validationError; else delete nextErrors[fieldId];
    const nextValues = { ...draft.values, [fieldId]: value };
    const changedFields = [...draft.changedFields];
    if (Object.is(nextValues[fieldId], draft.baseValues[fieldId])) {
      const index = changedFields.indexOf(fieldId);
      if (index >= 0) changedFields.splice(index, 1);
    } else if (!changedFields.includes(fieldId)) changedFields.push(fieldId);
    this.setState({ drafts: { ...this.state.drafts, [recordId]: { ...cloneDraft(draft), values: nextValues, changedFields, validationErrors: nextErrors } } });
  }

  public cancel(recordId: string): void {
    const drafts = { ...this.state.drafts };
    delete drafts[recordId];
    this.setState({ drafts, mutationStates: { ...this.state.mutationStates, [recordId]: "idle" } });
  }

  public async save(recordId: string): Promise<void> {
    if (this.mutationInFlight) throw new Error("mutation already in flight");
    const draft = this.state.drafts[recordId];
    const row = this.state.rows.find((candidate) => candidate.recordId === recordId);
    if (!draft || !row) throw new Error(`record ${recordId} is not being edited`);
    if (Object.keys(draft.validationErrors).length > 0) {
      this.setState({ lastError: { code: "invalid_request", message: "Fix the highlighted fields before saving.", details: {} } });
      throw new Error(Object.values(draft.validationErrors)[0] ?? "field validation failed");
    }
    if (draft.changedFields.length === 0) return;
    const idempotencyKey = draft.idempotencyKey ?? this.options.idempotencyKey?.() ?? makeId("mobile-edit");
    const patch = Object.fromEntries(draft.changedFields.map((fieldId) => [fieldId, draft.values[fieldId]]));
    const request: UpdateRequest = {
      contract: CONTRACT,
      requestId: this.requestId(),
      tableUri: this.options.tableUri,
      recordId,
      patch,
      expectedTableRevision: this.state.sourceRevision ?? "",
      expectedRecordRevision: row.recordRevision,
      idempotencyKey,
    };
    this.mutationInFlight = true;
    this.setState({ drafts: { ...this.state.drafts, [recordId]: { ...cloneDraft(draft), idempotencyKey } }, mutationStates: { ...this.state.mutationStates, [recordId]: "saving" } });
    try {
      const response = await this.options.transport.update(request);
      this.applyUpdate(recordId, response);
    } catch (error) {
      this.setState({ mutationStates: { ...this.state.mutationStates, [recordId]: "error" }, lastError: { code: "execution_failed", message: "The update could not be completed.", details: {} } });
    } finally {
      this.mutationInFlight = false;
    }
  }

  public async retry(recordId: string): Promise<void> {
    const state = this.state.mutationStates[recordId];
    if (state !== "unknown" && state !== "error" && state !== "conflict") throw new Error("record has no unresolved mutation");
    await this.save(recordId);
  }

  private async loadGeneration(generation: number): Promise<void> {
    try {
      const requestId = this.requestId();
      const baseRequest: CapabilitiesRequest = { contract: CONTRACT, requestId, tableUri: this.options.tableUri };
      const capabilities = await this.options.transport.capabilities(baseRequest);
      if (generation !== this.generation) return;
      const inspection = await this.options.transport.inspect({ ...baseRequest } satisfies InspectionRequest);
      if (generation !== this.generation) return;
      this.setState({ capabilities, inspection, fields: [...inspection.fields], phase: capabilities.record_update.support === "supported" ? "loading" : "read_only" });
      await this.readPage(generation, null, false);
    } catch (error) {
      if (generation !== this.generation) return;
      this.setState({ phase: "error", lastError: { code: "execution_failed", message: "The table could not be loaded.", details: {} } });
    }
  }

  private async readPage(generation: number, pageToken: string | null, append: boolean): Promise<void> {
    const capabilities = this.state.capabilities;
    if (!capabilities) return;
    this.setState({ phase: append ? "loading_more" : this.state.phase === "refreshing" ? "refreshing" : "loading" });
    let response: ReadResponse | undefined;
    let lastError: unknown;
    for (let attempt = 0; attempt < 2; attempt += 1) {
      try {
        response = await this.options.transport.read({ contract: CONTRACT, requestId: this.requestId(), tableUri: this.options.tableUri, pageSize: 25, pageToken, fields: this.state.fields.map((field) => field.id) });
        break;
      } catch (error) { lastError = error; }
    }
    if (!response) throw lastError ?? new Error("read failed");
    if (generation !== this.generation) return;
    const rows = response.rows.map(normalizeRecord);
    this.setState({ phase: this.state.capabilities?.record_update.support === "supported" ? "ready" : "read_only", fields: [...response.fields], rows: append ? [...this.state.rows, ...rows] : rows, nextPageToken: response.next_page_token, sourceRevision: response.source_revision });
  }

  private applyUpdate(recordId: string, response: UpdateResponse): void {
    if (response.error) {
      const state: MutationState = response.error.code === "stale_revision" ? "conflict" : "error";
      const serverValue = response.error.details.current_record as { record_id: string; record_revision: string; values: Record<string, unknown> } | undefined;
      const draft = this.state.drafts[recordId];
      this.setState({ mutationStates: { ...this.state.mutationStates, [recordId]: state }, drafts: { ...this.state.drafts, [recordId]: draft ? { ...cloneDraft(draft), serverRecord: serverValue ? normalizeRecord(serverValue) : undefined } : draft }, lastError: normalizeError(response.error, response.request_id) });
      return;
    }
    if (response.outcome === "succeeded" && response.commit === "committed" && response.verification === "passed" && response.record) {
      const canonical = normalizeRecord(response.record);
      this.setState({ rows: this.state.rows.map((row) => row.recordId === recordId ? canonical : row), sourceRevision: response.table_revision ?? this.state.sourceRevision, mutationStates: { ...this.state.mutationStates, [recordId]: "idle" } });
      const drafts = { ...this.state.drafts };
      delete drafts[recordId];
      this.setState({ drafts });
      return;
    }
    if (response.outcome === "unknown" || response.outcome === "partial") {
      this.setState({ mutationStates: { ...this.state.mutationStates, [recordId]: "unknown" }, lastError: { code: "uncertain_mutation", message: "The update needs reconciliation.", details: {}, requestId: response.request_id } });
      return;
    }
    this.setState({ mutationStates: { ...this.state.mutationStates, [recordId]: "error" }, lastError: { code: "execution_failed", message: "The update was not committed.", details: {}, requestId: response.request_id } });
  }

  private requestId(): string { return this.options.requestId?.() ?? makeId("mobile-request"); }

  private setState(patch: Partial<MobileTableState>): void {
    this.state = { ...this.state, ...patch };
    this.options.onStateChange?.(this.state);
  }
}

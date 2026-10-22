import type { MobileTableController } from "../../../core/src/controller";
import type { MobileField, MobileTableState, MutationState } from "../../../core/src/types";
import { coerceFieldInput } from "../../../core/src/validation";

export interface MobileTableViewModel {
  tabs: ["Card", "Table"];
  view: "cards" | "table";
  recordCount: number;
  rows: MobileTableState["rows"];
  fields: MobileField[];
  cardFields: MobileField[];
  refreshLabel: string;
  inlineEditing: false;
  mutationStates: Record<string, MutationState>;
  draftValues: Record<string, Record<string, unknown>>;
  canRetry: boolean;
  readOnly: boolean;
  readOnlyReason?: string;
  readOnlyLabel: string;
  phase: MobileTableState["phase"];
  errorMessage?: string;
}

export function createMobileTableViewModel(state: MobileTableState, view: "cards" | "table" = "cards"): MobileTableViewModel {
  return {
    tabs: ["Card", "Table"],
    view,
    recordCount: state.inspection?.row_count ?? state.rows.length,
    rows: state.rows,
    fields: state.fields,
    cardFields: state.fields.filter((field) => field.id !== "id").slice(0, 4),
    refreshLabel: "刷新表格",
    inlineEditing: false,
    mutationStates: state.mutationStates,
    draftValues: Object.fromEntries(Object.entries(state.drafts).map(([id, draft]) => [id, draft.values])),
    canRetry: Object.values(state.mutationStates).some((value) => value === "conflict" || value === "unknown" || value === "error"),
    readOnly: state.phase !== "ready",
    readOnlyReason: state.fields.find((field) => !field.editable && field.read_only_reason)?.read_only_reason ?? undefined,
    readOnlyLabel: state.phase !== "ready" ? `只读${state.fields.find((field) => !field.editable && field.read_only_reason)?.read_only_reason ? ` · ${state.fields.find((field) => !field.editable && field.read_only_reason)?.read_only_reason}` : ""}` : "",
    phase: state.phase,
    errorMessage: state.lastError?.message,
  };
}

export class MobileTableMiniView {
  public view: "cards" | "table" = "cards";
  private readonly widths = new Map<string, number>();

  public setView(view: "cards" | "table"): void { this.view = view; }
  public resizeColumn(fieldId: string, width: number): void { this.widths.set(fieldId, Math.min(420, Math.max(120, Math.round(width)))); }
  public columnWidth(fieldId: string): number { return this.widths.get(fieldId) ?? 180; }
}

type MiniComponentThis = {
  properties: { controller?: MobileTableController; title?: string };
  data: MobileTableViewModel & { activeRecordId?: string; columnWidths: Record<string, number>; resizeAnchors: Record<string, { startX: number; startWidth: number }> };
  setData: (data: Partial<MiniComponentThis["data"]>) => void;
  unsubscribe?: () => void;
};

function sync(this: MiniComponentThis): void {
  const controller = this.properties.controller;
  if (!controller) return;
  this.setData({ ...createMobileTableViewModel(controller.state, this.data.view), columnWidths: this.data.columnWidths });
}

declare const Component: (options: Record<string, unknown>) => void;

if (typeof Component === "function") {
  Component({
    properties: { controller: { type: Object, value: null }, title: { type: String, value: "OTC Table" } },
    data: { ...createMobileTableViewModel({ phase: "idle", fields: [], rows: [], nextPageToken: null, drafts: {}, mutationStates: {} }), activeRecordId: undefined, columnWidths: {}, resizeAnchors: {} },
    lifetimes: {
      attached(this: MiniComponentThis) {
        const controller = this.properties.controller;
        if (controller) this.unsubscribe = controller.subscribe(() => sync.call(this));
        void controller?.load().then(() => sync.call(this));
      },
      detached(this: MiniComponentThis) { this.unsubscribe?.(); this.unsubscribe = undefined; },
    },
    pageLifetimes: { show(this: MiniComponentThis) { const controller = this.properties.controller; if (controller && controller.state.phase !== "idle") void controller.refresh().then(() => sync.call(this)); } },
    methods: {
      onViewTap(this: MiniComponentThis, event: { currentTarget: { dataset: { view: "cards" | "table" } } }) { this.setData({ view: event.currentTarget.dataset.view }); },
      onRefresh(this: MiniComponentThis) { void this.properties.controller?.refresh().then(() => sync.call(this)); },
      onLoadMore(this: MiniComponentThis) { void this.properties.controller?.loadMore().then(() => sync.call(this)); },
      onRecordTap(this: MiniComponentThis, event: { currentTarget: { dataset: { recordId: string } } }) { const id = event.currentTarget.dataset.recordId; this.properties.controller?.beginEdit(id); if (this.properties.controller?.state.drafts[id]) this.setData({ activeRecordId: id }); sync.call(this); },
      onCancel(this: MiniComponentThis) { if (this.data.activeRecordId) this.properties.controller?.cancel(this.data.activeRecordId); this.setData({ activeRecordId: undefined }); sync.call(this); },
      onSave(this: MiniComponentThis) { const recordId = this.data.activeRecordId; if (recordId) void this.properties.controller?.save(recordId).then(() => { if (!this.properties.controller?.state.drafts[recordId]) this.setData({ activeRecordId: undefined }); sync.call(this); }); },
      onInput(this: MiniComponentThis, event: { currentTarget: { dataset: { fieldId: string } }; detail: { value: unknown } }) { const recordId = this.data.activeRecordId; const fieldId = event.currentTarget.dataset.fieldId; const field = this.properties.controller?.state.fields.find((candidate) => candidate.id === fieldId); const value = typeof event.detail.value === "string" && field ? coerceFieldInput(field, event.detail.value) : event.detail.value; if (recordId) this.properties.controller?.setDraftField(recordId, fieldId, value); sync.call(this); },
      onResizeStart(this: MiniComponentThis, event: { currentTarget: { dataset: { fieldId: string } }; changedTouches: Array<{ clientX: number }> }) { const fieldId = event.currentTarget.dataset.fieldId; const startX = event.changedTouches[0]?.clientX ?? 0; this.setData({ resizeAnchors: { ...this.data.resizeAnchors, [fieldId]: { startX, startWidth: this.data.columnWidths[fieldId] ?? 180 } } }); },
      onResizeMove(this: MiniComponentThis, event: { currentTarget: { dataset: { fieldId: string } }; changedTouches: Array<{ clientX: number }> }) { const fieldId = event.currentTarget.dataset.fieldId; const anchor = this.data.resizeAnchors[fieldId]; if (!anchor) return; const clientX = event.changedTouches[0]?.clientX ?? anchor.startX; const width = Math.min(420, Math.max(120, anchor.startWidth + clientX - anchor.startX)); this.setData({ columnWidths: { ...this.data.columnWidths, [fieldId]: width } }); },
      onResizeEnd(this: MiniComponentThis, event: { currentTarget: { dataset: { fieldId: string } } }) { const fieldId = event.currentTarget.dataset.fieldId; const resizeAnchors = { ...this.data.resizeAnchors }; delete resizeAnchors[fieldId]; this.setData({ resizeAnchors }); },
    },
  });
}

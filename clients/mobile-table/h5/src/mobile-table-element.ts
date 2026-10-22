import { MobileTableController } from "../../core/src/controller";
import type { DraftState, MobileField, MobileRecord, MobileTableState } from "../../core/src/types";
import { coerceFieldInput } from "../../core/src/validation";
import { MOBILE_TABLE_STYLES } from "./styles";

type View = "cards" | "table";

export class MobileTableElement extends HTMLElement {
  private controller?: MobileTableController;
  private currentView: View = "cards";
  private readonly widths = new Map<string, number>();
  private lastFocusedRow?: string;
  private observer?: IntersectionObserver;
  private unsubscribe?: () => void;

  public setController(controller: MobileTableController): void {
    this.unsubscribe?.();
    this.controller = controller;
    this.unsubscribe = controller.subscribe(() => this.render());
    this.render();
  }

  public get view(): View { return this.currentView; }
  public set view(value: View) { this.currentView = value; this.render(); }

  public columnWidth(fieldId: string): number { return this.widths.get(fieldId) ?? 180; }

  public resizeColumn(fieldId: string, width: number): void {
    this.widths.set(fieldId, Math.min(420, Math.max(120, Math.round(width))));
    this.render();
  }

  public connectedCallback(): void {
    this.render();
  }

  public disconnectedCallback(): void {
    this.observer?.disconnect();
    this.unsubscribe?.();
    this.unsubscribe = undefined;
  }

  private render(): void {
    const state = this.controller?.state;
    if (!state) {
      this.innerHTML = `<style>${MOBILE_TABLE_STYLES}</style><div class="mobile-table" aria-busy="true"></div>`;
      return;
    }
    const count = state.inspection?.row_count ?? state.rows.length;
    const title = this.getAttribute("title") ?? "OTC Table";
    this.innerHTML = `<style>${MOBILE_TABLE_STYLES}</style>
      <section class="mobile-table" aria-label="${this.escape(title)}">
        <header class="table-header"><h1>${this.escape(title)}</h1><span class="mode-status">${state.phase === "read_only" ? `只读${state.fields.find((field) => field.read_only_reason)?.read_only_reason ? ` · ${this.escape(state.fields.find((field) => field.read_only_reason)?.read_only_reason ?? "")}` : ""}` : "可编辑"}</span></header>
        <div class="control-row">
          <div class="view-tabs" role="tablist" aria-label="查看方式">
            ${this.tab("cards", "Card")}${this.tab("table", "Table")}
          </div>
          <span class="record-count">${count} 条记录</span>
          <div class="sync-actions"><span class="sync-dot" role="status" aria-label="已同步"></span><button class="refresh" type="button" aria-label="刷新表格">↻</button></div>
        </div>
        ${this.renderBody(state)}
        ${Object.keys(state.drafts)[0] ? this.renderSheet(state, Object.keys(state.drafts)[0]) : ""}
        <div class="announcement" aria-live="polite">${this.announcement(state)}</div>
      </section>`;
    this.bindEvents();
  }

  private tab(view: View, label: string): string {
    return `<button type="button" role="tab" data-view="${view}" aria-selected="${this.currentView === view}">${label}</button>`;
  }

  private renderBody(state: MobileTableState): string {
    if (state.phase === "loading" || state.phase === "refreshing") return `<div class="loading" aria-busy="true">正在加载…</div>`;
    if (state.phase === "error") return `<div class="error" role="alert">${this.escape(state.lastError?.message ?? "加载失败")}<button type="button" class="retry">重新加载</button></div>`;
    if (state.rows.length === 0) return `<div class="empty">暂无记录<button type="button" class="retry">刷新</button></div>`;
    return this.currentView === "cards" ? this.renderCards(state) : this.renderTable(state);
  }

  private renderCards(state: MobileTableState): string {
    return `<div class="card-grid" data-view="cards">${state.rows.map((row) => this.renderCard(row, state.fields)).join("")}</div><div data-load-more-sentinel aria-hidden="true"></div>`;
  }

  private renderCard(row: MobileRecord, fields: MobileField[]): string {
    const identity = row.values.id ?? row.recordId;
    const useful = fields.filter((field) => field.id !== "id").slice(0, 4);
    return `<button type="button" class="record-card" data-record-id="${this.escape(row.recordId)}"><strong>${this.escape(String(identity ?? ""))}</strong><dl>${useful.map((field) => `<dt>${this.escape(field.label)}</dt><dd>${this.escape(this.display(row.values[field.id]))}</dd>`).join("")}</dl></button>`;
  }

  private renderTable(state: MobileTableState): string {
    const columns = state.fields;
    const headers = columns.map((field) => `<th scope="col" data-column="${this.escape(field.id)}" style="width:${this.columnWidth(field.id)}px">${this.escape(field.label)}<button class="resize-handle" type="button" aria-label="调整${this.escape(field.label)}列宽" data-resize="${this.escape(field.id)}"></button></th>`).join("");
    const rows = state.rows.map((row) => `<tr tabindex="0" role="button" data-record-id="${this.escape(row.recordId)}">${columns.map((field) => `<td data-column="${this.escape(field.id)}" style="width:${this.columnWidth(field.id)}px">${this.escape(this.display(row.values[field.id]))}</td>`).join("")}</tr>`).join("");
    return `<div class="table-scroll" data-view="table"><table class="data-table"><thead><tr>${headers}</tr></thead><tbody>${rows}</tbody></table></div><div data-load-more-sentinel aria-hidden="true"></div>`;
  }

  private renderSheet(state: MobileTableState, recordId: string): string {
    const draft = state.drafts[recordId];
    if (!draft) return "";
    const fields = state.fields.map((field) => {
      const value = draft.values[field.id];
      const readonly = !field.editable || field.type === "unknown";
      const inputType = field.type === "integer" || field.type === "number" ? "number" : field.type === "date" ? "date" : field.type === "datetime" ? "datetime-local" : "text";
      const step = field.type === "integer" ? " step=\"1\"" : "";
      const input = field.type === "boolean" ? `<input type="checkbox" name="${this.escape(field.id)}" ${value === true ? "checked" : ""} ${readonly ? "disabled" : ""}/>` : `<input type="${inputType}"${step} name="${this.escape(field.id)}" value="${this.escape(value == null ? "" : String(value))}" ${readonly ? "readonly" : ""}/>`;
      return `<label>${this.escape(field.label)}${input}<small>${this.escape(draft.validationErrors[field.id] ?? field.read_only_reason ?? "")}</small></label>`;
    }).join("");
    const saving = state.mutationStates[recordId] === "saving";
    return `<div class="sheet-backdrop" data-record-sheet><section class="sheet" role="dialog" aria-modal="true" aria-label="编辑记录"><h2>编辑记录</h2><form>${fields}<div class="sheet-actions"><button type="button" class="cancel">取消</button><button type="button" class="save" ${saving ? "disabled" : ""}>保存</button></div></form></section></div>`;
  }

  private bindEvents(): void {
    const controller = this.controller;
    if (!controller) return;
    this.querySelectorAll<HTMLButtonElement>("[data-view]").forEach((button) => button.addEventListener("click", () => { this.currentView = button.dataset.view as View; this.render(); }));
    this.querySelector<HTMLButtonElement>(".refresh")?.addEventListener("click", async () => { await controller.refresh(); this.render(); });
    this.querySelector<HTMLButtonElement>(".retry")?.addEventListener("click", async () => { await controller.refresh(); this.render(); });
    this.querySelectorAll<HTMLElement>("[data-record-id]").forEach((row) => { const open = () => { const id = row.dataset.recordId; if (!id) return; this.lastFocusedRow = id; controller.beginEdit(id); if (!controller.state.drafts[id]) return; this.render(); this.querySelector<HTMLButtonElement>("[data-record-sheet] .cancel")?.focus(); }; row.addEventListener("click", open); row.addEventListener("keydown", (event) => { if (event.key === "Enter" || event.key === " ") { event.preventDefault(); open(); } }); });
    const recordId = Object.keys(controller.state.drafts).find((id) => controller.state.drafts[id]);
    if (recordId) {
      const draft = controller.state.drafts[recordId];
      this.querySelectorAll<HTMLInputElement>("[data-record-sheet] input").forEach((input) => input.addEventListener("change", () => { const fieldId = input.name; const field = controller.state.fields.find((candidate) => candidate.id === fieldId); const value = input.type === "checkbox" ? input.checked : field ? coerceFieldInput(field, input.value) : input.value; controller.setDraftField(recordId, fieldId, value); this.render(); }));
      this.querySelector<HTMLButtonElement>("[data-record-sheet] .cancel")?.addEventListener("click", () => { controller.cancel(recordId); this.render(); this.querySelector<HTMLElement>(`[data-record-id="${CSS.escape(recordId)}"]`)?.focus(); });
      this.querySelector<HTMLButtonElement>("[data-record-sheet] .save")?.addEventListener("click", async () => { await controller.save(recordId); this.render(); if (!controller.state.drafts[recordId]) this.querySelector<HTMLElement>(`[data-record-id="${CSS.escape(recordId)}"]`)?.focus(); });
      void draft;
    }
    this.bindResizeHandles();
    const sentinel = this.querySelector<HTMLElement>("[data-load-more-sentinel]");
    if (sentinel && typeof IntersectionObserver !== "undefined") {
      this.observer?.disconnect();
      this.observer = new IntersectionObserver((entries) => { if (entries.some((entry) => entry.isIntersecting)) void controller.loadMore().then(() => this.render()); });
      this.observer.observe(sentinel);
    }
  }

  private bindResizeHandles(): void {
    this.querySelectorAll<HTMLButtonElement>("[data-resize]").forEach((handle) => {
      handle.addEventListener("pointerdown", (event) => {
        const fieldId = handle.dataset.resize;
        if (!fieldId) return;
        const startX = event.clientX;
        const startWidth = this.columnWidth(fieldId);
        const move = (moveEvent: PointerEvent) => this.resizeColumn(fieldId, startWidth + moveEvent.clientX - startX);
        const up = () => { window.removeEventListener("pointermove", move); window.removeEventListener("pointerup", up); };
        window.addEventListener("pointermove", move);
        window.addEventListener("pointerup", up);
      });
    });
  }

  private announcement(state: MobileTableState): string { return state.phase === "loading" ? "正在加载记录" : state.phase === "error" ? "加载失败" : Object.values(state.mutationStates).includes("saving") ? "正在保存记录" : Object.values(state.mutationStates).includes("conflict") ? "记录发生冲突" : Object.values(state.mutationStates).includes("unknown") ? "记录待确认" : ""; }
  private display(value: unknown): string { return value === null ? "空" : typeof value === "boolean" ? (value ? "是" : "否") : String(value ?? ""); }
  private escape(value: string): string { return value.replace(/[&<>"']/g, (char) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[char] ?? char); }
}

export { MOBILE_TABLE_STYLES };

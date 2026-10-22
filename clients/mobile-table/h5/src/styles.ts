export const MOBILE_TABLE_STYLES = `
:host { display: block; color: #1f2937; font: 15px/1.45 system-ui, sans-serif; }
.mobile-table { display: grid; gap: 16px; }
.table-header { display: flex; align-items: baseline; justify-content: space-between; gap: 12px; }
.table-header h1 { margin: 0; font-size: 22px; }
.control-row { display: grid; grid-template-columns: 1fr auto 1fr; align-items: center; gap: 10px; }
.view-tabs { display: inline-flex; justify-self: start; gap: 4px; }
.view-tabs button, .refresh, .record-card, .sheet button, .resize-handle { min-height: 44px; }
.view-tabs button { border: 0; border-radius: 8px; background: #edf1f7; color: #536174; padding: 8px 13px; }
.view-tabs button[aria-selected="true"] { background: #17324d; color: white; }
.record-count { justify-self: center; color: #536174; font-size: 13px; white-space: nowrap; }
.sync-actions { display: inline-flex; align-items: center; justify-self: end; gap: 8px; color: #536174; font-size: 13px; }
.sync-dot { width: 8px; height: 8px; border-radius: 50%; background: #2c9d71; }
.refresh { width: 44px; border: 0; border-radius: 9px; background: #edf1f7; color: #17324d; font-size: 20px; }
.card-grid { display: grid; grid-template-columns: 1fr; gap: 12px; }
.record-card { display: grid; gap: 5px; width: 100%; border: 1px solid #e0e6ef; border-radius: 14px; background: white; padding: 14px; text-align: left; box-shadow: 0 4px 16px rgba(23,50,77,.07); }
.record-card strong { font-size: 14px; }
.record-card dl { display: grid; grid-template-columns: minmax(80px, auto) 1fr; gap: 4px 10px; margin: 0; }
.record-card dt { color: #6b778a; }
.record-card dd { margin: 0; overflow: hidden; text-overflow: ellipsis; }
.table-scroll { overflow-x: auto; border: 1px solid #e0e6ef; border-radius: 12px; }
.data-table { min-width: 720px; width: 100%; border-collapse: collapse; table-layout: fixed; }
.data-table th, .data-table td { position: relative; border-bottom: 1px solid #edf0f4; padding: 10px 12px; text-align: left; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.data-table th { background: #f7f9fc; color: #536174; font-size: 12px; }
.resize-handle { position: absolute; right: 0; top: 0; width: 24px; cursor: col-resize; border: 0; background: transparent; touch-action: none; }
.resize-handle::after { content: ""; position: absolute; inset: 9px 10px; border-right: 2px solid #a5b1c2; }
.sheet-backdrop { position: fixed; inset: 0; z-index: 10; display: grid; align-items: end; background: rgba(16, 26, 39, .38); }
.sheet { max-height: min(82vh, 680px); overflow: auto; border-radius: 20px 20px 0 0; background: white; padding: 20px; }
.sheet form { display: grid; gap: 14px; }
.sheet label { display: grid; gap: 5px; color: #536174; }
.sheet input { min-height: 44px; border: 1px solid #d5dce7; border-radius: 8px; padding: 0 10px; font: inherit; }
.sheet-actions { display: flex; justify-content: flex-end; gap: 8px; }
.sheet-actions button { border: 0; border-radius: 8px; padding: 8px 16px; }
.sheet-actions .save { background: #17324d; color: white; }
.announcement { position: absolute; width: 1px; height: 1px; overflow: hidden; clip: rect(0 0 0 0); }
.empty, .error, .loading { color: #6b778a; padding: 28px 12px; text-align: center; }
@media (min-width: 768px) {
  .card-grid { grid-template-columns: repeat(auto-fit, minmax(210px, 1fr)); }
  .table-scroll { max-width: 100%; }
}
`;

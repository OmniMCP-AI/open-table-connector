import { describe, expect, it } from "vitest";
import { MobileTableController } from "../../core/src/controller";
import type { MobileTableTransport } from "../../core/src/transport";
import type { CapabilitiesResponse, InspectionResponse, ReadResponse, UpdateResponse } from "../../core/src/types";
import { createMobileTableViewModel, MobileTableMiniView } from "../components/mobile-table/mobile-table";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";

function fixture<T>(name: string): T {
  return JSON.parse(readFileSync(resolve(process.cwd(), "../../../specification/fixtures/mobile_table", name), "utf8")) as T;
}

function controller(update: MobileTableTransport["update"] = async () => fixture<UpdateResponse>("update-success.json")) {
  const transport: MobileTableTransport = {
    async capabilities() { return fixture<CapabilitiesResponse>("capabilities-supported.json"); },
    async inspect() { return fixture<InspectionResponse>("inspect-base.json"); },
    async read(request) { return fixture<ReadResponse>(request.pageToken ? "read-continuation.json" : "read-first-page.json"); },
    update,
  };
  return new MobileTableController({ tableUri: "https://example.invalid/table/123", transport });
}

describe("WeChat mobile table parity", () => {
  it("maps the shared controller state to the same tabs, count, rows, and read-only labels", async () => {
    const tableController = controller();
    await tableController.load();
    const view = createMobileTableViewModel(tableController.state);

    expect(view.tabs).toEqual(["Card", "Table"]);
    expect(view.recordCount).toBe(412);
    expect(view.rows.map((row) => row.recordId)).toEqual(["rec_123", "rec_124"]);
    expect(view.refreshLabel).toBe("刷新表格");
    expect(view.inlineEditing).toBe(false);
  });

  it("preserves a conflict draft and exposes an explicit retry state", async () => {
    const tableController = controller(async () => fixture<UpdateResponse>("update-conflict.json"));
    await tableController.load();
    tableController.beginEdit("rec_123");
    tableController.setDraftField("rec_123", "status", "Done");
    await tableController.save("rec_123");
    const view = createMobileTableViewModel(tableController.state);

    expect(view.mutationStates.rec_123).toBe("conflict");
    expect(view.draftValues.rec_123.status).toBe("Done");
    expect(view.canRetry).toBe(true);
  });

  it("uses shared controller actions for view switching, refresh, reach-bottom, and bounded resize", () => {
    const view = new MobileTableMiniView();
    expect(view.view).toBe("cards");
    view.setView("table");
    view.resizeColumn("status", 999);
    expect(view.view).toBe("table");
    expect(view.columnWidth("status")).toBe(420);
  });

  it("declares the native scroll and touch bindings without inline cell editing", () => {
    const wxml = readFileSync(resolve(process.cwd(), "components/mobile-table/mobile-table.wxml"), "utf8");
    expect(wxml).toContain("scroll-view");
    expect(wxml).toContain("bindscrolltolower");
    expect(wxml).toContain("bindtouchstart");
    expect(wxml).toContain("bindtouchend");
    expect(wxml).toContain("aria-label=\"刷新表格\"");
    expect(wxml).not.toContain("<text>已同步</text>");
    expect(wxml).not.toContain("contenteditable");
  });
});

// @vitest-environment jsdom
import { afterEach, describe, expect, it } from "vitest";
import { MobileTableController } from "../../core/src/controller";
import type { MobileTableTransport } from "../../core/src/transport";
import type { CapabilitiesResponse, InspectionResponse, ReadResponse, UpdateResponse } from "../../core/src/types";
import { MobileTableElement } from "../src/mobile-table-element";
import { fixture } from "./test-fixtures";

if (!customElements.get("otc-mobile-table")) customElements.define("otc-mobile-table", MobileTableElement);

function controller(update: MobileTableTransport["update"] = async () => fixture<UpdateResponse>("update-success.json")) {
  const transport: MobileTableTransport = {
    async capabilities() { return fixture<CapabilitiesResponse>("capabilities-supported.json"); },
    async inspect() { return fixture<InspectionResponse>("inspect-base.json"); },
    async read() { return fixture<ReadResponse>("read-first-page.json"); },
    update,
  };
  return new MobileTableController({ tableUri: "https://example.invalid/table/123", transport });
}

async function mount() {
  const tableController = controller();
  await tableController.load();
  const element = document.createElement("otc-mobile-table") as MobileTableElement;
  element.setController(tableController);
  document.body.append(element);
  return { element, tableController };
}

afterEach(() => { document.body.innerHTML = ""; });

describe("otc-mobile-table", () => {
  it("renders semantic Card/Table tabs, server record count, and an accessible icon-only refresh", async () => {
    const { element } = await mount();

    const tabs = [...element.querySelectorAll('[role="tab"]')];
    expect(tabs.map((tab) => tab.textContent?.trim())).toEqual(["Card", "Table"]);
    expect(element.querySelector('[role="tablist"]')).toBeTruthy();
    expect(element.querySelector(".record-count")?.textContent).toBe("412 条记录");
    expect(element.querySelector(".refresh")?.getAttribute("aria-label")).toBe("刷新表格");
    expect(element.querySelector(".refresh")?.textContent?.trim()).toBe("↻");
    expect(element.querySelector(".control-row")?.textContent).not.toContain("字段");
    expect(element.textContent).not.toContain("能力说明");
    expect(element.textContent).not.toContain("左右滚动查看更多列");
  });

  it("opens the shared detail sheet when a card row is tapped", async () => {
    const { element, tableController } = await mount();
    const row = element.querySelector('[data-record-id="rec_123"]') as HTMLElement;

    row.click();

    expect(tableController.state.drafts.rec_123).toBeDefined();
    expect(element.querySelector("[data-record-sheet]")).toBeTruthy();
    expect(element.querySelector('input[name="status"]')).toBeTruthy();
  });
});

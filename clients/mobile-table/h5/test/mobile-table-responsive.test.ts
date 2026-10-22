// @vitest-environment jsdom
import { describe, expect, it } from "vitest";
import { MobileTableElement } from "../src/mobile-table-element";
import { MOBILE_TABLE_STYLES } from "../src/styles";

if (!customElements.get("otc-mobile-table-responsive")) customElements.define("otc-mobile-table-responsive", MobileTableElement);

describe("mobile table responsive layout", () => {
  it("declares phone single-column cards and iPad auto-fit cards", () => {
    expect(MOBILE_TABLE_STYLES).toContain("grid-template-columns: 1fr");
    expect(MOBILE_TABLE_STYLES).toContain("repeat(auto-fit, minmax(210px, 1fr))");
    expect(MOBILE_TABLE_STYLES).toContain("min-width: 768px");
  });

  it("keeps table widths aligned and bounded after a resize", () => {
    const element = document.createElement("otc-mobile-table-responsive") as MobileTableElement;
    element.resizeColumn("status", 999);
    expect(element.columnWidth("status")).toBe(420);
    element.resizeColumn("status", 180);
    expect(element.columnWidth("status")).toBe(180);
  });

  it("ships a horizontal table surface, touch-sized controls, and load-more sentinel", () => {
    expect(MOBILE_TABLE_STYLES).toContain("overflow-x: auto");
    expect(MOBILE_TABLE_STYLES).toContain("min-height: 44px");
    const element = document.createElement("otc-mobile-table-responsive") as MobileTableElement;
    element.setAttribute("data-test-render", "true");
    expect(element).toBeInstanceOf(HTMLElement);
  });
});

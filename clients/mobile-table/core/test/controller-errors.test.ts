import { describe, expect, it } from "vitest";
import { MobileTableController } from "../src/controller";
import type { MobileTableTransport } from "../src/transport";
import type { CapabilitiesResponse, InspectionResponse, ReadResponse, UpdateResponse } from "../src/types";
import { fixture } from "./test-fixtures";

describe("MobileTableController failure state", () => {
  it("keeps unresolved state for an unknown mutation outcome without automatic retry", async () => {
    let updateCalls = 0;
    const transport: MobileTableTransport = {
      async capabilities() { return fixture<CapabilitiesResponse>("capabilities-supported.json"); },
      async inspect() { return fixture<InspectionResponse>("inspect-base.json"); },
      async read() { return fixture<ReadResponse>("read-first-page.json"); },
      async update() { updateCalls += 1; return fixture<UpdateResponse>("update-unknown.json"); },
    };
    const controller = new MobileTableController({ tableUri: "https://example.invalid/table/123", transport });
    await controller.load();
    controller.beginEdit("rec_123");
    controller.setDraftField("rec_123", "status", "Done");
    await controller.save("rec_123");

    expect(updateCalls).toBe(1);
    expect(controller.state.mutationStates["rec_123"]).toBe("unknown");
    expect(controller.state.drafts["rec_123"]).toBeDefined();
  });
});

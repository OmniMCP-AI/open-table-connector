import { describe, expect, it } from "vitest";
import { MobileTableController } from "../src/controller";
import type { MobileTableTransport } from "../src/transport";
import type { CapabilitiesResponse, InspectionResponse, ReadResponse, UpdateResponse } from "../src/types";
import { fixture } from "./test-fixtures";

function loadedTransport(update: (request: Parameters<MobileTableTransport["update"]>[0]) => Promise<UpdateResponse>) {
  const requests: Parameters<MobileTableTransport["update"]>[0][] = [];
  const transport: MobileTableTransport = {
    async capabilities() { return fixture<CapabilitiesResponse>("capabilities-supported.json"); },
    async inspect() { return fixture<InspectionResponse>("inspect-base.json"); },
    async read() { return fixture<ReadResponse>("read-first-page.json"); },
    async update(request) { requests.push(request); return update(request); },
  };
  return { transport, requests };
}

describe("MobileTableController editing", () => {
  it("sends changed editable fields and replaces the row with canonical readback", async () => {
    const { transport, requests } = loadedTransport(async () => fixture<UpdateResponse>("update-success.json"));
    const controller = new MobileTableController({ tableUri: "https://example.invalid/table/123", transport, requestId: () => "req_edit" });
    await controller.load();

    controller.beginEdit("rec_123");
    controller.setDraftField("rec_123", "status", "Done");
    await controller.save("rec_123");

    expect(requests).toHaveLength(1);
    expect(requests[0].patch).toEqual({ status: "Done" });
    expect(requests[0].expectedTableRevision).toBe("sha256:source-base");
    expect(requests[0].expectedRecordRevision).toBe("sha256:record-123");
    expect(controller.state.rows.find((row) => row.recordId === "rec_123")?.values).toEqual({ status: "Done", owner: null });
    expect(controller.state.drafts["rec_123"]).toBeUndefined();
  });

  it("preserves a draft on conflict and reuses the idempotency key only on explicit retry", async () => {
    let attempt = 0;
    const { transport, requests } = loadedTransport(async () => {
      attempt += 1;
      return attempt === 1 ? fixture<UpdateResponse>("update-conflict.json") : fixture<UpdateResponse>("update-success.json");
    });
    const controller = new MobileTableController({ tableUri: "https://example.invalid/table/123", transport, requestId: () => "req_conflict", idempotencyKey: () => "mobile-edit-fixed" });
    await controller.load();
    controller.beginEdit("rec_123");
    controller.setDraftField("rec_123", "status", "Done");
    await controller.save("rec_123");

    expect(controller.state.mutationStates["rec_123"]).toBe("conflict");
    expect(controller.state.drafts["rec_123"]?.values.status).toBe("Done");
    await controller.retry("rec_123");

    expect(requests).toHaveLength(2);
    expect(requests[0].idempotencyKey).toBe("mobile-edit-fixed");
    expect(requests[1].idempotencyKey).toBe(requests[0].idempotencyKey);
  });

  it("rejects invalid field values before dispatch and allows only one mutation in flight", async () => {
    let release!: () => void;
    const { transport, requests } = loadedTransport(() => new Promise((resolve) => { release = () => resolve(fixture<UpdateResponse>("update-success.json")); }));
    const controller = new MobileTableController({ tableUri: "https://example.invalid/table/123", transport });
    await controller.load();
    controller.beginEdit("rec_123");
    controller.setDraftField("rec_123", "count", "not-an-integer");
    await expect(controller.save("rec_123")).rejects.toThrow(/integer/);
    expect(requests).toHaveLength(0);
    controller.setDraftField("rec_123", "count", 0);
    controller.setDraftField("rec_123", "status", "Done");
    const save = controller.save("rec_123");
    await expect(controller.save("rec_123")).rejects.toThrow(/mutation already in flight/);
    release();
    await save;
  });
});

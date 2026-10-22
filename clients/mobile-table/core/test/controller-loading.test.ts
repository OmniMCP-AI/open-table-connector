import { describe, expect, it } from "vitest";
import { MobileTableController } from "../src/controller";
import type { MobileTableTransport } from "../src/transport";
import type { CapabilitiesResponse, InspectionResponse, ReadResponse } from "../src/types";
import { fixture } from "./test-fixtures";

function transport(): MobileTableTransport & { calls: string[] } {
  const calls: string[] = [];
  return {
    calls,
    async capabilities(request) {
      calls.push(`capabilities:${request.requestId}`);
      return fixture<CapabilitiesResponse>("capabilities-supported.json");
    },
    async inspect(request) {
      calls.push(`inspect:${request.fields?.join(",") ?? "all"}`);
      return fixture<InspectionResponse>("inspect-base.json");
    },
    async read(request) {
      calls.push(`read:${request.pageSize}:${request.pageToken ?? "null"}`);
      return fixture<ReadResponse>("read-first-page.json");
    },
    async update() {
      throw new Error("unexpected update");
    },
  };
}

describe("MobileTableController loading", () => {
  it("loads capabilities and inspection before the first read with page size 25", async () => {
    const host = transport();
    const controller = new MobileTableController({
      tableUri: "https://example.invalid/table/123",
      transport: host,
      requestId: () => "req_load",
    });

    await controller.load();

    expect(host.calls).toEqual(["capabilities:req_load", "inspect:all", "read:25:null"]);
    expect(controller.state.phase).toBe("ready");
    expect(controller.state.rows).toHaveLength(2);
    expect(controller.state.sourceRevision).toBe("sha256:source-base");
    expect(controller.state.nextPageToken).toBe("opaque.cursor/2");
  });

  it("retries a failed safe read once and keeps the successful page", async () => {
    let attempts = 0;
    const host = transport();
    host.read = async () => {
      attempts += 1;
      if (attempts === 1) throw new Error("temporary transport failure");
      return fixture<ReadResponse>("read-empty.json");
    };
    const controller = new MobileTableController({
      tableUri: "https://example.invalid/table/123",
      transport: host,
      requestId: () => "req_retry",
    });

    await controller.load();

    expect(attempts).toBe(2);
    expect(controller.state.phase).toBe("ready");
    expect(controller.state.rows).toEqual([]);
  });
});

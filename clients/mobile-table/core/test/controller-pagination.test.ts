import { describe, expect, it } from "vitest";
import { MobileTableController } from "../src/controller";
import type { MobileTableTransport } from "../src/transport";
import type { CapabilitiesResponse, InspectionResponse, ReadResponse } from "../src/types";
import { fixture } from "./test-fixtures";

function pagedTransport() {
  const requests: string[] = [];
  const transport: MobileTableTransport = {
    async capabilities() { return fixture<CapabilitiesResponse>("capabilities-supported.json"); },
    async inspect() { return fixture<InspectionResponse>("inspect-base.json"); },
    async read(request) {
      requests.push(request.pageToken ?? "first");
      return fixture<ReadResponse>(request.pageToken ? "read-continuation.json" : "read-first-page.json");
    },
    async update() { throw new Error("unexpected update"); },
  };
  return { transport, requests };
}

describe("MobileTableController pagination", () => {
  it("forwards opaque continuation tokens and appends rows", async () => {
    const { transport, requests } = pagedTransport();
    const controller = new MobileTableController({ tableUri: "https://example.invalid/table/123", transport });

    await controller.load();
    await controller.loadMore();

    expect(requests).toEqual(["first", "opaque.cursor/2"]);
    expect(controller.state.rows.map((row) => row.recordId)).toEqual(["rec_123", "rec_124", "rec_125"]);
    expect(controller.state.nextPageToken).toBeNull();
  });

  it("ignores the stale response from an older generation during refresh", async () => {
    const deferred: Array<(response: ReadResponse) => void> = [];
    let readCount = 0;
    const transport: MobileTableTransport = {
      async capabilities() { return fixture<CapabilitiesResponse>("capabilities-supported.json"); },
      async inspect() { return fixture<InspectionResponse>("inspect-base.json"); },
      read: (request) => new Promise((resolve) => {
        readCount += 1;
        deferred.push(resolve);
        if (readCount === 1) expect(request.pageToken).toBeNull();
      }),
      async update() { throw new Error("unexpected update"); },
    };
    const controller = new MobileTableController({ tableUri: "https://example.invalid/table/123", transport });
    const firstLoad = controller.load();
    await new Promise((resolve) => setTimeout(resolve, 0));
    const refresh = controller.refresh();
    deferred[0](fixture<ReadResponse>("read-first-page.json"));
    await new Promise((resolve) => setTimeout(resolve, 0));
    deferred[1](fixture<ReadResponse>("read-empty.json"));
    await Promise.all([firstLoad, refresh]);

    expect(readCount).toBe(2);
    expect(controller.state.rows).toEqual([]);
    expect(controller.state.sourceRevision).toBe("sha256:source-empty");
  });
});

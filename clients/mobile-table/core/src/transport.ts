import type { CapabilitiesResponse, InspectionResponse, ReadResponse, UpdateResponse } from "./types";

export interface CapabilitiesRequest {
  contract: "otc.mobile.table/1.0";
  requestId: string;
  tableUri: string;
}

export interface InspectionRequest extends CapabilitiesRequest {
  fields?: string[];
}

export interface ReadRequest extends CapabilitiesRequest {
  pageSize: number;
  pageToken: string | null;
  fields: string[];
}

export interface UpdateRequest extends CapabilitiesRequest {
  recordId: string;
  patch: Record<string, unknown>;
  expectedTableRevision: string;
  expectedRecordRevision: string;
  idempotencyKey: string;
}

export interface MobileTableTransport {
  capabilities(request: CapabilitiesRequest): Promise<CapabilitiesResponse>;
  inspect(request: InspectionRequest): Promise<InspectionResponse>;
  read(request: ReadRequest): Promise<ReadResponse>;
  update(request: UpdateRequest): Promise<UpdateResponse>;
}

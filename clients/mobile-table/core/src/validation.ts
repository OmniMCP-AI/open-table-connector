import type { MobileField } from "./types";

export function validateFieldValue(field: MobileField, value: unknown): string | null {
  if (value === null) return field.nullable ? null : `${field.label} cannot be null`;
  if (!field.editable) return field.read_only_reason ?? `${field.label} is read-only`;
  switch (field.type) {
    case "string": return typeof value === "string" ? null : `${field.label} must be text`;
    case "integer": return typeof value === "number" && Number.isInteger(value) ? null : `${field.label} must be an integer`;
    case "number": return typeof value === "number" && Number.isFinite(value) ? null : `${field.label} must be a finite number`;
    case "boolean": return typeof value === "boolean" ? null : `${field.label} must be boolean`;
    case "date":
    case "datetime": return typeof value === "string" && value.length > 0 ? null : `${field.label} must be a date string`;
    case "unknown": return `${field.label} has no safe editor`;
  }
}

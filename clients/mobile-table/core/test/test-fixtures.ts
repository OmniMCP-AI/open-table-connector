import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { fileURLToPath } from "node:url";

export function fixture<T>(name: string): T {
  const path = resolve(fileURLToPath(new URL(".", import.meta.url)), "../../../../specification/fixtures/mobile_table", name);
  return JSON.parse(readFileSync(path, "utf8")) as T;
}

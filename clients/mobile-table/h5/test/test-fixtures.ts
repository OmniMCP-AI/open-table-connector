import { readFileSync } from "node:fs";
import { resolve } from "node:path";

export function fixture<T>(name: string): T {
  const path = resolve(process.cwd(), "../../../specification/fixtures/mobile_table", name);
  return JSON.parse(readFileSync(path, "utf8")) as T;
}

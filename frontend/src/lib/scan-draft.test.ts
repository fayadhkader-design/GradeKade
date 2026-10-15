import { afterEach, expect, it, vi } from "vitest";
import { newId, emptyDraft } from "./scan-draft";
afterEach(() => vi.unstubAllGlobals());
it("makes secure UUID retry keys even without randomUUID", () => {
  vi.stubGlobal("crypto", {
    getRandomValues: (bytes: Uint8Array) => {
      bytes.fill(255);
      return bytes;
    },
  });
  expect(newId()).toBe("ffffffff-ffff-4fff-bfff-ffffffffffff");
  expect(emptyDraft().submitted).toBe(false);
});

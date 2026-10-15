import { describe, expect, it } from "vitest";
import { ocrLabel, ocrDescription } from "./ocr";
describe("OCR mode labels", () => {
  it("distinguishes real local OCR from mock and fixtures", () => {
    expect(ocrLabel("paddle")).toBe("REAL OCR · PaddleOCR");
    expect(ocrDescription("paddle")).toContain("locally on CPU");
    expect(ocrLabel("mathpix")).toBe("REAL OCR · Mathpix");
    expect(ocrLabel("mock")).toBe("MOCK OCR");
    expect(ocrLabel("synthetic_fixture")).toContain("simulated");
    expect(ocrLabel()).toBe("Checking OCR provider");
  });
});

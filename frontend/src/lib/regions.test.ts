import { describe, it, expect } from "vitest";
import { pagePoint, rectangle } from "./regions";
describe("normalized answer regions", () => {
  it("uses displayed image dimensions and clamps outside drags", () => {
    expect(
      pagePoint(200, 300, { left: 100, top: 100, width: 400, height: 800 }),
    ).toEqual({ x: 0.25, y: 0.25 });
    expect(
      pagePoint(-20, 1000, { left: 0, top: 0, width: 400, height: 800 }),
    ).toEqual({ x: 0, y: 1 });
  });
  it("supports drawing in either direction without negative dimensions", () => {
    expect(rectangle({ x: 0.8, y: 0.7 }, { x: 0.2, y: 0.1 })).toEqual({
      x: 0.2,
      y: 0.1,
      width: 0.6000000000000001,
      height: 0.6,
    });
  });
});

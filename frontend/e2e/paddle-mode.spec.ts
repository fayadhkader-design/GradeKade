import { test, expect } from "@playwright/test";
test("local Paddle mode and missing-runtime diagnostics are clear on mobile", async ({
  page,
}) => {
  await page.setViewportSize({ width: 390, height: 844 });
  let available = true;
  await page.route("**/api/health", (route) =>
    route.fulfill({
      json: {
        status: available ? "ok" : "degraded",
        ocr_provider: "paddle",
        ocr_fallback: false,
        ocr_available: available,
        ocr_diagnostic: available
          ? null
          : "Install the separate Paddle CPU environment.",
        experimental_auto_grade: false,
      },
    }),
  );
  await page.goto("/scan");
  await expect(page.locator(".ocr-mode-banner")).toContainText(
    "REAL OCR · PaddleOCR",
  );
  await expect(page.locator(".ocr-mode-banner")).toContainText(
    "Automatic grading is off",
  );
  await expect(page.locator(".scan-header .badge")).toHaveText(
    "REAL OCR · PaddleOCR",
  );
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBeTruthy();
  available = false;
  await page.reload();
  await expect(page.locator(".ocr-mode-banner")).toContainText("UNAVAILABLE");
  await expect(page.locator(".ocr-mode-banner")).toContainText(
    "Install the separate Paddle CPU environment.",
  );
});

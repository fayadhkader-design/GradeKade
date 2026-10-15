import { test, expect } from "@playwright/test";

test.use({ viewport: { width: 390, height: 844 } });

test("phone draft survives reload and interrupted upload; ordered booklet review finalizes", async ({
  page,
}) => {
  await page.goto("/scan");
  await page
    .getByRole("button", { name: "Set up sample student & template" })
    .click();
  await expect(page.getByLabel("Scan student")).not.toHaveValue("");
  for (let i = 0; i < 2; i++)
    await page.getByRole("button", { name: "Add original demo page" }).click();
  await expect(
    page
      .getByRole("status", { name: "" })
      .filter({ hasText: "Draft saved on this device" }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Move page earlier" }).click();
  await expect(
    page.getByRole("button", { name: "Preview page 1" }),
  ).toHaveClass(/active/);
  await page.reload();
  await expect(
    page.getByRole("button", { name: "Preview page 2" }),
  ).toBeVisible();
  let uploads = 0;
  await page.route("**/api/booklets/*/pages/*", async (route) => {
    uploads++;
    if (uploads === 2) await route.abort("failed");
    else await route.continue();
  });
  await page
    .getByRole("button", { name: "Submit booklet", exact: true })
    .click();
  await expect(
    page.getByRole("alert").filter({ hasText: "Your pages are kept" }),
  ).toContainText("Your pages are kept on this device");
  await page.unroute("**/api/booklets/*/pages/*");
  await page
    .getByRole("button", { name: "Resume upload & processing" })
    .click();
  await expect(
    page.getByRole("heading", { name: "Booklet processed" }),
  ).toBeVisible();
  await expect(
    page.getByText("30 of 40 answers auto-graded · 10 need review.", {
      exact: true,
    }),
  ).toBeVisible();
  await page.getByRole("link", { name: "Open booklet & review" }).click();
  const sampleIds = await (await page.request.post("/api/demo/setup")).json();
  const unrelated = await (
    await page.request.post("/api/submissions", {
      multipart: {
        student_id: sampleIds.student_id,
        worksheet_template_id: sampleIds.template_id,
        synthetic_demo: "true",
        file: {
          name: "completed.png",
          mimeType: "image/png",
          buffer: await (
            await page.request.get("/api/samples/completed.png")
          ).body(),
        },
      },
    })
  ).json();
  await page.request.post(`/api/submissions/${unrelated.id}/process`);
  const bookletId = page.url().split("/").pop();
  const scoped = await (
    await page.request.get(`/api/review-queue?booklet_id=${bookletId}`)
  ).json();
  expect(scoped).toHaveLength(10); // unrelated worksheet has five more exceptions
  // Force a small review slice so advancing must refetch additional exceptions.
  await page.route("**/api/review-queue?booklet_id=*", async (route) => {
    const response = await route.fetch();
    const items = await response.json();
    await route.fulfill({ response, json: items.slice(0, 1) });
  });
  await page.getByRole("button", { name: "Review 10 answers" }).click();
  for (const pageNumber of [1, 2]) {
    for (const q of [2, 7, 12, 15, 20]) {
      await expect(
        page.getByRole("heading", {
          name: `Page ${pageNumber} · Question ${q}`,
          exact: true,
        }),
      ).toBeVisible();
      const button = page.getByRole("button", {
        name: [12, 20].includes(q) ? /^Incorrect(?: I)?$/ : /^Correct(?: C)?$/,
      });
      await expect(button).toBeEnabled();
      await button.click();
    }
  }
  await expect(
    page.getByRole("heading", { name: "Review complete" }),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "Back to booklet summary", exact: true })
    .click();
  await expect(
    page.getByText("Current score: 34 / 40 (85%) · Corrections required", {
      exact: true,
    }),
  ).toBeVisible();
  await page.getByLabel("Manual grading baseline", { exact: true }).fill("120");
  await page.getByRole("button", { name: "Save comparison" }).click();
  await expect(page.getByText(/Observed capture \+ review was/)).toBeVisible();
  const leftovers = await (await page.request.get("/api/review-queue")).json();
  expect(leftovers).toHaveLength(5);
  for (const answer of leftovers)
    await page.request.post(`/api/question-submissions/${answer.id}/review`, {
      data: { grade: "incorrect", review_seconds: 1 },
    });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBeTruthy();
});

test("guided camera uses a fixture stream, saves capture and stops camera on exit", async ({
  page,
}) => {
  await page.addInitScript(() => {
    Object.defineProperty(navigator.mediaDevices, "getUserMedia", {
      configurable: true,
      value: async () => {
        const canvas = document.createElement("canvas");
        canvas.width = 900;
        canvas.height = 1200;
        const context = canvas.getContext("2d")!;
        context.fillStyle = "white";
        context.fillRect(0, 0, 900, 1200);
        context.fillStyle = "black";
        context.font = "40px sans-serif";
        context.fillText("Original camera test worksheet", 50, 100);
        context.fillText("17 + 25 = 42", 100, 300);
        const stream = canvas.captureStream(5);
        (
          window as unknown as { testCameraTrack: MediaStreamTrack }
        ).testCameraTrack = stream.getTracks()[0];
        return stream;
      },
    });
  });
  await page.goto("/scan");
  await page
    .getByRole("button", { name: "Set up sample student & template" })
    .click();
  await page.getByRole("button", { name: "Open camera", exact: true }).click();
  await expect(page.locator("video")).toBeVisible();
  await expect
    .poll(() =>
      page
        .locator("video")
        .evaluate((video: HTMLVideoElement) => video.videoWidth),
    )
    .toBeGreaterThan(0);
  await page.getByRole("button", { name: "Capture page", exact: true }).click();
  await expect(
    page.getByAltText("Captured page 1", { exact: true }),
  ).toBeVisible();
  await expect(
    page.getByLabel("Synthetic OCR for original sample pages only"),
  ).not.toBeChecked();
  await expect(
    page.getByText("Draft saved on this device", { exact: true }),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "Capture next page", exact: true })
    .click();
  await page.getByRole("button", { name: "Close camera", exact: true }).click();
  expect(
    await page.evaluate(
      () =>
        (window as unknown as { testCameraTrack: MediaStreamTrack })
          .testCameraTrack.readyState,
    ),
  ).toBe("ended");
  await page.reload();
  await expect(
    page.getByAltText("Captured page 1", { exact: true }),
  ).toBeVisible();
  // A replacement updates the existing page rather than adding another one.
  await page
    .getByLabel("Replace worksheet photo", { exact: true })
    .setInputFiles({
      name: "retake.png",
      mimeType: "image/png",
      buffer: await (
        await page.request.get("/api/samples/completed.png")
      ).body(),
    });
  await expect(
    page.getByRole("button", { name: "Preview page 1", exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Preview page 2", exact: true }),
  ).toHaveCount(0);
});

test("denied camera has an actionable photo fallback", async ({ page }) => {
  await page.addInitScript(() => {
    Object.defineProperty(navigator.mediaDevices, "getUserMedia", {
      configurable: true,
      value: async () => {
        throw new DOMException("Denied", "NotAllowedError");
      },
    });
  });
  await page.goto("/scan");
  await page
    .getByRole("button", { name: "Set up sample student & template" })
    .click();
  await page.getByRole("button", { name: "Open camera", exact: true }).click();
  await expect(
    page.getByRole("alert").filter({ hasText: "Allow camera access" }),
  ).toContainText("Allow camera access");
  await expect(
    page.getByRole("button", { name: "Choose photos / camera" }),
  ).toBeEnabled();
});

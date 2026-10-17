import { test, expect } from "@playwright/test";

test("reopened correction processing recovers from a temporary refresh failure", async ({
  page,
}) => {
  await page.setViewportSize({ width: 390, height: 844 });
  let reads = 0;
  let finished = false;
  let failNextRefresh = false;
  await page.route("**/api/correction-rounds/recovery-round", async (route) => {
    expect(route.request().method()).toBe("GET");
    reads++;
    if (failNextRefresh) {
      failNextRefresh = false;
      return route.fulfill({
        status: 503,
        json: { detail: "Temporary connection problem" },
      });
    }
    await route.fulfill({
      json: {
        id: "recovery-round",
        booklet_id: "recovery-booklet",
        round_number: 1,
        completed_at: null,
        status: "in_progress",
        unresolved_before: 1,
        corrected: 0,
        waiting: finished ? 1 : 0,
        pages: [
          {
            source_submission_id: "original-page",
            page_number: 1,
            question_numbers: [3],
            submission: {
              id: "corrected-page",
              original_url:
                "data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7",
              status: finished ? "needs_review" : "processing",
              total: finished ? 1 : 0,
              waiting: finished ? 1 : 0,
              processing: null,
              error: null,
            },
          },
        ],
      },
    });
  });
  await page.goto("/corrections/recovery-round");
  await expect(page.getByRole("main").getByRole("status")).toHaveText(
    "Processing corrections…",
  );
  // No local process request exists after navigation or reload.
  await page.reload();
  await expect(page.getByRole("main").getByRole("status")).toHaveText(
    "Processing corrections…",
  );
  failNextRefresh = true;
  await expect(page.getByRole("main").getByRole("alert")).toContainText(
    "Temporary connection problem",
  );
  finished = true;
  await expect(
    page.getByRole("button", { name: "Review 1 corrections" }),
  ).toBeEnabled();
  await expect(page.getByRole("main").getByRole("alert")).toHaveCount(0);
  await expect(page.getByRole("main").getByRole("status")).toHaveCount(0);
  await expect(
    page.getByRole("button", { name: "Process page 1" }),
  ).toHaveCount(0);
  await expect(
    page.getByLabel("Corrected page 1", { exact: true }),
  ).toHaveCount(0);
  const settledReads = reads;
  // Once processing ends, background polling must stop.
  await page.waitForTimeout(3200);
  expect(reads).toBe(settledReads);
});

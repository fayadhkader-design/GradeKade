import { test, expect } from "@playwright/test";
import path from "node:path";
import fs from "node:fs";

test("phone correction rounds go 17/20 to 19/20 to 20/20 with intact history", async ({
  page,
  request,
}) => {
  await page.setViewportSize({ width: 390, height: 844 });
  const ids = await (await request.post("/api/demo/setup")).json();
  const bookletId = crypto.randomUUID();
  expect(
    (
      await request.post("/api/booklets", {
        data: {
          id: bookletId,
          student_id: ids.student_id,
          page_count: 1,
          capture_seconds: 1,
          synthetic_demo: true,
        },
      })
    ).ok(),
  ).toBeTruthy();
  const created = await request.post(
    `/api/booklets/${bookletId}/pages/${crypto.randomUUID()}`,
    {
      multipart: {
        template_id: ids.template_id,
        page_number: "1",
        file: {
          name: "completed.png",
          mimeType: "image/png",
          buffer: fs.readFileSync(
            path.resolve(__dirname, "../../sample_data/completed.png"),
          ),
        },
      },
    },
  );
  const original = await created.json();
  expect(
    (await request.post(`/api/submissions/${original.id}/process`)).ok(),
  ).toBeTruthy();
  const queue = await (
    await request.get(`/api/review-queue?booklet_id=${bookletId}`)
  ).json();
  for (const a of queue)
    await request.post(`/api/question-submissions/${a.id}/review`, {
      data: {
        grade: [12, 20].includes(a.question_number) ? "incorrect" : "correct",
        review_seconds: 1,
      },
    });
  const originalAnswers = (
    await (await request.get(`/api/submissions/${original.id}`)).json()
  ).answers;
  await page.goto(`/booklets/${bookletId}`);
  await expect(
    page.getByText("3 corrections remaining", { exact: true }),
  ).toBeVisible();
  await page.screenshot({
    path: "../outputs/corrections-initial-phone.png",
    fullPage: true,
  });
  for (const round of [1, 2]) {
    await page.getByRole("button", { name: "Start correction round" }).click();
    await expect(
      page.getByRole("heading", {
        name: `Correction round ${round}`,
        exact: true,
      }),
    ).toBeVisible();
    await page
      .getByLabel("Corrected page 1", { exact: true })
      .setInputFiles(
        path.resolve(
          __dirname,
          `../../sample_data/correction-round-${round}.png`,
        ),
      );
    await page
      .getByRole("button", { name: "Process page 1", exact: true })
      .click();
    await expect(
      page.getByRole("button", {
        name: `Review ${round === 1 ? 3 : 1} corrections`,
      }),
    ).toBeVisible();
    await page.getByRole("button", { name: /Review \d+ corrections/ }).click();
    for (const number of round === 1 ? [3, 12, 20] : [20]) {
      await expect(
        page.getByRole("heading", {
          name: `Page 1 · Question ${number}`,
          exact: true,
        }),
      ).toBeVisible();
      const button = page.getByRole("button", {
        name:
          round === 1 && number === 20
            ? /^Incorrect(?: I)?$/
            : /^Correct(?: C)?$/,
      });
      await expect(button).toBeEnabled();
      await button.click();
    }
    await page
      .getByRole("button", { name: "Back to correction round", exact: true })
      .click();
    await page
      .getByRole("button", { name: "Finalize correction round", exact: true })
      .click();
    await expect(
      page.getByText(
        `Round finalized: ${round === 1 ? 2 : 1} of ${round === 1 ? 3 : 1} corrected · ${round === 1 ? 1 : 0} remaining.`,
      ),
    ).toBeVisible();
    await page.getByRole("link", { name: "Back to booklet summary" }).click();
    await expect(
      page.getByText(`${round === 1 ? 1 : 0} corrections remaining`, {
        exact: true,
      }),
    ).toBeVisible();
  }
  await expect(
    page.getByRole("heading", { name: "Booklet complete", exact: true }),
  ).toBeVisible();
  await expect(
    page.getByText("Final score: 20 / 20 (100%)", { exact: true }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Show question history" }).click();
  const q20 = page.locator("details").filter({
    has: page.locator("summary", {
      hasText: "Page 1 · Question 20 · Resolved · 3 attempts",
    }),
  });
  await q20.locator("summary").click();
  await expect(
    q20.getByRole("heading", { name: "Attempt 1 · Initial" }),
  ).toBeVisible();
  await expect(
    q20.getByRole("heading", { name: "Attempt 3 · Correction 2" }),
  ).toBeVisible();
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBeTruthy();
  await page.screenshot({
    path: "../outputs/corrections-complete-phone.png",
    fullPage: true,
  });
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.screenshot({
    path: "../outputs/corrections-complete-desktop.png",
    fullPage: true,
  });
  const after = await (
    await request.get(`/api/submissions/${original.id}`)
  ).json();
  expect(after.answers).toEqual(originalAnswers);
});

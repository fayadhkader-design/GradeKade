import { test, expect } from "@playwright/test";
import path from "node:path";
import fs from "node:fs";
test("evaluation saves independent truth and inspects evidence on desktop and phone", async ({
  page,
  request,
}) => {
  const setup = await request.post("/api/demo/setup");
  const ids = await setup.json();
  const created = await request.post("/api/submissions", {
    multipart: {
      student_id: ids.student_id,
      worksheet_template_id: ids.template_id,
      synthetic_demo: "true",
      file: {
        name: "completed.png",
        mimeType: "image/png",
        buffer: fs.readFileSync(
          path.resolve(__dirname, "../../sample_data/completed.png"),
        ),
      },
    },
  });
  const submission = await created.json();
  expect(
    (await request.post(`/api/submissions/${submission.id}/process`)).ok(),
  ).toBeTruthy();
  // Other workflow tests create historical answers on this shared server.
  // Keep this annotation UI exercise scoped to the submission it owns.
  await page.route("**/api/evaluation?*", async (route) => {
    const response = await route.fetch();
    const data = await response.json();
    data.items = data.items.filter(
      (item: { submission_id: string }) => item.submission_id === submission.id,
    );
    data.total = data.items.length;
    await route.fulfill({ response, json: data });
  });
  await page.goto("/evaluation");
  await expect(
    page.getByText(/MOCK OCR · No handwriting recognition/),
  ).toBeVisible();
  await page.getByLabel("Dataset source").selectOption("synthetic");
  await expect(
    page.getByRole("heading", { name: "Question 1", exact: true }),
  ).toBeVisible();
  await page.getByLabel("What was actually written").fill("42");
  await page.getByLabel("Human-verified grade").selectOption("correct");
  await expect(page.getByAltText("Answer crop for question 1")).toBeVisible();
  await page.getByRole("button", { name: "Save human truth" }).click();
  await expect(
    page.getByRole("status").filter({ hasText: "Ground truth saved" }),
  ).toBeVisible();
  await page
    .getByText("Inspect OCR and grading evidence", { exact: true })
    .click();
  await expect(
    page.getByText("Original system decision", { exact: true }),
  ).toBeVisible();
  await page.screenshot({
    path: "../.impeccable/review/evaluation-desktop.png",
    fullPage: true,
  });
  await page.setViewportSize({ width: 390, height: 844 });
  await expect(
    page.getByRole("button", { name: "Save human truth" }),
  ).toBeVisible();
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBeTruthy();
  await page.screenshot({
    path: "../.impeccable/review/evaluation-mobile.png",
    fullPage: true,
  });
  await page.getByLabel("Answers on this page").selectOption("unverified");
  for (let i = 0; i < 18; i++)
    await page.getByRole("button", { name: "Next answer" }).click();
  await expect(
    page.getByRole("heading", { name: "Question 20", exact: true }),
  ).toBeVisible();
  await page.getByLabel("Transcription status").selectOption("blank");
  await page.getByLabel("Human-verified grade").selectOption("incorrect");
  await page.getByRole("button", { name: "Save human truth" }).click();
  await expect(
    page.getByRole("heading", { name: "Question 19", exact: true }),
  ).toBeVisible();
  const exported = await request.get("/api/evaluation/export?source=synthetic");
  expect(exported.headers()["content-type"]).toContain("application/zip");
  const after = await request.get(`/api/submissions/${submission.id}`);
  const final = await after.json();
  expect(final.answers[0].raw_ocr_text).toBe("42");
  // This test owns its submission; leave other tests' global review queue unchanged.
  for (const answer of final.answers.filter(
    (a: { review_status: string }) => a.review_status === "needs_review",
  )) {
    expect(
      (
        await request.post(`/api/question-submissions/${answer.id}/review`, {
          data: {
            grade: [12, 20].includes(answer.question_number)
              ? "incorrect"
              : "correct",
            review_seconds: 1,
          },
        })
      ).ok(),
    ).toBeTruthy();
  }
});

import { test, expect } from "@playwright/test";
import path from "node:path";
const samples = path.resolve(__dirname, "../../sample_data");

test("manual template annotation, upload, review, and final score", async ({
  page,
}) => {
  await page.goto("/");
  await page.getByRole("button", { name: "Templates", exact: true }).click();
  await page.getByLabel("Template name").fill("Browser arithmetic template");
  await page
    .getByLabel("Blank worksheet", { exact: true })
    .setInputFiles(path.join(samples, "blank.png"));
  await page
    .getByRole("button", { name: "Create template", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: "Browser arithmetic template" }),
  ).toBeVisible();
  const image = page.getByAltText(
    "Blank worksheet: Browser arithmetic template",
  );
  await expect(image).toBeVisible();
  // Draw ten rectangles against displayed image coordinates. No API shortcut for annotation.
  const box = await image.boundingBox();
  if (!box) throw new Error("Worksheet image did not render");
  const expected = [
    "42",
    "35",
    "42",
    "8",
    "1.5",
    "2.25",
    "1/2",
    "1/2",
    "72",
    "36",
  ];
  const types = [
    "integer",
    "integer",
    "integer",
    "integer",
    "decimal",
    "decimal",
    "fraction",
    "fraction",
    "integer",
    "integer",
  ];
  for (let index = 0; index < 10; index++) {
    const x = box.x + (375 / 1200) * box.width;
    const y = box.y + ((270 + index * 120) / 1600) * box.height;
    await page.mouse.move(x, y);
    await page.mouse.down();
    await page.mouse.move(
      x + (170 / 1200) * box.width,
      y + (75 / 1600) * box.height,
      { steps: 4 },
    );
    await page.mouse.up();
    await page
      .getByLabel("Correct answer", { exact: true })
      .fill(expected[index]);
    await page
      .getByLabel("Answer type", { exact: true })
      .selectOption(types[index]);
  }
  await page
    .getByRole("button", { name: "Save answer key", exact: true })
    .click();
  await expect(
    page.getByRole("status").filter({ hasText: "10 answer boxes saved" }),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "Upload worksheet", exact: true })
    .click();
  await page.getByRole("button", { name: "Add a demo student" }).click();
  await page
    .getByLabel("First name or display identifier")
    .fill("Browser learner");
  await page.getByRole("button", { name: "Save student", exact: true }).click();
  await expect(page.getByLabel("Student", { exact: true })).not.toHaveValue("");
  await page
    .getByLabel("Worksheet template", { exact: true })
    .selectOption({ label: "Browser arithmetic template · 10 questions" });
  await page
    .getByLabel("Completed worksheet file")
    .setInputFiles(path.join(samples, "completed.png"));
  await page
    .getByRole("button", { name: "Upload & process worksheet" })
    .click();
  await expect(
    page.getByRole("heading", { name: "Worksheet results", exact: true }),
  ).toBeVisible();
  await expect(
    page.getByText("10 answers need review", { exact: true }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Review 10 answers" }).click();
  await expect(
    page.getByRole("heading", { name: "Question 1", exact: true }),
  ).toBeVisible();
  for (let q = 1; q <= 10; q++) {
    await expect(
      page.getByRole("heading", { name: `Question ${q}`, exact: true }),
    ).toBeVisible();
    await expect(
      page.getByRole("button", { name: "Correct C", exact: true }),
    ).toBeEnabled();
    await page.keyboard.press(q === 3 ? "i" : "c");
  }
  await expect(
    page.getByRole("heading", { name: "Review complete", exact: true }),
  ).toBeVisible();
  await page.getByRole("button", { name: "View worksheet result" }).click();
  await expect(page.getByText("9 / 10", { exact: true })).toBeVisible();
  await expect(
    page.getByText("90% · final score", { exact: true }),
  ).toBeVisible();
});

test("synthetic demo auto-grades and protects edit shortcuts", async ({
  page,
}) => {
  await page.goto("/");
  await page.getByRole("button", { name: "Prepare demo", exact: true }).click();
  await page
    .getByLabel("Completed worksheet file")
    .setInputFiles(path.join(samples, "completed.png"));
  await page
    .getByRole("button", { name: "Upload & process worksheet" })
    .click();
  await expect(
    page.getByText("5 answers need review", { exact: true }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Review 5 answers" }).click();
  await expect(
    page.getByRole("heading", { name: "Question 2", exact: true }),
  ).toBeVisible();
  await page.keyboard.press("e");
  await expect(
    page.getByLabel("Recognized answer", { exact: true }),
  ).toBeFocused();
  await page.getByLabel("Recognized answer", { exact: true }).fill("c");
  await expect(
    page.getByRole("heading", { name: "Question 2", exact: true }),
  ).toBeVisible();
  await page.getByLabel("Recognized answer", { exact: true }).fill("35");
  await page.getByRole("button", { name: /^Correct C$/ }).click();
  for (const q of [7, 12, 15, 20]) {
    await expect(
      page.getByRole("heading", { name: `Question ${q}`, exact: true }),
    ).toBeVisible();
    await expect(
      page.getByRole("button", { name: "Correct C", exact: true }),
    ).toBeEnabled();
    await page.keyboard.press([12, 20].includes(q) ? "i" : "c");
  }
  await expect(
    page.getByRole("heading", { name: "Review complete", exact: true }),
  ).toBeVisible();
  await page.getByRole("button", { name: "View worksheet result" }).click();
  await expect(page.getByText("17 / 20", { exact: true })).toBeVisible();
});

test("dashboard remains usable on a narrow viewport", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/");
  await expect(
    page.getByRole("heading", { name: "A clearer grading day." }),
  ).toBeVisible();
  await page.getByRole("button", { name: /^Review queue/ }).click();
  await expect(
    page.getByRole("heading", { name: "Your judgment, where it matters." }),
  ).toBeVisible();
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBeTruthy();
});

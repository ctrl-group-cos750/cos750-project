import { demoAccounts } from "./content";
import { segmentRegion, walkModule } from "./drive";
import { DEMO_PASSWORD } from "./env";
import { expect, test, type Page } from "./fixtures";
import { logIn } from "./helpers";

// NFR-U1: every module except 2, 4 and 5 (the code modules, which need a wide screen) works on a
// phone 360 px wide: each segment fits without scrolling sideways (WCAG 1.4.10), and every
// activity is answered there with real clicks and taps, so a control that something covers fails.
// So do the pages around the modules.
test.use({ viewport: { width: 360, height: 740 } });

async function fits(page: Page, label: string) {
  const { scrollWidth, innerWidth } = await page.evaluate(() => ({
    scrollWidth: document.documentElement.scrollWidth,
    innerWidth: window.innerWidth,
  }));
  // Soft: one test lists every segment that doesn't fit, not just the first.
  expect
    .soft(
      scrollWidth,
      `${label} is ${scrollWidth}px wide in a ${innerWidth}px window`,
    )
    .toBeLessThanOrEqual(innerWidth);
}

for (const number of [0, 1, 3, 6]) {
  test(`module ${number}: every segment at 360 px, every activity answered`, async ({
    page,
    course,
  }) => {
    if (number >= 3) test.slow();
    await course.completeBefore(number);
    const module = await course.module(number);
    await course.roomFor(module.segments.length + module.retrieval.length);
    await walkModule(page, module, { onSegment: (label) => fits(page, label) });
  });
}

test("the sign-in pages fit 360 px", async ({ page }) => {
  for (const path of ["/login", "/register"]) {
    await page.goto(path);
    await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
    await fits(page, path);
  }
});

test("the map, report, badges and profile fit 360 px", async ({
  page,
  course,
}) => {
  await course.completeBefore(1);
  for (const path of ["/", "/report", "/badges", "/profile"]) {
    await page.goto(path);
    await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
    await fits(page, path);
  }
});

test("the report and a review path fit 360 px", async ({ page }) => {
  const notYet = demoAccounts.find((d) => (d.expect.not_yet ?? []).length > 0);
  expect(notYet, "a demo account with an objective not yet met").toBeDefined();
  await logIn(page, `${notYet?.key}@demo.example.com`, DEMO_PASSWORD);
  await page.goto("/report");
  await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
  await fits(page, "/report with a review path");
  await page.goto(`/review/${notYet?.expect.not_yet?.[0]}`);
  await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
  await fits(page, "the review path");
});

test.describe("badge notes", () => {
  // Nothing closes the notes here: the test is about where they sit.
  test.use({ dismissOverlays: false });

  // On a phone a new badge's note is a compact banner at the top of the screen, so it never covers
  // the module's Next at the bottom (WCAG 2.2 2.4.11), and its links are 44 px tall (#215 review).
  test("at 360 px a new badge's note doesn't cover the module's Next", async ({
    page,
    course,
  }) => {
    // Module 0 finished earns the First Module badge; its note shows on the next page, module 1
    // (its recall questions answered, so the module itself is on screen, with Next).
    await course.walk(0);
    await course.walk(1, 0);
    const module = await course.module(1);
    await page.goto(`/modules/${module.id}`);
    await expect(segmentRegion(page, module.segments[0].title)).toBeVisible();
    await expect(
      page
        .getByRole("status")
        .getByRole("button", { name: /^Dismiss/ })
        .first(),
    ).toBeVisible();
    const next = page
      .getByRole("navigation", { name: "Segment navigation" })
      .getByRole("button", {
        name: /^Next/,
      });
    // What a tap would hit in the middle of Next, scrolled as far into view as it goes.
    const covered = await next.evaluate((el) => {
      el.scrollIntoView({ block: "end" });
      const box = el.getBoundingClientRect();
      const at = document.elementFromPoint(
        box.left + box.width / 2,
        box.top + box.height / 2,
      );
      return at !== null && !el.contains(at);
    });
    expect(covered, "Next is covered by the badge note").toBe(false);
    const note = page.getByRole("status");
    for (const link of await note.getByRole("link").all()) {
      const box = await link.boundingBox();
      expect(
        box?.height ?? 0,
        "a link in the badge note is a 44 px target",
      ).toBeGreaterThanOrEqual(44);
    }
  });
});

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
    // Module 1 finished earns the First Module badge (module 0, the warm-up, asks only diagnostic
    // questions and earns none); its note shows on the next page, module 2 (its recall questions
    // answered, so the module itself is on screen, with Next).
    await course.walk(0);
    await course.walk(1);
    await course.walk(2, 0);
    const module = await course.module(2);
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
      // Rounded to a hundredth: Firefox reports a 44 px box at a fractional offset as 43.999996.
      const height = Math.round((box?.height ?? 0) * 100) / 100;
      expect(
        height,
        "a link in the badge note is a 44 px target",
      ).toBeGreaterThanOrEqual(44);
    }
  });

  // At 320 px the note sits under the header, as at every width: over it, it covered the theme
  // toggle, the account menu and the module's heading (#222 review). And the page moves down to
  // make room, so it doesn't cover the heading under the header either (#222 re-review).
  for (const width of [320, 360]) {
    test(`at ${width} px a new badge's note sits under the header and above the heading`, async ({
      page,
      course,
    }) => {
      await page.setViewportSize({ width, height: 640 });
      await course.walk(0);
      await course.walk(1);
      await course.walk(2, 0);
      const module = await course.module(2);
      await page.goto(`/modules/${module.id}`);
      await expect(segmentRegion(page, module.segments[0].title)).toBeVisible();
      const dismiss = page
        .getByRole("status")
        .getByRole("button", { name: /^Dismiss/ })
        .first();
      await expect(dismiss).toBeVisible();
      const header = await page.locator("header").first().boundingBox();
      // The notes' region: its top is the first note's.
      const note = await page
        .getByRole("status")
        .filter({ has: page.getByRole("button", { name: /^Dismiss/ }) })
        .first()
        .boundingBox();
      expect(header, "the header").not.toBeNull();
      expect(note, "the badge note").not.toBeNull();
      expect(
        note?.y ?? 0,
        "the note starts under the header",
      ).toBeGreaterThanOrEqual((header?.y ?? 0) + (header?.height ?? 0));
      // Nothing in the header is under the note: its buttons can still be pressed.
      const covered = await page
        .locator("header")
        .first()
        .evaluate((el) =>
          [...el.querySelectorAll("button, a")].some((control) => {
            const box = control.getBoundingClientRect();
            if (box.width === 0) return false;
            const at = document.elementFromPoint(
              box.left + box.width / 2,
              box.top + box.height / 2,
            );
            return at !== null && !control.contains(at);
          }),
        );
      expect(covered, "a header control is covered by the badge note").toBe(
        false,
      );
      // Nor is the module's heading: the page moves down while the note shows (#222 re-review, B3).
      const heading = await page
        .getByRole("heading", { level: 1 })
        .boundingBox();
      expect(heading, "the module heading").not.toBeNull();
      expect(
        heading?.y ?? 0,
        "the heading starts under the badge note",
      ).toBeGreaterThanOrEqual((note?.y ?? 0) + (note?.height ?? 0));
    });
  }

  // When the note goes by itself, the room made for it goes too. Scrolled a little into the page,
  // that moved everything up by the note's height, and a focused control could end up under the
  // opaque header (WCAG 2.4.11; #222 re-review). The page is scrolled back by as much instead.
  test("at 360 px a focused control stays in view when the badge note goes", async ({
    page,
    course,
  }) => {
    await page.setViewportSize({ width: 360, height: 740 });
    await course.walk(0);
    await course.walk(1);
    await course.walk(2, 0);
    const module = await course.module(2);
    await page.goto(`/modules/${module.id}`);
    await expect(segmentRegion(page, module.segments[0].title)).toBeVisible();
    const note = page
      .getByRole("status")
      .getByRole("button", { name: /^Dismiss/ });
    await expect(note.first()).toBeVisible();
    await page.mouse.move(1, 700); // nowhere near the note, which stays while the pointer is in it
    // The room made for the note, once it has settled.
    await expect
      .poll(() =>
        page.evaluate(() =>
          document
            .querySelector("main")
            ?.style.getPropertyValue("--note-space"),
        ),
      )
      .toMatch(/px$/);
    await page.evaluate(() => window.scrollTo(0, 150));
    // The first control in the page below the header, focused from code: the keyboard would also
    // scroll it into view, which is not what this test is about.
    const focused = await page.evaluate(() => {
      const header =
        document.querySelector("header")?.getBoundingClientRect().bottom ?? 0;
      const control = [
        ...document.querySelectorAll<HTMLElement>("main a, main button"),
      ].find((el) => {
        const box = el.getBoundingClientRect();
        // Not one in the note itself, which stays while focus is in it.
        if (el.closest('output, [role="status"]')) return false;
        return (
          box.height > 0 &&
          box.top > header + 8 &&
          box.bottom < window.innerHeight
        );
      });
      control?.focus({ preventScroll: true });
      return control?.getBoundingClientRect().top;
    });
    expect(focused, "a control in view to focus").toBeDefined();
    await expect(note).toHaveCount(0, { timeout: 15_000 }); // it goes by itself
    await page.waitForTimeout(300); // the layout effect and any scroll after it
    const { top, header } = await page.evaluate(() => ({
      top: document.activeElement?.getBoundingClientRect().top ?? -1,
      header:
        document.querySelector("header")?.getBoundingClientRect().bottom ?? 0,
    }));
    expect(
      top,
      "the focused control is below the header",
    ).toBeGreaterThanOrEqual(header);
    // Nothing on screen moved: only the space above it went, with the scroll.
    expect(
      Math.abs(top - (focused ?? 0)),
      "the focused control stayed put",
    ).toBeLessThan(2);
  });
});

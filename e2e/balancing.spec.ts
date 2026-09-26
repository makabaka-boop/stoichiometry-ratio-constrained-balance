import { expect, test } from "@playwright/test";

/**
 * Exactly one journey: load a batch, solve it, manually re-check the
 * certified coefficients, prove a wrong entry is rejected, and finally
 * prove that touching the input revokes the old certificate and review.
 */
test.describe("配平工作台单次录入-求解-复核流程", () => {
  test("H2 + O2 -> H2O：获得唯一配方，人工复核可逐项验算，修改输入立即撤销旧证书", async ({
    page,
  }) => {
    await page.goto("/");

    // ---- 唯一一次录入：载入示例批次 ----
    await page.getByTestId("load-sample").click();
    await expect(page.getByTestId("compound-card")).toHaveCount(3);
    await expect(page.getByTestId("matrix-table")).toBeVisible();

    // ---- 求解 ----
    await page.getByTestId("solve-button").click();

    const verdict = page.getByTestId("result-panel");
    await expect(verdict).toBeVisible();
    await expect(verdict).toHaveAttribute("data-status", "BALANCED");
    await expect(verdict).toHaveAttribute("data-stale", "false");
    await expect(page.getByTestId("result-equation")).toHaveText("2 H2 + O2 -> 2 H2O");
    await expect(page.getByTestId("result-status")).toContainText("零空间维数：1");

    // Per-element totals must be verifiable on both sides.
    const hydrogenRow = page.getByTestId("total-row").filter({ hasText: "H" });
    await expect(hydrogenRow).toContainText("4");
    const oxygenRow = page.getByTestId("total-row").filter({ hasText: "O" });
    await expect(oxygenRow).toContainText("2");
    await expect(page.getByTestId("total-row")).toHaveCount(2);

    // Certified coefficients were seeded into the manual review fields.
    const reviewInputs = page.getByTestId("review-coefficient");
    await expect.poll(() => reviewInputs.evaluateAll(
      (nodes) => (nodes as HTMLInputElement[]).map((node) => node.value),
    )).toEqual(["2", "1", "2"]);

    // ---- 复核：先把氧的系数改错，应明确不可认证 ----
    await reviewInputs.nth(1).fill("2");
    await page.getByTestId("review-button").click();

    const reviewVerdict = page.getByTestId("review-verdict");
    await expect(reviewVerdict).toHaveAttribute("data-valid", "false");
    await expect(page.getByTestId("review-summary")).toContainText("复核不通过");
    const oxygenReviewRow = page
      .getByTestId("review-element-row")
      .filter({ hasText: "O" });
    await expect(oxygenReviewRow).toContainText("不守恒");
    await expect(oxygenReviewRow).toContainText("4"); // 2*O2 = 4 left vs 2 right
    const hydrogenReviewRow = page
      .getByTestId("review-element-row")
      .filter({ hasText: "H" });
    await expect(hydrogenReviewRow).toContainText("守恒");

    // ---- 改回正确系数，复核通过且最简 ----
    await reviewInputs.nth(1).fill("1");
    await page.getByTestId("review-button").click();
    await expect(reviewVerdict).toHaveAttribute("data-valid", "true");
    await expect(page.getByTestId("review-summary")).toContainText("复核通过");
    await expect(page.getByTestId("review-element-row")).toHaveCount(2);

    // ---- 任何输入修改立即撤销旧证书与旧复核 ----
    await page.getByTestId("add-reactant").click();
    await expect(verdict).toHaveAttribute("data-stale", "true");
    await expect(page.getByTestId("stale-badge")).toBeVisible();
    await expect(page.getByTestId("review-stale-badge")).toBeVisible();
  });
});

import { expect, test } from "@playwright/test";

/**
 * Two journeys:
 *  1. load a batch, solve it, manually re-check the certified coefficients,
 *     prove a wrong entry is rejected, and prove that touching the input
 *     revokes the old certificate and review;
 *  2. an underdetermined system becomes unique through an approved feed
 *     ratio, the review checks the ratio, invalid ratio input never
 *     overwrites the last valid form, and editing ratios or compounds
 *     revokes the certificate immediately.
 */
test.describe("配平工作台录入-求解-复核流程", () => {
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

  test("多解体系经已批准比例约束变唯一：签发证书、复核检查比例、修改比例或化合物立即撤销证书", async ({
    page,
  }) => {
    // Longer journey (two solves + two reviews + invalid-input checks).
    test.setTimeout(60_000);
    await page.goto("/");

    // ---- 多解体系：不加比例时不可认证 ----
    await page.getByTestId("load-underdetermined-sample").click();
    await expect(page.getByTestId("compound-card")).toHaveCount(4);
    await page.getByTestId("solve-button").click();

    const verdict = page.getByTestId("result-panel");
    await expect(verdict).toHaveAttribute("data-status", "UNDERDETERMINED");
    await expect(page.getByTestId("result-status")).toContainText("零空间维数：2");

    // ---- 填写已批准比例 H2O : H2O2 = 2 : 1，约束后变唯一 ----
    await page.getByTestId("add-ratio").click();
    await page.getByTestId("ratio-a").selectOption({ label: "#3 H2O" });
    await page.getByTestId("ratio-b").selectOption({ label: "#4 H2O2" });
    await page.getByTestId("ratio-a-coefficient").fill("2");
    await page.getByTestId("ratio-b-coefficient").fill("1");

    // 比例约束行进入守恒矩阵预览，与守恒行共同消元。
    const ratioRow = page.getByTestId("matrix-ratio-row");
    await expect(ratioRow).toHaveCount(1);
    await expect(ratioRow).toContainText("-2");

    await page.getByTestId("solve-constrained-button").click();
    await expect(verdict).toHaveAttribute("data-status", "BALANCED");
    await expect(verdict).toHaveAttribute("data-stale", "false");
    await expect(page.getByTestId("result-equation")).toHaveText(
      "3 H2 + 2 O2 -> 2 H2O + H2O2",
    );
    // 页面同时展示比例依据、最终系数与逐元素合计。
    await expect(page.getByTestId("ratio-basis")).toContainText("H2O : H2O2 = 2 : 1");
    await expect(
      page.getByTestId("certificate-coefficient").filter({ hasText: "H2O2" }),
    ).toContainText("1");
    await expect(
      page.getByTestId("certificate-coefficient").filter({ hasText: "H2：" }),
    ).toContainText("3");
    await expect(page.getByTestId("total-row").filter({ hasText: "H" })).toContainText("6");
    await expect(page.getByTestId("total-row").filter({ hasText: "O" })).toContainText("4");

    // ---- 人工复核：签发系数满足比例，复核通过 ----
    const reviewInputs = page.getByTestId("review-coefficient");
    await expect.poll(() => reviewInputs.evaluateAll(
      (nodes) => (nodes as HTMLInputElement[]).map((node) => node.value),
    )).toEqual(["3", "2", "2", "1"]);
    await page.getByTestId("review-button").click();
    await expect(page.getByTestId("review-verdict")).toHaveAttribute("data-valid", "true");
    await expect(page.getByTestId("review-ratio-row")).toHaveAttribute(
      "data-satisfied",
      "true",
    );

    // ---- 守恒但违反比例的配方：复核明确不通过 ----
    await reviewInputs.nth(0).fill("4");
    await reviewInputs.nth(1).fill("3");
    await reviewInputs.nth(2).fill("2");
    await reviewInputs.nth(3).fill("2");
    await page.getByTestId("review-button").click();
    await expect(page.getByTestId("review-verdict")).toHaveAttribute("data-valid", "false");
    await expect(page.getByTestId("review-verdict")).toContainText(
      "系数不满足所填的已批准投料比例",
    );
    await expect(page.getByTestId("review-ratio-row")).toHaveAttribute(
      "data-satisfied",
      "false",
    );
    // 每个元素仍然守恒——不通过完全由比例检查给出。
    await expect(page.getByTestId("review-element-row")).toHaveCount(2);
    await expect(page.getByTestId("review-element-row").filter({ hasText: "不守恒" })).toHaveCount(0);

    // ---- 修改比例立即撤销旧证书；非法输入不覆盖上一次有效表单 ----
    await page.getByTestId("ratio-a-coefficient").fill("0");
    await expect(verdict).toHaveAttribute("data-stale", "true");
    await expect(page.getByTestId("stale-badge")).toBeVisible();

    await page.getByTestId("solve-constrained-button").click();
    await expect(page.getByTestId("ratio-issues")).toBeVisible();
    await expect(page.getByTestId("ratio-issues")).toContainText("正整数");
    // 非法输入未发送请求：旧证书仍在（已标记撤销），表单保持所填内容。
    await expect(verdict).toBeVisible();
    await expect(page.getByTestId("ratio-a-coefficient")).toHaveValue("0");

    // ---- 改回合法比例重新签发，随后修改化合物同样立即撤销 ----
    await page.getByTestId("ratio-a-coefficient").fill("2");
    await page.getByTestId("solve-constrained-button").click();
    await expect(verdict).toHaveAttribute("data-status", "BALANCED");
    await expect(verdict).toHaveAttribute("data-stale", "false");

    await page.getByTestId("add-reactant").click();
    await expect(verdict).toHaveAttribute("data-stale", "true");
    await expect(page.getByTestId("stale-badge")).toBeVisible();
  });
});

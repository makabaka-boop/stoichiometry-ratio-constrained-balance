import { ReviewResult } from "../lib/api";
import { CompoundDraft } from "../lib/api";

interface Props {
  drafts: CompoundDraft[];
  values: Record<string, string>;
  onValueChange: (id: string, value: string) => void;
  onReview: () => void;
  busy: boolean;
  result: ReviewResult | null;
  error: string | null;
  stale: boolean;
}

const REASON_TEXT: Record<string, string> = {
  NOT_CONSERVED: "存在元素两侧总数不相等",
  NOT_PRIMITIVE: "系数非最简（整体最大公约数大于 1）",
  MISSING_COEFFICIENTS: "有化合物缺少系数",
  UNKNOWN_COEFFICIENT_IDS: "出现了未知化合物 ID 的系数",
  NON_POSITIVE_COEFFICIENT: "系数必须为正整数",
};

export function ReviewPanel({
  drafts,
  values,
  onValueChange,
  onReview,
  busy,
  result,
  error,
  stale,
}: Props) {
  return (
    <section className={`panel review${result?.valid ? " tone-ok" : result ? "tone-bad" : ""}`}>
      <h2>人工系数复核区</h2>
      <p className="hint">
        填入你怀疑的整数系数，服务端独立复核：逐元素给出两侧总数，指出不守恒或非最简。
        任何输入修改都会立即撤销旧证书，并把上次复核标记为已过期。
      </p>

      <div className="review-grid" data-testid="review-grid">
        {drafts.map((draft, index) => (
          <label key={draft.key} className="review-field">
            <span>
              #{index + 1} {draft.id.trim() || "（未命名）"}
              <em className="side-tag">{draft.side === "REACTANT" ? "反应物" : "产物"}</em>
            </span>
            <input
              data-testid="review-coefficient"
              data-compound-id={draft.id.trim()}
              inputMode="numeric"
              value={values[draft.key] ?? ""}
              disabled={draft.id.trim() === ""}
              placeholder="整数系数"
              onChange={(event) => onValueChange(draft.key, event.target.value)}
            />
          </label>
        ))}
      </div>

      <button
        type="button"
        className="primary"
        data-testid="review-button"
        onClick={onReview}
        disabled={busy || drafts.length === 0}
      >
        {busy ? "复核中…" : "提交人工复核"}
      </button>

      {error && (
        <div className="error-box" data-testid="review-error">
          {error}
        </div>
      )}

      {result && !error && (
        <div className="review-verdict" data-testid="review-verdict" data-valid={result.valid}>
          {stale && (
            <p className="stale-badge" data-testid="review-stale-badge">
              本次复核基于的输入已被修改，结论已过期。
            </p>
          )}
          <h3 data-testid="review-summary">
            {result.valid
              ? "复核通过：逐元素守恒，且系数为最简整数比。"
              : "复核不通过，该配方不可认证。"}
          </h3>
          {result.reasons.length > 0 && (
            <ul className="reason-list">
              {result.reasons.map((reason) => (
                <li key={reason}>{REASON_TEXT[reason] ?? reason}</li>
              ))}
            </ul>
          )}
          {!result.valid && result.gcd !== null && result.gcd > 1 && (
            <p>整体最大公约数 = {result.gcd}，可整体约去。</p>
          )}
          {result.elements.length > 0 && (
            <table className="totals-table" data-testid="review-table">
              <thead>
                <tr>
                  <th>元素</th>
                  <th>反应物侧</th>
                  <th>产物侧</th>
                  <th>判定</th>
                </tr>
              </thead>
              <tbody>
                {result.elements.map((row) => (
                  <tr
                    key={row.element}
                    data-testid="review-element-row"
                    data-element={row.element}
                    className={row.balanced ? "ok-row" : "bad-row"}
                  >
                    <td>{row.element}</td>
                    <td>{row.reactant}</td>
                    <td>{row.product}</td>
                    <td>{row.balanced ? "守恒" : "不守恒"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}
    </section>
  );
}

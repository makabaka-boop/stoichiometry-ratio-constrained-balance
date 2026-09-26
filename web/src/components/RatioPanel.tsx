import { CompoundDraft, RatioDraft } from "../lib/api";
import { MAX_RATIOS } from "../lib/validation";

interface Props {
  drafts: CompoundDraft[];
  ratios: RatioDraft[];
  onChange: (ratios: RatioDraft[]) => void;
  onSolve: () => void;
  busy: boolean;
  issues: string[];
}

let counter = 0;
function uid(): string {
  counter += 1;
  return `r-${Date.now()}-${counter}`;
}

export function emptyRatio(): RatioDraft {
  return { key: uid(), aKey: "", bKey: "", aCoefficient: "1", bCoefficient: "1" };
}

/**
 * Independent ratio-constrained balancing entry: one or two approved
 * "compound A coefficient : compound B coefficient" positive-integer
 * ratios, eliminated together with the conservation matrix on the server.
 */
export function RatioPanel({ drafts, ratios, onChange, onSolve, busy, issues }: Props) {
  const update = (key: string, patch: Partial<RatioDraft>) => {
    onChange(ratios.map((ratio) => (ratio.key === key ? { ...ratio, ...patch } : ratio)));
  };

  const remove = (key: string) => {
    onChange(ratios.filter((ratio) => ratio.key !== key));
  };

  const add = () => {
    if (ratios.length < MAX_RATIOS) onChange([...ratios, emptyRatio()]);
  };

  const compoundOptions = drafts
    .map((draft, index) => ({ key: draft.key, label: `#${index + 1} ${draft.id.trim()}`, id: draft.id.trim() }))
    .filter((option) => option.id !== "");

  return (
    <section className="panel ratio-panel" data-testid="ratio-panel">
      <h2>比例约束配平（已批准投料比例）</h2>
      <p className="hint">
        守恒成立但配方不唯一时，填写一至两条已批准的「化合物 A 系数 : 化合物 B 系数」正整数比例；
        服务端把每条比例 q·c<sub>A</sub> − p·c<sub>B</sub> = 0 作为精确有理数新约束与守恒矩阵共同消元，
        只有约束后零空间维数为一且可整体化为全正原始整数向量时才签发证书。
      </p>

      <div className="ratio-list">
        {ratios.map((ratio, index) => (
          <div key={ratio.key} className="ratio-row" data-testid="ratio-row">
            <span className="ratio-index">比例 {index + 1}</span>
            <select
              data-testid="ratio-a"
              value={ratio.aKey}
              onChange={(event) => update(ratio.key, { aKey: event.target.value })}
            >
              <option value="">化合物 A…</option>
              {compoundOptions.map((option) => (
                <option key={option.key} value={option.key}>
                  {option.label}
                </option>
              ))}
            </select>
            <input
              className="ratio-coefficient"
              data-testid="ratio-a-coefficient"
              inputMode="numeric"
              value={ratio.aCoefficient}
              placeholder="系数 p"
              onChange={(event) => update(ratio.key, { aCoefficient: event.target.value })}
            />
            <span className="ratio-colon">:</span>
            <select
              data-testid="ratio-b"
              value={ratio.bKey}
              onChange={(event) => update(ratio.key, { bKey: event.target.value })}
            >
              <option value="">化合物 B…</option>
              {compoundOptions.map((option) => (
                <option key={option.key} value={option.key}>
                  {option.label}
                </option>
              ))}
            </select>
            <input
              className="ratio-coefficient"
              data-testid="ratio-b-coefficient"
              inputMode="numeric"
              value={ratio.bCoefficient}
              placeholder="系数 q"
              onChange={(event) => update(ratio.key, { bCoefficient: event.target.value })}
            />
            <button
              type="button"
              className="ghost small"
              data-testid="remove-ratio"
              onClick={() => remove(ratio.key)}
            >
              ×
            </button>
          </div>
        ))}
      </div>

      <div className="ratio-actions">
        <button
          type="button"
          className="secondary"
          data-testid="add-ratio"
          onClick={add}
          disabled={ratios.length >= MAX_RATIOS}
        >
          + 比例约束
        </button>
        <button
          type="button"
          className="primary"
          data-testid="solve-constrained-button"
          onClick={onSolve}
          disabled={busy || drafts.length === 0 || ratios.length === 0}
        >
          {busy ? "精确求解中…" : "按比例约束求解并签发证书"}
        </button>
      </div>

      {issues.length > 0 && (
        <div className="error-box" data-testid="ratio-issues">
          <strong>比例约束未通过本地预检（请求未发送，上次有效表单保持不变）：</strong>
          <ul>
            {issues.map((message) => (
              <li key={message}>{message}</li>
            ))}
          </ul>
        </div>
      )}
    </section>
  );
}

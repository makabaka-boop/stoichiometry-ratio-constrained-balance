import { CompoundDraft, RatioSpec } from "../lib/api";

interface Props {
  drafts: CompoundDraft[];
  /** Validated ratio constraints appended to the elimination matrix. */
  ratios: RatioSpec[];
}

/** Read-only signed conservation matrix: reactants positive, products negative. */
export function MatrixPreview({ drafts, ratios }: Props) {
  const symbols: string[] = [];
  for (const draft of drafts) {
    for (const entry of draft.entries) {
      const symbol = entry.symbol.trim();
      if (symbol !== "" && !symbols.includes(symbol)) symbols.push(symbol);
    }
  }

  const numeric = drafts.map((draft) => {
    const map = new Map<string, number>();
    for (const entry of draft.entries) {
      const count = Number(entry.count);
      if (entry.symbol.trim() !== "" && Number.isInteger(count) && count > 0) {
        map.set(entry.symbol.trim(), count);
      }
    }
    return map;
  });

  if (drafts.length === 0) return null;

  const ids = drafts.map((draft) => draft.id.trim());

  return (
    <section className="panel matrix-preview" data-testid="matrix-preview">
      <h2>守恒矩阵预览</h2>
      <p className="hint">反应物列为正、产物列为负；消元在此矩阵上以有理数精确进行。</p>
      <div className="matrix-scroll">
        <table data-testid="matrix-table">
          <thead>
            <tr>
              <th>元素 \ 化合物</th>
              {drafts.map((draft, index) => (
                <th key={draft.key}>
                  #{index + 1} {draft.id.trim() || "？"}
                  <div className={`mini-side ${draft.side.toLowerCase()}`}>
                    {draft.side === "REACTANT" ? "反应物" : "产物"}
                  </div>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {symbols.map((symbol) => (
              <tr key={symbol}>
                <td>{symbol}</td>
                {numeric.map((map, c) => {
                  const count = map.get(symbol) ?? 0;
                  const signed = drafts[c].side === "PRODUCT" ? -count : count;
                  return (
                    <td key={c} className={signed === 0 ? "zero" : signed > 0 ? "pos" : "neg"}>
                      {count === 0 ? "0" : signed}
                    </td>
                  );
                })}
              </tr>
            ))}
            {ratios.map((ratio, index) => (
              <tr key={`ratio-${index}`} className="ratio-constraint-row" data-testid="matrix-ratio-row">
                <td>
                  比例{index + 1}
                  <div className="mini-side ratio">
                    {ratio.a} : {ratio.b}
                  </div>
                </td>
                {ids.map((id, c) => {
                  const value =
                    id === ratio.a ? ratio.b_coefficient : id === ratio.b ? -ratio.a_coefficient : 0;
                  return (
                    <td key={c} className={value === 0 ? "zero" : value > 0 ? "pos" : "neg"}>
                      {value}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {ratios.length > 0 && (
        <p className="hint" data-testid="matrix-ratio-hint">
          比例约束行 q·c<sub>A</sub> − p·c<sub>B</sub> = 0 与守恒行共同消元。
        </p>
      )}
    </section>
  );
}

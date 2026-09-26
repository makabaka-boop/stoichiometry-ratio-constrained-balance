import { CompoundDraft } from "../lib/api";

interface Props {
  drafts: CompoundDraft[];
}

/** Read-only signed conservation matrix: reactants positive, products negative. */
export function MatrixPreview({ drafts }: Props) {
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

  return (
    <section className="panel matrix-preview" data-testid="matrix-preview">
      <h2>守恒矩阵预览</h2>
      <p className="hint">反应物列为正、产物列为负；消元在此矩阵上以有理数精确进行。</p>
      <div className="matrix-scroll">
        <table data-testid="matrix-table">
          <thead>
            <tr>
              <th>元素 \\ 化合物</th>
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
          </tbody>
        </table>
      </div>
    </section>
  );
}

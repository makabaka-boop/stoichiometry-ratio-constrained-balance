import { BalanceResult } from "../lib/api";

interface Props {
  result: BalanceResult;
  stale: boolean;
}

const STATUS_TEXT: Record<BalanceResult["status"], { title: string; tone: string }> = {
  BALANCED: { title: "唯一原始配方（可逐项验算）", tone: "ok" },
  NO_BALANCE: { title: "不可认证：守恒方程组无解", tone: "bad" },
  UNDERDETERMINED: { title: "不可认证：存在多组配方", tone: "warn" },
  NO_POSITIVE_BALANCE: { title: "不可认证：唯一解无法全为正", tone: "bad" },
};

export function ResultPanel({ result, stale }: Props) {
  const meta = STATUS_TEXT[result.status];

  return (
    <section
      className={`panel verdict tone-${meta.tone}${stale ? " stale" : ""}`}
      data-testid="result-panel"
      data-status={result.status}
      data-stale={stale ? "true" : "false"}
    >
      <div className="verdict-head">
        <h2>{meta.title}</h2>
        {stale && (
          <span className="stale-badge" data-testid="stale-badge">
            旧证书已撤销 · 输入已修改
          </span>
        )}
      </div>
      <p className="status-code" data-testid="result-status">
        状态码：{result.status}　·　零空间维数：{result.nullity}
      </p>

      {result.status === "BALANCED" && result.coefficients && result.element_totals ? (
        <>
          <p className="equation" data-testid="result-equation">
            {result.equation}
          </p>
          <table className="totals-table" data-testid="certificate-table">
            <thead>
              <tr>
                <th>元素</th>
                <th>反应物侧合计</th>
                <th>产物侧合计</th>
                <th>守恒</th>
              </tr>
            </thead>
            <tbody>
              {result.element_totals.map((row) => (
                <tr key={row.element} data-testid="total-row" data-element={row.element}>
                  <td>{row.element}</td>
                  <td>{row.reactant}</td>
                  <td>{row.product}</td>
                  <td>{row.balanced ? "✓" : "✗"}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <ul className="coefficient-list" data-testid="certificate-coefficients">
            {result.compound_ids.map((id) => (
              <li key={id} data-testid="certificate-coefficient" data-compound-id={id}>
                {id}：<strong>{result.coefficients![id]}</strong>
              </li>
            ))}
          </ul>
        </>
      ) : (
        <p className="reason" data-testid="result-reason">
          {result.reason}
        </p>
      )}
    </section>
  );
}

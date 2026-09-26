import { useMemo, useState } from "react";
import {
  ApiError,
  BalanceResult,
  CompoundDraft,
  ReviewResult,
  requestBalance,
  requestReview,
} from "./lib/api";
import { buildPayload, validateDrafts } from "./lib/validation";
import { CompoundEditor } from "./components/CompoundEditor";
import { MatrixPreview } from "./components/MatrixPreview";
import { ResultPanel } from "./components/ResultPanel";
import { ReviewPanel } from "./components/ReviewPanel";
import "./styles.css";

export default function App() {
  const [drafts, setDrafts] = useState<CompoundDraft[]>([]);
  /**
   * Bumped on EVERY edit of the input. A certificate records the revision
   * it was minted at; once currentRevision > certifiedRevision the old
   * certificate is visibly revoked, even before the next solve.
   */
  const [revision, setRevision] = useState(0);
  const [result, setResult] = useState<BalanceResult | null>(null);
  const [certifiedRevision, setCertifiedRevision] = useState<number | null>(null);
  const [balanceIssues, setBalanceIssues] = useState<string[]>([]);
  const [balanceBusy, setBalanceBusy] = useState(false);

  const [reviewValues, setReviewValues] = useState<Record<string, string>>({});
  const [reviewResult, setReviewResult] = useState<ReviewResult | null>(null);
  const [reviewSnapshot, setReviewSnapshot] = useState<{
    matrixRevision: number;
    values: Record<string, string>;
  } | null>(null);
  const [reviewError, setReviewError] = useState<string | null>(null);
  const [reviewBusy, setReviewBusy] = useState(false);

  const touch = () => {
    setRevision((value) => value + 1);
    setBalanceIssues([]);
  };

  const handleDraftsChange = (next: CompoundDraft[]) => {
    setDrafts(next);
    touch();
  };

  // Typing a candidate coefficient does NOT revoke the balance certificate
  // (which certifies the compound matrix), but it does invalidate any prior
  // review verdict, which certified those exact coefficient values.
  const handleReviewValue = (key: string, value: string) => {
    setReviewValues((current) => ({ ...current, [key]: value }));
  };

  const localIssues = useMemo(() => validateDrafts(drafts).map((i) => i.message), [drafts]);

  const handleBalance = async () => {
    if (localIssues.length > 0) {
      setBalanceIssues(localIssues);
      setResult(null);
      setCertifiedRevision(null);
      return;
    }
    setBalanceBusy(true);
    setBalanceIssues([]);
    try {
      const payload = buildPayload(drafts);
      const answer = await requestBalance(payload);
      setResult(answer);
      if (answer.status === "BALANCED" && answer.coefficients) {
        // A new certificate is minted; seed the manual review fields
        // with the certified primitive coefficients.
        setCertifiedRevision(revision);
        const seeded: Record<string, string> = {};
        drafts.forEach((draft) => {
          seeded[draft.key] = String(answer.coefficients![draft.id.trim()] ?? "");
        });
        setReviewValues(seeded);
      } else {
        setCertifiedRevision(null);
      }
    } catch (error) {
      const issues =
        error instanceof ApiError
          ? error.issues.map((issue) => `${issue.code}：${issue.message}`)
          : ["未知错误"];
      setBalanceIssues(issues);
      setResult(null);
      setCertifiedRevision(null);
    } finally {
      setBalanceBusy(false);
    }
  };

  const handleReview = async () => {
    if (localIssues.length > 0) {
      setReviewError(localIssues.join(" "));
      return;
    }
    const numeric: Record<string, number> = {};
    const badFields: string[] = [];
    drafts.forEach((draft, index) => {
      const raw = (reviewValues[draft.key] ?? "").trim();
      const value = Number(raw);
      if (!Number.isInteger(value) || value <= 0) {
        badFields.push(`#${index + 1} ${draft.id.trim()}`);
      } else {
        numeric[draft.id.trim()] = value;
      }
    });
    if (badFields.length > 0) {
      setReviewError(`以下化合物的系数不是正整数：${badFields.join("、")}。`);
      return;
    }

    setReviewBusy(true);
    setReviewError(null);
    try {
      const answer = await requestReview(buildPayload(drafts), numeric);
      setReviewResult(answer);
      setReviewSnapshot({ matrixRevision: revision, values: { ...reviewValues } });
    } catch (error) {
      setReviewError(
        error instanceof ApiError
          ? error.issues.map((issue) => `${issue.code}：${issue.message}`).join(" ")
          : "复核请求失败。",
      );
    } finally {
      setReviewBusy(false);
    }
  };

  const loadSample = () => {
    setDrafts([
      {
        key: "sample-1",
        id: "H2",
        side: "REACTANT",
        entries: [{ key: "sample-e1", symbol: "H", count: "2" }],
      },
      {
        key: "sample-2",
        id: "O2",
        side: "REACTANT",
        entries: [{ key: "sample-e2", symbol: "O", count: "2" }],
      },
      {
        key: "sample-3",
        id: "H2O",
        side: "PRODUCT",
        entries: [
          { key: "sample-e3", symbol: "H", count: "2" },
          { key: "sample-e4", symbol: "O", count: "1" },
        ],
      },
    ]);
    touch();
    setResult(null);
    setCertifiedRevision(null);
    setReviewResult(null);
    setReviewSnapshot(null);
    setReviewValues({});
  };

  const certificateStale =
    result?.status === "BALANCED" &&
    certifiedRevision !== null &&
    revision > certifiedRevision;
  const reviewStale =
    reviewSnapshot !== null &&
    (revision > reviewSnapshot.matrixRevision ||
      JSON.stringify(reviewValues) !== JSON.stringify(reviewSnapshot.values));

  return (
    <main className="app">
      <header>
        <h1>中试投料配平工作台</h1>
        <p className="subtitle">
          精确有理数高斯消元 · 原子守恒 · 唯一原始整数系数，或明确给出不可认证原因
        </p>
        <button type="button" className="ghost small" data-testid="load-sample" onClick={loadSample}>
          载入示例：H₂ + O₂ → H₂O
        </button>
      </header>

      <div className="layout">
        <div className="column">
          <CompoundEditor drafts={drafts} onChange={handleDraftsChange} />
          <MatrixPreview drafts={drafts} />
        </div>

        <div className="column">
          <section className="panel solve-bar">
            <button
              type="button"
              className="primary big"
              data-testid="solve-button"
              onClick={handleBalance}
              disabled={balanceBusy || drafts.length === 0}
            >
              {balanceBusy ? "精确求解中…" : "建立守恒矩阵并求解"}
            </button>
            {localIssues.length > 0 && drafts.length > 0 && (
              <div className="error-box" data-testid="local-issues">
                <strong>本地预检未通过（整份请求不会发送）：</strong>
                <ul>
                  {localIssues.map((message) => (
                    <li key={message}>{message}</li>
                  ))}
                </ul>
              </div>
            )}
            {balanceIssues.length > 0 && (
              <div className="error-box" data-testid="balance-issues">
                <strong>请求被拒绝：</strong>
                <ul>
                  {balanceIssues.map((message) => (
                    <li key={message}>{message}</li>
                  ))}
                </ul>
              </div>
            )}
          </section>

          {result && <ResultPanel result={result} stale={certificateStale} />}

          {drafts.length > 0 && (
            <ReviewPanel
              drafts={drafts}
              values={reviewValues}
              onValueChange={handleReviewValue}
              onReview={handleReview}
              busy={reviewBusy}
              result={reviewResult}
              error={reviewError}
              stale={reviewStale}
            />
          )}
        </div>
      </div>
    </main>
  );
}

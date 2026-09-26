export type Side = "REACTANT" | "PRODUCT";

/**
 * The editor keeps counts as raw strings so the user can transiently type
 * "12" without NaN flicker; validation converts them to positive integers.
 */
export interface EntryRow {
  key: string;
  symbol: string;
  count: string;
}

export interface CompoundDraft {
  key: string;
  id: string;
  side: Side;
  entries: EntryRow[];
}

/**
 * One approved feed-ratio row as edited in the UI. ``aKey``/``bKey`` are
 * compound draft keys (stable across id renames); the coefficients stay raw
 * strings so invalid text never overwrites the last valid form.
 */
export interface RatioDraft {
  key: string;
  aKey: string;
  bKey: string;
  aCoefficient: string;
  bCoefficient: string;
}

/** Wire shape of one approved ratio: coefficient[a] : coefficient[b]. */
export interface RatioSpec {
  a: string;
  b: string;
  a_coefficient: number;
  b_coefficient: number;
}

export interface RatioReport extends RatioSpec {
  satisfied: boolean;
}

export interface ElementTotal {
  element: string;
  reactant: number;
  product: number;
  balanced: boolean;
}

export type BalanceStatus =
  | "BALANCED"
  | "NO_BALANCE"
  | "UNDERDETERMINED"
  | "NO_POSITIVE_BALANCE";

export interface BalanceResult {
  status: BalanceStatus;
  nullity: number;
  reason?: string;
  elements: string[];
  compound_ids: string[];
  coefficients?: Record<string, number>;
  element_totals?: ElementTotal[];
  equation?: string;
  /** Echo of the approved ratios the certificate was issued under. */
  ratios?: RatioSpec[];
}

export interface ReviewResult {
  valid: boolean;
  reasons: string[];
  gcd: number | null;
  primitive: boolean;
  missing_ids: string[];
  unknown_ids: string[];
  non_positive_ids: string[];
  unbalanced_elements: string[];
  elements: ElementTotal[];
  /** Per-ratio verdicts, present when the review included ratio checks. */
  ratios?: RatioReport[];
  violated_ratios?: number[];
}

export interface ApiIssue {
  code: string;
  message: string;
  loc?: string;
  compound_id?: string;
  element?: string;
  value?: unknown;
}

export class ApiError extends Error {
  readonly issues: ApiIssue[];
  constructor(issues: ApiIssue[]) {
    super(issues.map((issue) => issue.message).join("; "));
    this.issues = issues;
  }
}

async function postJson<T>(path: string, body: unknown): Promise<T> {
  let response: Response;
  try {
    response = await fetch(path, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
  } catch {
    throw new ApiError([
      {
        code: "NETWORK_ERROR",
        message: "无法连接计算服务，请确认 api 服务已启动。",
      },
    ]);
  }
  const payload = await response.json().catch(() => null);
  if (response.status === 422 && payload && Array.isArray(payload.issues)) {
    throw new ApiError(payload.issues as ApiIssue[]);
  }
  if (!response.ok) {
    throw new ApiError([
      { code: "HTTP_ERROR", message: `服务返回 ${response.status}。` },
    ]);
  }
  return payload as T;
}

export function requestBalance(
  compounds: Array<{ id: string; side: Side; composition: Record<string, number> }>,
): Promise<BalanceResult> {
  return postJson("/api/balance", { compounds });
}

export function requestReview(
  compounds: Array<{ id: string; side: Side; composition: Record<string, number> }>,
  coefficients: Record<string, number>,
): Promise<ReviewResult> {
  return postJson("/api/review", { compounds, coefficients });
}

export function requestConstrainedBalance(
  compounds: Array<{ id: string; side: Side; composition: Record<string, number> }>,
  ratios: RatioSpec[],
): Promise<BalanceResult> {
  return postJson("/api/balance/constrained", { compounds, ratios });
}

export function requestConstrainedReview(
  compounds: Array<{ id: string; side: Side; composition: Record<string, number> }>,
  coefficients: Record<string, number>,
  ratios: RatioSpec[],
): Promise<ReviewResult> {
  return postJson("/api/review/constrained", { compounds, coefficients, ratios });
}

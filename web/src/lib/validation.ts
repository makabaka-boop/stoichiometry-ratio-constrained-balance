import { CompoundDraft, RatioDraft, RatioSpec } from "./api";
import { ELEMENT_SYMBOLS } from "./elements";

export interface LocalIssue {
  message: string;
}

export const MIN_COMPOUNDS = 2;
export const MAX_COMPOUNDS = 12;
export const MAX_ELEMENTS = 20;
export const MIN_RATIOS = 1;
export const MAX_RATIOS = 2;

/**
 * Mirror of the server-side semantic checks. The server remains the
 * authority (it rejects the whole batch with stable error codes), but
 * pre-validating keeps the round-trip free of trivially fixable errors.
 */
export function validateDrafts(drafts: CompoundDraft[]): LocalIssue[] {
  const issues: LocalIssue[] = [];

  if (drafts.length < MIN_COMPOUNDS || drafts.length > MAX_COMPOUNDS) {
    issues.push({
      message: `化合物数量必须在 ${MIN_COMPOUNDS} 至 ${MAX_COMPOUNDS} 之间（当前 ${drafts.length}）。`,
    });
  }

  const seenIds = new Set<string>();
  const elementSymbols = new Set<string>();

  drafts.forEach((draft, index) => {
    const where = `化合物 ${index + 1}`;
    const id = draft.id.trim();

    if (id === "") {
      issues.push({ message: `${where}：ID 不能为空。` });
    } else {
      if (!/^[\x20-\x7E]+$/.test(id)) {
        issues.push({ message: `${where}：ID 必须为 ASCII 字符。` });
      }
      if (seenIds.has(id)) {
        issues.push({ message: `${where}：ID “${id}” 重复，所有 ID 必须唯一。` });
      }
      seenIds.add(id);
    }

    const validEntries = draft.entries.filter((entry) => entry.symbol.trim() !== "");
    if (validEntries.length === 0) {
      issues.push({ message: `${where}${id ? `（${id}）` : ""}：组成不能为空。` });
    }

    const localSymbols = new Set<string>();
    for (const entry of validEntries) {
      const symbol = entry.symbol.trim();
      const count = Number(entry.count);
      if (!ELEMENT_SYMBOLS.has(symbol)) {
        issues.push({ message: `${where}：元素符号 “${symbol}” 不被识别。` });
      }
      if (localSymbols.has(symbol)) {
        issues.push({ message: `${where}：元素 “${symbol}” 在同一化合物中重复。` });
      }
      localSymbols.add(symbol);
      if (!Number.isInteger(count) || count <= 0) {
        issues.push({
          message: `${where}：元素 “${symbol}” 的原子数必须为正整数（当前 “${entry.count}”）。`,
        });
      }
      elementSymbols.add(symbol);
    }
  });

  if (elementSymbols.size > MAX_ELEMENTS) {
    issues.push({
      message: `共出现 ${elementSymbols.size} 种元素，上限为 ${MAX_ELEMENTS} 种。`,
    });
  }

  return issues;
}

/** Build the JSON composition map; only call this after validateDrafts passes. */
export function buildPayload(drafts: CompoundDraft[]) {
  return drafts.map((draft) => {
    const composition: Record<string, number> = {};
    for (const entry of draft.entries) {
      const symbol = entry.symbol.trim();
      if (symbol === "") continue;
      composition[symbol] = Number(entry.count);
    }
    return { id: draft.id.trim(), side: draft.side, composition };
  });
}

export interface RatioResolution {
  specs: RatioSpec[];
  issues: string[];
}

/**
 * Mirror of the server-side ratio checks. Resolves draft keys to compound
 * IDs and parses the raw coefficient strings; anything invalid is reported
 * and produces no spec, so an invalid edit can never overwrite the last
 * valid ratios submitted to the server.
 */
export function resolveRatioSpecs(
  ratios: RatioDraft[],
  drafts: CompoundDraft[],
): RatioResolution {
  const issues: string[] = [];
  const specs: RatioSpec[] = [];

  if (ratios.length < MIN_RATIOS || ratios.length > MAX_RATIOS) {
    issues.push(`比例约束需填写 ${MIN_RATIOS}–${MAX_RATIOS} 条（当前 ${ratios.length} 条）。`);
  }

  ratios.forEach((ratio, index) => {
    const where = `比例 ${index + 1}`;
    const aDraft = drafts.find((draft) => draft.key === ratio.aKey);
    const bDraft = drafts.find((draft) => draft.key === ratio.bKey);
    const a = aDraft?.id.trim() ?? "";
    const b = bDraft?.id.trim() ?? "";

    if (!aDraft || a === "") {
      issues.push(`${where}：化合物 A 未选择（引用的化合物可能已删除或尚未命名）。`);
    }
    if (!bDraft || b === "") {
      issues.push(`${where}：化合物 B 未选择（引用的化合物可能已删除或尚未命名）。`);
    }
    if (aDraft && bDraft && ratio.aKey === ratio.bKey) {
      issues.push(`${where}：化合物 A 与 B 必须是两种不同的化合物。`);
    }

    const pText = ratio.aCoefficient.trim();
    const qText = ratio.bCoefficient.trim();
    const pValid = /^\d+$/.test(pText) && Number(pText) > 0;
    const qValid = /^\d+$/.test(qText) && Number(qText) > 0;
    if (!pValid) {
      issues.push(`${where}：化合物 A 的系数必须为正整数（当前 “${ratio.aCoefficient}”）。`);
    }
    if (!qValid) {
      issues.push(`${where}：化合物 B 的系数必须为正整数（当前 “${ratio.bCoefficient}”）。`);
    }

    if (a !== "" && b !== "" && ratio.aKey !== ratio.bKey && pValid && qValid) {
      specs.push({ a, b, a_coefficient: Number(pText), b_coefficient: Number(qText) });
    }
  });

  return { specs, issues };
}

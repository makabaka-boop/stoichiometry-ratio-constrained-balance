import { CompoundDraft } from "./api";
import { ELEMENT_SYMBOLS } from "./elements";

export interface LocalIssue {
  message: string;
}

export const MIN_COMPOUNDS = 2;
export const MAX_COMPOUNDS = 12;
export const MAX_ELEMENTS = 20;

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

import { CompoundDraft, Side } from "../lib/api";

interface Props {
  drafts: CompoundDraft[];
  onChange: (drafts: CompoundDraft[]) => void;
}

let counter = 0;
function uid(prefix: string): string {
  counter += 1;
  return `${prefix}-${Date.now()}-${counter}`;
}

export function emptyCompound(side: Side = "REACTANT"): CompoundDraft {
  return { key: uid("c"), id: "", side, entries: [{ key: uid("e"), symbol: "", count: "1" }] };
}

export function CompoundEditor({ drafts, onChange }: Props) {
  const update = (key: string, patch: Partial<CompoundDraft>) => {
    onChange(drafts.map((draft) => (draft.key === key ? { ...draft, ...patch } : draft)));
  };

  const updateEntry = (compoundKey: string, entryKey: string, patch: { symbol?: string; count?: string }) => {
    onChange(
      drafts.map((draft) =>
        draft.key !== compoundKey
          ? draft
          : {
              ...draft,
              entries: draft.entries.map((entry) =>
                entry.key === entryKey ? { ...entry, ...patch } : entry,
              ),
            },
      ),
    );
  };

  const removeCompound = (key: string) => {
    onChange(drafts.filter((draft) => draft.key !== key));
  };

  const addEntry = (compoundKey: string) => {
    onChange(
      drafts.map((draft) =>
        draft.key === compoundKey
          ? { ...draft, entries: [...draft.entries, { key: uid("e"), symbol: "", count: "1" }] }
          : draft,
      ),
    );
  };

  const removeEntry = (compoundKey: string, entryKey: string) => {
    onChange(
      drafts.map((draft) =>
        draft.key === compoundKey
          ? { ...draft, entries: draft.entries.filter((entry) => entry.key !== entryKey) }
          : draft,
      ),
    );
  };

  const addCompound = (side: Side) => {
    onChange([...drafts, emptyCompound(side)]);
  };

  return (
    <section className="panel" data-testid="compound-editor">
      <h2>化合物矩阵</h2>
      <p className="hint">
        录入 2–12 个唯一 ASCII ID，每项标明反应物 / 产物，并以「元素符号 → 正整数」表示组成；
        未知字段、重复 ID、非法符号或空组成都会被整份拒绝。
      </p>

      <div className="compound-list">
        {drafts.map((draft, index) => (
          <div
            key={draft.key}
            className={`compound-card side-${draft.side.toLowerCase()}`}
            data-testid="compound-card"
            data-compound-key={draft.key}
          >
            <div className="compound-head">
              <span className="compound-index">#{index + 1}</span>
              <input
                className="id-input"
                data-testid="compound-id"
                value={draft.id}
                placeholder="化合物 ID（ASCII）"
                onChange={(event) => update(draft.key, { id: event.target.value })}
              />
              <select
                data-testid="compound-side"
                value={draft.side}
                onChange={(event) => update(draft.key, { side: event.target.value as Side })}
              >
                <option value="REACTANT">反应物 REACTANT</option>
                <option value="PRODUCT">产物 PRODUCT</option>
              </select>
              <button
                type="button"
                className="danger small"
                data-testid="remove-compound"
                onClick={() => removeCompound(draft.key)}
              >
                删除
              </button>
            </div>
            <div className="entry-list">
              {draft.entries.map((entry) => (
                <div key={entry.key} className="entry-row" data-testid="entry-row">
                  <input
                    className="symbol-input"
                    data-testid="entry-symbol"
                    value={entry.symbol}
                    placeholder="元素"
                    onChange={(event) =>
                      updateEntry(draft.key, entry.key, { symbol: event.target.value })
                    }
                  />
                  <span className="arrow">→</span>
                  <input
                    className="count-input"
                    data-testid="entry-count"
                    value={entry.count}
                    inputMode="numeric"
                    onChange={(event) =>
                      updateEntry(draft.key, entry.key, { count: event.target.value })
                    }
                  />
                  <button
                    type="button"
                    className="ghost small"
                    data-testid="remove-entry"
                    onClick={() => removeEntry(draft.key, entry.key)}
                  >
                    ×
                  </button>
                </div>
              ))}
              <button
                type="button"
                className="ghost small"
                data-testid="add-entry"
                onClick={() => addEntry(draft.key)}
              >
                + 元素
              </button>
            </div>
          </div>
        ))}
      </div>

      <div className="editor-actions">
        <button
          type="button"
          className="secondary"
          data-testid="add-reactant"
          onClick={() => addCompound("REACTANT")}
        >
          + 反应物
        </button>
        <button
          type="button"
          className="secondary"
          data-testid="add-product"
          onClick={() => addCompound("PRODUCT")}
        >
          + 产物
        </button>
        <button
          type="button"
          className="ghost small"
          data-testid="clear-all"
          onClick={() => onChange([])}
        >
          清空全部
        </button>
      </div>
    </section>
  );
}

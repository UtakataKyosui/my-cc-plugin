import {
  entryKey,
  isExpired,
  KEY_PREFIX,
  parseEntry,
  type Rating,
  type UseEntry,
  type UseGroup,
} from "./entries";

export type Store = {
  get: (key: string) => Promise<unknown>;
  set: (key: string, value: unknown) => Promise<void>;
  delete: (key: string) => Promise<void>;
  keys: () => Promise<string[]>;
};

export type StoredUse = {
  key: string;
  entry: UseEntry;
};

let seq = 0;

export async function recordUse(store: Store, entry: UseEntry): Promise<string> {
  const key = entryKey(entry.sessionId, entry.at, seq++);
  await store.set(key, entry);
  return key;
}

export async function listUses(store: Store): Promise<StoredUse[]> {
  const uses: StoredUse[] = [];
  for (const key of await store.keys()) {
    if (!key.startsWith(KEY_PREFIX)) continue;
    const entry = parseEntry(await store.get(key));
    if (entry) uses.push({ key, entry });
  }
  return uses;
}

/**
 * 同じ名前の未評価の使用すべてに同じ評価を書く。1回答えれば、その名前の
 * まとめて聞かれた分が片付く。
 */
export async function applyRating(
  store: Store,
  uses: readonly StoredUse[],
  group: UseGroup,
  rating: Rating,
  nowMs: number,
  note?: string,
): Promise<number> {
  let written = 0;
  for (const { key, entry } of uses) {
    if (entry.rating) continue;
    if (entry.kind !== group.kind || entry.name !== group.name) continue;

    const rated: UseEntry = { ...entry, rating, ratedAt: nowMs };
    if (note) rated.note = note;
    await store.set(key, rated);
    written += 1;
  }
  return written;
}

export async function pruneUses(store: Store, nowMs: number, keepDays: number): Promise<number> {
  let removed = 0;
  for (const { key, entry } of await listUses(store)) {
    if (!isExpired(entry, nowMs, keepDays)) continue;
    await store.delete(key);
    removed += 1;
  }
  return removed;
}

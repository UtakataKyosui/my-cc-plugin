export type UseKind = "skill" | "agent";

export type Rating = "good" | "fine" | "bad" | "skip";

export type UseEntry = {
  kind: UseKind;
  name: string;
  /** 使った時刻。epoch ミリ秒。 */
  at: number;
  sessionId: string;
  /** SubAgent のときは Agent ツールに渡された description。 */
  detail?: string;
  rating?: Rating;
  ratedAt?: number;
  /** 選択肢以外を打ったときの自由入力。 */
  note?: string;
};

/** 評価をまとめて付ける単位。同じ名前の複数回の使用を1件として扱う。 */
export type UseGroup = {
  kind: UseKind;
  name: string;
  count: number;
  lastAt: number;
};

export const KEY_PREFIX = "use:";

const RATINGS: Record<string, Rating> = {
  good: "good",
  fine: "fine",
  bad: "bad",
  skip: "skip",
};

export function entryKey(sessionId: string, nowMs: number, seq: number): string {
  return `${KEY_PREFIX}${sessionId}:${nowMs}-${seq}`;
}

/** ダイアログの答えを評価に直す。選択肢以外は自由入力とみなす。 */
export function ratingOf(answer: string): Rating | undefined {
  return RATINGS[answer.trim().toLowerCase()];
}

export function parseEntry(value: unknown): UseEntry | undefined {
  if (value === null || typeof value !== "object") return undefined;
  const v = value as Record<string, unknown>;

  const kind = v.kind === "skill" || v.kind === "agent" ? v.kind : undefined;
  if (!kind) return undefined;
  if (typeof v.name !== "string" || v.name === "") return undefined;
  if (typeof v.at !== "number" || !Number.isFinite(v.at)) return undefined;
  if (typeof v.sessionId !== "string") return undefined;

  const entry: UseEntry = { kind, name: v.name, at: v.at, sessionId: v.sessionId };
  if (typeof v.detail === "string") entry.detail = v.detail;
  if (typeof v.rating === "string" && RATINGS[v.rating]) entry.rating = RATINGS[v.rating];
  if (typeof v.ratedAt === "number" && Number.isFinite(v.ratedAt)) entry.ratedAt = v.ratedAt;
  if (typeof v.note === "string") entry.note = v.note;
  return entry;
}

/**
 * 未評価の使用を名前ごとにまとめ、新しく使ったものから順に並べる。
 *
 * 1つの Skill は1ターンに何度も展開される。SubAgent が `skills:` で
 * プリロードする分も同じ名前で来るので、名前で束ねてから聞く。
 */
export function unratedGroups(entries: readonly UseEntry[]): UseGroup[] {
  const groups = new Map<string, UseGroup>();
  for (const entry of entries) {
    if (entry.rating) continue;
    const key = `${entry.kind}:${entry.name}`;
    const group = groups.get(key);
    if (group) {
      group.count += 1;
      group.lastAt = Math.max(group.lastAt, entry.at);
    } else {
      groups.set(key, { kind: entry.kind, name: entry.name, count: 1, lastAt: entry.at });
    }
  }
  return [...groups.values()].sort((a, b) => b.lastAt - a.lastAt);
}

/** 評価済みも含めた集計。stats 引数で出す表の材料。 */
export function tally(entries: readonly UseEntry[]): {
  kind: UseKind;
  name: string;
  count: number;
  good: number;
  fine: number;
  bad: number;
}[] {
  const rows = new Map<string, ReturnType<typeof tally>[number]>();
  for (const entry of entries) {
    const key = `${entry.kind}:${entry.name}`;
    const row = rows.get(key) ?? { kind: entry.kind, name: entry.name, count: 0, good: 0, fine: 0, bad: 0 };
    row.count += 1;
    if (entry.rating === "good") row.good += 1;
    if (entry.rating === "fine") row.fine += 1;
    if (entry.rating === "bad") row.bad += 1;
    rows.set(key, row);
  }
  return [...rows.values()].sort((a, b) => b.count - a.count || a.name.localeCompare(b.name));
}

export function isExpired(entry: UseEntry, nowMs: number, keepDays: number): boolean {
  return nowMs - entry.at > keepDays * 24 * 60 * 60 * 1000;
}

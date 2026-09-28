import type { Rating, UseGroup, UseKind } from "./entries";
import { tally, type UseEntry } from "./entries";

export type RatedResult = {
  group: UseGroup;
  rating: Rating;
  note?: string;
};

export type Scope = "session" | "all";

/** 登録するスラッシュコマンドの名前。built-in の名前は登録を拒否されるので、/feedback は使えない。 */
export const COMMAND = "rate-usage";

const LABEL: Record<Rating, string> = {
  good: "Good",
  fine: "Fine",
  bad: "Bad",
  skip: "Skip",
};

const KIND_LABEL: Record<UseKind, string> = {
  skill: "skill",
  agent: "agent",
};

export function question(group: UseGroup): string {
  const times = group.count > 1 ? `（${group.count} 回）` : "";
  return `${KIND_LABEL[group.kind]}: ${group.name}${times} はどうでしたか？`;
}

/** 記録が1件も無いときの文面。評価し終えた状態と読み違えないようにする。 */
export function noRecordsText(scope: Scope): string {
  return scope === "all"
    ? "Skill も SubAgent もまだ記録されていません。"
    : `このセッションではまだ Skill も SubAgent も使っていません。/${COMMAND} all で他のセッションの分を見られます。`;
}

export function noUnratedText(scope: Scope): string {
  return scope === "all"
    ? "未評価の Skill と SubAgent はありません。"
    : `このセッションで使った Skill と SubAgent は、すべて評価済みです。/${COMMAND} all で他のセッションの分も聞けます。`;
}

export function ratedText(results: readonly RatedResult[], remaining: number): string {
  if (results.length === 0) {
    return remaining > 0 ? `評価を記録しませんでした。未評価は ${remaining} 件のままです。` : "評価を記録しませんでした。";
  }

  const lines = [
    "評価を記録しました。",
    "",
    "| 種別 | 名前 | 評価 | 件数 |",
    "|---|---|---|---|",
    ...results.map(
      ({ group, rating, note }) =>
        `| ${KIND_LABEL[group.kind]} | ${group.name} | ${LABEL[rating]}${note ? ` (${note})` : ""} | ${group.count} |`,
    ),
  ];

  if (remaining > 0) {
    lines.push("", `残り ${remaining} 件は未評価のままです。もう一度 /${COMMAND} を叩くと続きから聞きます。`);
  }
  return lines.join("\n");
}

export function statsText(entries: readonly UseEntry[]): string {
  const rows = tally(entries);
  if (rows.length === 0) return "まだ Skill も SubAgent も記録されていません。";

  return [
    `記録は ${entries.length} 件、名前は ${rows.length} 種類です。`,
    "",
    "| 種別 | 名前 | 使用 | Good | Fine | Bad |",
    "|---|---|---|---|---|---|",
    ...rows.map(
      (r) => `| ${KIND_LABEL[r.kind]} | ${r.name} | ${r.count} | ${r.good} | ${r.fine} | ${r.bad} |`,
    ),
  ].join("\n");
}

import { expect, test } from "claude-code/testing";
import type { UseEntry, UseGroup } from "../hooks/entries";
import { COMMAND, noRecordsText, noUnratedText, question, ratedText, statsText } from "../hooks/report";

const NOW = 1_789_632_000_000; // 2026-09-17 17:00:00 JST
const group = (over: Partial<UseGroup> = {}): UseGroup => ({
  kind: "skill",
  name: "gh-wheel",
  count: 1,
  lastAt: NOW,
  ...over,
});

test("question は種別と名前を出し、複数回なら回数も出す", async () => {
  expect(question(group())).toBe("skill: gh-wheel はどうでしたか？");
  expect(question(group({ count: 3 }))).toBe("skill: gh-wheel（3 回） はどうでしたか？");
  expect(question(group({ kind: "agent", name: "role-verifier" }))).toBe(
    "agent: role-verifier はどうでしたか？",
  );
});

test("COMMAND は register.ts が登録する名前と一致する", async () => {
  // register.ts は validate が読めるように名前を直書きしている。文面とずれないよう固定する
  expect(COMMAND).toBe("rate-usage");
  expect(COMMAND).not.toBe("feedback");
});

test("noUnratedText はスコープで文面を変える", async () => {
  expect(noUnratedText("all")).toContain("未評価の Skill と SubAgent はありません");
  expect(noUnratedText("session")).toContain(`/${COMMAND} all`);
});

test("noRecordsText は記録が無いことを、評価済みと区別して言う", async () => {
  expect(noRecordsText("session")).toContain("まだ Skill も SubAgent も使っていません");
  expect(noRecordsText("session")).not.toContain("評価済み");
  expect(noRecordsText("all")).toContain("まだ記録されていません");
});

test("ratedText は表と残り件数を出す", async () => {
  const text = ratedText([{ group: group({ count: 2 }), rating: "good" }], 1);
  expect(text).toContain("| skill | gh-wheel | Good | 2 |");
  expect(text).toContain("残り 1 件");
});

test("ratedText は自由入力を評価の横に添える", async () => {
  const text = ratedText([{ group: group(), rating: "skip", note: "出力が長い" }], 0);
  expect(text).toContain("Skip (出力が長い)");
  expect(text).not.toContain("残り");
});

test("ratedText は1件も答えなかったときに残り件数を言う", async () => {
  expect(ratedText([], 3)).toBe("評価を記録しませんでした。未評価は 3 件のままです。");
});

test("statsText は記録が無いことを言える", async () => {
  expect(statsText([])).toBe("まだ Skill も SubAgent も記録されていません。");
});

test("statsText は使用回数と評価の内訳を並べる", async () => {
  const entries: UseEntry[] = [
    { kind: "skill", name: "gh-wheel", at: NOW, sessionId: "s1", rating: "good" },
    { kind: "skill", name: "gh-wheel", at: NOW, sessionId: "s1", rating: "bad" },
    { kind: "agent", name: "role-verifier", at: NOW, sessionId: "s1" },
  ];
  const text = statsText(entries);
  expect(text).toContain("記録は 3 件、名前は 2 種類です。");
  expect(text).toContain("| skill | gh-wheel | 2 | 1 | 0 | 1 |");
});

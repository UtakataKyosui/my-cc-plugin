import { expect, test } from "claude-code/testing";
import {
  entryKey,
  isExpired,
  parseEntry,
  ratingOf,
  tally,
  unratedGroups,
  type UseEntry,
} from "../hooks/entries";

const NOW = 1_789_632_000_000; // 2026-09-17 17:00:00 JST
const DAY = 24 * 60 * 60 * 1000;

const use = (over: Partial<UseEntry> = {}): UseEntry => ({
  kind: "skill",
  name: "gh-wheel",
  at: NOW,
  sessionId: "s1",
  ...over,
});

test("entryKey はセッションと時刻と連番で衝突を避ける", async () => {
  expect(entryKey("s1", NOW, 0)).toBe(`use:s1:${NOW}-0`);
  expect(entryKey("s1", NOW, 1)).not.toBe(entryKey("s1", NOW, 0));
});

test("ratingOf は選択肢を大文字小文字なしで読む", async () => {
  expect(ratingOf("Good")).toBe("good");
  expect(ratingOf(" bad ")).toBe("bad");
  expect(ratingOf("Skip")).toBe("skip");
  expect(ratingOf("もうちょい速くしてほしい")).toBeUndefined();
});

test("parseEntry は必須の欠けた値を弾く", async () => {
  expect(parseEntry(use())).toEqual(use());
  expect(parseEntry({ kind: "skill", name: "x", sessionId: "s1" })).toBeUndefined();
  expect(parseEntry({ kind: "other", name: "x", at: NOW, sessionId: "s1" })).toBeUndefined();
  expect(parseEntry(null)).toBeUndefined();
});

test("parseEntry は知らない評価を落とす", async () => {
  const entry = parseEntry({ ...use(), rating: "great" });
  expect(entry?.rating).toBeUndefined();
});

test("unratedGroups は同じ名前をまとめ、新しい順に並べる", async () => {
  const groups = unratedGroups([
    use({ name: "gh-wheel", at: NOW - 1000 }),
    use({ name: "gh-wheel", at: NOW }),
    use({ kind: "agent", name: "role-verifier", at: NOW - 5000 }),
  ]);

  expect(groups).toEqual([
    { kind: "skill", name: "gh-wheel", count: 2, lastAt: NOW },
    { kind: "agent", name: "role-verifier", count: 1, lastAt: NOW - 5000 },
  ]);
});

test("unratedGroups は評価済みを外す", async () => {
  const groups = unratedGroups([use({ rating: "good" }), use({ name: "other" })]);
  expect(groups.map((g) => g.name)).toEqual(["other"]);
});

test("unratedGroups は種別が違えば別の行にする", async () => {
  const groups = unratedGroups([use({ name: "same" }), use({ kind: "agent", name: "same" })]);
  expect(groups.length).toBe(2);
});

test("tally は評価の内訳を数える", async () => {
  const rows = tally([
    use({ rating: "good" }),
    use({ rating: "bad" }),
    use(),
    use({ kind: "agent", name: "role-reviewer", rating: "fine" }),
  ]);

  expect(rows[0]).toEqual({ kind: "skill", name: "gh-wheel", count: 3, good: 1, fine: 0, bad: 1 });
  expect(rows[1]).toEqual({ kind: "agent", name: "role-reviewer", count: 1, good: 0, fine: 1, bad: 0 });
});

test("isExpired は保持日数を過ぎたものだけ true", async () => {
  expect(isExpired(use({ at: NOW - 89 * DAY }), NOW, 90)).toBe(false);
  expect(isExpired(use({ at: NOW - 91 * DAY }), NOW, 90)).toBe(true);
});

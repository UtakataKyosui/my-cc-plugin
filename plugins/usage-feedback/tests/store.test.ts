import { expect, test } from "claude-code/testing";
import type { UseEntry } from "../hooks/entries";
import { applyRating, listUses, pruneUses, recordUse, type Store } from "../hooks/store";

const NOW = 1_789_632_000_000; // 2026-09-17 17:00:00 JST
const DAY = 24 * 60 * 60 * 1000;

function memoryStore(seed: Record<string, unknown> = {}): Store {
  const data = new Map(Object.entries(seed));
  return {
    get: async (key) => data.get(key),
    set: async (key, value) => void data.set(key, value),
    delete: async (key) => void data.delete(key),
    keys: async () => [...data.keys()],
  };
}

const use = (over: Partial<UseEntry> = {}): UseEntry => ({
  kind: "skill",
  name: "gh-wheel",
  at: NOW,
  sessionId: "s1",
  ...over,
});

test("recordUse と listUses は往復する", async () => {
  const store = memoryStore();
  await recordUse(store, use());
  await recordUse(store, use({ kind: "agent", name: "role-verifier" }));

  const uses = await listUses(store);
  expect(uses.length).toBe(2);
  expect(uses.map((u) => u.entry.name).sort()).toEqual(["gh-wheel", "role-verifier"]);
});

test("listUses は use: 以外のキーと壊れた値を読まない", async () => {
  const store = memoryStore({
    "use:s1:1-0": use(),
    "use:s1:1-1": { kind: "skill" },
    "session:x": { usd: 1 },
  });
  const uses = await listUses(store);
  expect(uses.length).toBe(1);
});

test("applyRating は同じ名前の未評価すべてに書く", async () => {
  const store = memoryStore({
    "use:s1:1-0": use(),
    "use:s1:1-1": use(),
    "use:s1:1-2": use({ name: "other" }),
  });
  const uses = await listUses(store);

  const written = await applyRating(
    store,
    uses,
    { kind: "skill", name: "gh-wheel", count: 2, lastAt: NOW },
    "good",
    NOW,
  );

  expect(written).toBe(2);
  const after = await listUses(store);
  expect(after.filter((u) => u.entry.rating === "good").length).toBe(2);
  expect(after.find((u) => u.entry.name === "other")?.entry.rating).toBeUndefined();
});

test("applyRating は評価済みを上書きしない", async () => {
  const store = memoryStore({ "use:s1:1-0": use({ rating: "bad", ratedAt: NOW - 1 }) });
  const uses = await listUses(store);

  const written = await applyRating(
    store,
    uses,
    { kind: "skill", name: "gh-wheel", count: 1, lastAt: NOW },
    "good",
    NOW,
  );

  expect(written).toBe(0);
  expect((await listUses(store))[0]?.entry.rating).toBe("bad");
});

test("applyRating は自由入力を note に残す", async () => {
  const store = memoryStore({ "use:s1:1-0": use() });
  const uses = await listUses(store);

  await applyRating(
    store,
    uses,
    { kind: "skill", name: "gh-wheel", count: 1, lastAt: NOW },
    "skip",
    NOW,
    "出力が長い",
  );

  const after = (await listUses(store))[0]?.entry;
  expect(after?.rating).toBe("skip");
  expect(after?.note).toBe("出力が長い");
});

test("pruneUses は保持日数を過ぎたものだけ消す", async () => {
  const store = memoryStore({
    "use:s1:1-0": use({ at: NOW - 100 * DAY, rating: "good" }),
    "use:s1:1-1": use({ at: NOW - 10 * DAY }),
    keep: { usd: 1 },
  });

  const removed = await pruneUses(store, NOW, 90);
  expect(removed).toBe(1);
  expect((await store.keys()).sort()).toEqual(["keep", "use:s1:1-1"]);
});

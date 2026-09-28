import type { Register } from "claude-code";
import { ratingOf, unratedGroups, type UseEntry } from "./entries";
import {
  COMMAND,
  noRecordsText,
  noUnratedText,
  question,
  ratedText,
  statsText,
  type RatedResult,
  type Scope,
} from "./report";
import { applyRating, listUses, pruneUses, recordUse, type Store } from "./store";

const ANSWERS = ["Good", "Fine", "Bad", "Skip"] as const;

/** 記録を残す日数。これを過ぎた使用は評価の有無にかかわらず落とす。 */
function keepDaysOf(options: Readonly<Record<string, unknown>>): number {
  const days = Number(options.keepDays);
  return Number.isFinite(days) && days > 0 ? Math.round(days) : 90;
}

export const register: Register = (on, options) => {
  const keepDays = keepDaysOf(options);
  let sessionId = "";
  let store: Store | undefined;

  const remember = async (entry: Omit<UseEntry, "sessionId">) => {
    if (!store) return;
    try {
      await recordUse(store, { ...entry, sessionId });
    } catch {
      // 記録できなくても、使おうとしている Skill や SubAgent は止めない
    }
  };

  on("session.start", async ($, e, next) => {
    sessionId = await $.session.id();
    store = {
      get: (key) => $.store.get(key),
      set: (key, value) => $.store.set(key, value),
      delete: (key) => $.store.delete(key),
      keys: () => $.store.keys(),
    };

    await pruneUses(store, await $.clock.now(), keepDays);
    try {
      await $.command.register({
        name: "rate-usage",
        description: "使った Skill と SubAgent に Good・Fine・Bad を付ける",
        argumentHint: "[all|stats]",
      });
    } catch (error) {
      // 名前が built-in と衝突すると登録は拒否される。黙って消えると
      // 記録だけ溜まって評価できなくなるので、理由をその場に出す
      $.ui.log(`usage-feedback: /${COMMAND} を登録できませんでした: ${String(error)}`);
    }
    return next(e);
  }).catch(($, e, next) => next(e));

  // 記録は next の前に済ませる。next のあとで投げると、その先の
  // .catch が next をもう一度呼んで二重に起動する余地が残る
  on("skill.prompt", async ($, e, next) => {
    await remember({ kind: "skill", name: e.skill, at: await $.clock.now() });
    return next(e);
  }).catch(($, e, next) => next(e));

  on("agent.spawn", async ($, e, next) => {
    await remember({
      kind: "agent",
      name: e.subagentType,
      at: await $.clock.now(),
      detail: e.description,
    });
    return next(e);
  }).catch(($, e, next) => next(e));

  on("command.run", { command: "rate-usage" }, async ($, e, next) => {
    if (!store) return next(e);

    const arg = e.args.trim().toLowerCase();
    const uses = await listUses(store);

    if (arg === "stats") {
      return { text: statsText(uses.map((u) => u.entry)) };
    }

    const scope: Scope = arg === "all" ? "all" : "session";
    const inScope = uses.filter((u) => scope === "all" || u.entry.sessionId === sessionId);
    if (inScope.length === 0) return { text: noRecordsText(scope) };

    const groups = unratedGroups(inScope.map((u) => u.entry));
    if (groups.length === 0) return { text: noUnratedText(scope) };

    const rated: RatedResult[] = [];
    for (const group of groups) {
      let answer: string;
      try {
        answer = await $.ui.ask(question(group), { options: ANSWERS, header: "評価" });
      } catch {
        // 閉じられた・中断された。ここまでの評価は書けているので打ち切る
        break;
      }

      const rating = ratingOf(answer);
      // 選択肢以外を打たれたら、点は付けずに書かれた文だけ残す
      const note = rating ? undefined : answer;
      await applyRating(store, inScope, group, rating ?? "skip", await $.clock.now(), note);
      rated.push({ group, rating: rating ?? "skip", note });
    }

    return { text: ratedText(rated, groups.length - rated.length) };
  }).catch(($, e, next) => next(e));
};
